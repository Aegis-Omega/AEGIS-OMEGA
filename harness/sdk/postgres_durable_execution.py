#!/usr/bin/env python3
"""Transactional PostgreSQL backend for the Automaton-3 reference semantics.

This module intentionally has no psycopg/asyncpg dependency. A caller injects a
PEP-249-style PostgreSQL connection. The SQL contract lives in
harness/sdk/sql/automaton3_postgres_durability_v1.sql.

Security / epistemic boundary:
- DB failures fail closed; write calls are never automatically retried.
- PostgreSQL serializes lease/execution transitions; it does not make an
  external provider side effect exactly-once.
- Existing sovereign_execution canonical hashing remains authoritative. SQL
  does not reimplement JCS/canonical hashing.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Protocol, Sequence

from harness.sdk.sovereign_execution import (
    ADMITTED,
    DENIED,
    ZERO_HASH,
    DurableExecutionRecord,
    LeaseReceipt,
    SovereignExecutionError,
    WriterLease,
    _assert_authority_string,
    _assert_git,
    _assert_hash,
    canonical_hash,
)


class DBAPIConnection(Protocol):
    """Minimal synchronous connection contract; compatible with psycopg-style DB-API."""

    def cursor(self) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise SovereignExecutionError("POSTGRES_DURABILITY_INVALID_RESPONSE") from exc
    if not isinstance(value, dict):
        raise SovereignExecutionError("POSTGRES_DURABILITY_INVALID_RESPONSE")
    return value


def _codes(result: dict[str, Any]) -> list[str]:
    raw = result.get("codes")
    if raw is None:
        code = result.get("code", "NONE")
        raw = [] if code in (None, "", "NONE") else [code]
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise SovereignExecutionError("POSTGRES_DURABILITY_INVALID_RESPONSE")
    return sorted(set(raw))


def _lease_receipt(
    operation: str,
    domain: str,
    generation: int,
    token: str,
    reasons: Sequence[str],
) -> LeaseReceipt:
    denial_codes = tuple(sorted(set(reasons)))
    body = {
        "operation": operation,
        "outcome": ADMITTED if not denial_codes else DENIED,
        "authority_domain": domain,
        "lease_generation": generation,
        "fencing_token_digest": canonical_hash("AEGIS_FENCE_TOKEN_REDACTION_V1", token),
        "denial_codes": list(denial_codes),
    }
    return LeaseReceipt(
        operation=operation,
        outcome=body["outcome"],
        authority_domain=domain,
        lease_generation=generation,
        fencing_token_digest=body["fencing_token_digest"],
        denial_codes=denial_codes,
        receipt_root=canonical_hash("AEGIS_LEASE_RECEIPT_V1", body),
    )


class _PostgresCalls:
    def __init__(self, connection: DBAPIConnection):
        self._connection = connection

    def _call(self, function: str, parameters: Sequence[Any]) -> dict[str, Any]:
        placeholders = ", ".join(["%s"] * len(parameters))
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"select aegis_private.{function}({placeholders})",
                tuple(parameters),
            )
            row = cursor.fetchone()
            if row is None or len(row) != 1:
                raise SovereignExecutionError("POSTGRES_DURABILITY_INVALID_RESPONSE")
            result = _payload(row[0])
            self._connection.commit()
            return result
        except SovereignExecutionError:
            try:
                self._connection.rollback()
            finally:
                raise
        except Exception as exc:
            try:
                self._connection.rollback()
            finally:
                raise SovereignExecutionError("POSTGRES_DURABILITY_UNAVAILABLE") from exc
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _require_ok(result: dict[str, Any]) -> None:
        if result.get("ok") is True:
            return
        reasons = _codes(result)
        raise SovereignExecutionError(reasons[0] if reasons else "POSTGRES_DURABILITY_DENIED")


class PostgresWriterLeaseManager(_PostgresCalls):
    """Drop-in writer-lease semantics with the serialization boundary in PostgreSQL."""

    def current(self, authority_domain: str) -> WriterLease | None:
        result = self._call("a3_writer_snapshot_v1", [authority_domain])
        if not result.get("active"):
            return None
        return WriterLease(
            schema_version="1.0.0",
            authority_domain=str(result["authority_domain"]),
            holder_identity_root=str(result["holder_identity_root"]),
            source_commit=str(result["source_commit"]),
            lease_generation=int(result["lease_generation"]),
            fencing_token=str(result["fencing_token"]),
            expected_parent_state=str(result["expected_parent_state"]),
        )

    def acquire(
        self,
        *,
        authority_domain: str,
        holder_identity_root: str,
        source_commit: str,
        expected_parent_state: str,
    ) -> tuple[WriterLease | None, LeaseReceipt]:
        reasons: list[str] = []
        try:
            _assert_hash("holder_identity_root", holder_identity_root)
        except SovereignExecutionError as exc:
            reasons.append(str(exc))
        try:
            _assert_git("source_commit", source_commit)
        except SovereignExecutionError as exc:
            reasons.append(str(exc))
        try:
            _assert_hash("expected_parent_state", expected_parent_state)
        except SovereignExecutionError as exc:
            reasons.append(str(exc))

        snapshot = self._call("a3_writer_snapshot_v1", [authority_domain])
        generation = int(snapshot.get("generation", 0)) + 1
        if snapshot.get("active"):
            reasons.append("WRITER_ALREADY_ACTIVE")

        if reasons:
            receipt = _lease_receipt(
                "ACQUIRE", authority_domain, generation, ZERO_HASH, reasons
            )
            return None, receipt

        token = canonical_hash(
            "AEGIS_WRITER_FENCE_V1",
            {
                "authority_domain": authority_domain,
                "holder_identity_root": holder_identity_root,
                "source_commit": source_commit,
                "lease_generation": generation,
                "expected_parent_state": expected_parent_state,
            },
        )
        result = self._call(
            "a3_try_acquire_writer_v1",
            [
                authority_domain,
                holder_identity_root,
                source_commit,
                expected_parent_state,
                generation - 1,
                token,
            ],
        )
        sql_reasons = _codes(result)
        actual_generation = int(result.get("lease_generation", generation))
        if sql_reasons:
            return None, _lease_receipt(
                "ACQUIRE",
                authority_domain,
                actual_generation,
                ZERO_HASH,
                sql_reasons,
            )

        lease = WriterLease(
            "1.0.0",
            authority_domain,
            holder_identity_root,
            source_commit,
            actual_generation,
            token,
            expected_parent_state,
        )
        return lease, _lease_receipt(
            "ACQUIRE", authority_domain, actual_generation, token, ()
        )

    def authorize_write(
        self,
        *,
        authority_domain: str,
        holder_identity_root: str,
        fencing_token: str,
        lease_generation: int,
        expected_parent_state: str,
        action_digest: str,
    ) -> LeaseReceipt:
        result = self._call(
            "a3_authorize_write_v1",
            [
                authority_domain,
                holder_identity_root,
                fencing_token,
                lease_generation,
                expected_parent_state,
                action_digest,
            ],
        )
        return _lease_receipt(
            "AUTHORIZE_WRITE",
            authority_domain,
            lease_generation,
            fencing_token,
            _codes(result),
        )

    def advance(
        self,
        *,
        authority_domain: str,
        fencing_token: str,
        new_parent_state: str,
    ) -> LeaseReceipt:
        result = self._call(
            "a3_advance_writer_v1",
            [authority_domain, fencing_token, new_parent_state],
        )
        generation = int(result.get("lease_generation", 0))
        return _lease_receipt(
            "ADVANCE",
            authority_domain,
            generation,
            fencing_token,
            _codes(result),
        )

    def revoke(self, authority_domain: str, holder_identity_root: str) -> LeaseReceipt:
        result = self._call(
            "a3_revoke_writer_v1", [authority_domain, holder_identity_root]
        )
        generation = int(result.get("lease_generation", 0))
        token = str(result.get("fencing_token") or ZERO_HASH)
        return _lease_receipt(
            "REVOKE", authority_domain, generation, token, _codes(result)
        )


class PostgresDurableExecutionRegistry(_PostgresCalls):
    """Persistent Automaton-3 registry with row-lock/CAS transitions."""

    def register(self, execution_id: str, record: DurableExecutionRecord) -> str:
        if record.status != "PLANNED":
            raise SovereignExecutionError("DURABLE_MUST_REGISTER_AS_PLANNED")
        result = self._call(
            "a3_register_execution_v1",
            [
                execution_id,
                record.workflow_identity,
                record.owner,
                record.source_commit,
                record.workspace_binding,
                record.current_phase,
                list(record.current_authority),
                record.last_completed_transition,
                record.pending_external_action,
                record.retry_count,
                record.next_retry,
                record.cancellation_state,
                record.lease_holder,
                record.parent_state_root,
                record.current_receipt_root,
                record.failure_state,
                record.status,
                record.last_heartbeat_generation,
            ],
        )
        self._require_ok(result)
        return self.root(execution_id)

    def transition(
        self,
        execution_id: str,
        *,
        status: str,
        phase: str,
        transition_sequence: int,
        receipt_root: str,
    ) -> str:
        result = self._call(
            "a3_transition_execution_v1",
            [execution_id, status, phase, transition_sequence, receipt_root],
        )
        self._require_ok(result)
        return self.root(execution_id)

    def heartbeat(self, execution_id: str, generation: int) -> str:
        result = self._call(
            "a3_heartbeat_execution_v1", [execution_id, generation]
        )
        self._require_ok(result)
        return self.root(execution_id)

    def mark_orphaned(
        self, execution_id: str, current_generation: int, maximum_gap: int
    ) -> str:
        result = self._call(
            "a3_mark_orphaned_v1",
            [execution_id, current_generation, maximum_gap],
        )
        self._require_ok(result)
        return self.root(execution_id)

    def cancel(self, execution_id: str) -> str:
        result = self._call("a3_cancel_execution_v1", [execution_id])
        self._require_ok(result)
        return self.root(execution_id)

    def claim_external_action(self, execution_id: str, idempotency_key: str) -> str:
        _assert_authority_string("idempotency_key", idempotency_key)
        result = self._call(
            "a3_claim_external_action_v1", [execution_id, idempotency_key]
        )
        self._require_ok(result)
        return self.root(execution_id)

    def get(self, execution_id: str) -> DurableExecutionRecord:
        result = self._call("a3_execution_snapshot_v1", [execution_id])
        self._require_ok(result)
        raw = result.get("record")
        if not isinstance(raw, dict):
            raise SovereignExecutionError("POSTGRES_DURABILITY_INVALID_RESPONSE")
        actions = raw.get("used_external_actions", [])
        authority = raw.get("current_authority", [])
        if not isinstance(actions, list) or not isinstance(authority, list):
            raise SovereignExecutionError("POSTGRES_DURABILITY_INVALID_RESPONSE")
        return DurableExecutionRecord(
            workflow_identity=str(raw["workflow_identity"]),
            owner=str(raw["owner"]),
            source_commit=str(raw["source_commit"]),
            workspace_binding=str(raw["workspace_binding"]),
            current_phase=str(raw["current_phase"]),
            current_authority=tuple(str(item) for item in authority),
            last_completed_transition=int(raw["last_completed_transition"]),
            pending_external_action=str(raw["pending_external_action"]),
            retry_count=int(raw["retry_count"]),
            next_retry=(
                None if raw.get("next_retry") is None else int(raw["next_retry"])
            ),
            cancellation_state=str(raw["cancellation_state"]),
            lease_holder=str(raw["lease_holder"]),
            parent_state_root=str(raw["parent_state_root"]),
            current_receipt_root=str(raw["current_receipt_root"]),
            failure_state=str(raw["failure_state"]),
            status=str(raw["status"]),
            last_heartbeat_generation=int(raw["last_heartbeat_generation"]),
            used_external_actions=set(str(item) for item in actions),
        )

    def root(self, execution_id: str) -> str:
        record = self.get(execution_id)
        body = asdict(record)
        body["used_external_actions"] = sorted(record.used_external_actions)
        return canonical_hash("AEGIS_DURABLE_EXECUTION_V1", body)
