#!/usr/bin/env python3
"""Source/parity tests for the Automaton-3 PostgreSQL durability seam."""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from harness.sdk.postgres_durable_execution import (
    PostgresDurableExecutionRegistry,
    PostgresWriterLeaseManager,
)
from harness.sdk.sovereign_execution import (
    ADMITTED,
    DENIED,
    ZERO_HASH,
    DurableExecutionRecord,
    SovereignExecutionError,
    WriterLeaseManager,
    canonical_hash,
)

SQL = (ROOT / "harness/sdk/sql/automaton3_postgres_durability_v1.sql").read_text(
    encoding="utf-8"
)
HASH = "1" * 64
COMMIT = "a" * 40
BINDING = "2" * 64


class FakeCursor:
    def __init__(self, connection: "FakeConnection"):
        self.connection = connection
        self.response = None

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        match = re.search(r"select aegis_private\.([a-z0-9_]+)\(", query)
        if not match:
            raise AssertionError(f"unexpected SQL: {query}")
        function = match.group(1)
        self.connection.calls.append((function, params))
        value = self.connection.responses[function]
        if isinstance(value, list):
            if not value:
                raise AssertionError(f"no fake response left for {function}")
            value = value.pop(0)
        if isinstance(value, Exception):
            raise value
        self.response = value

    def fetchone(self):
        return (self.response,)

    def close(self) -> None:
        self.connection.closes += 1


class FakeConnection:
    def __init__(self, **responses):
        self.responses = defaultdict(lambda: {"ok": True, "code": "NONE"})
        self.responses.update(responses)
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class PostgresDurabilitySourceTests(TestCase):
    def test_private_schema_and_no_security_definer(self):
        lower = SQL.lower()
        self.assertIn("create schema if not exists aegis_private", lower)
        self.assertIn("revoke all on schema aegis_private from public", lower)
        self.assertNotIn("security definer", lower)
        for table in re.findall(r"create table if not exists\s+([^\s(]+)", lower):
            self.assertTrue(table.startswith("aegis_private."), table)

    def test_concurrency_primitives_are_structural(self):
        lower = SQL.lower()
        self.assertGreaterEqual(lower.count("for update;"), 7)
        self.assertIn(
            "primary key (authority_domain, lease_generation, action_digest)", lower
        )
        self.assertIn("primary key (execution_id, idempotency_key)", lower)
        self.assertIn("on conflict (authority_domain) do nothing", lower)
        self.assertIn("on conflict (execution_id) do nothing", lower)

    def test_cancel_and_orphan_revoke_leases_in_same_function_body(self):
        lower = SQL.lower()
        for function in ("a3_cancel_execution_v1", "a3_mark_orphaned_v1"):
            start = lower.index(f"create or replace function aegis_private.{function}")
            end = lower.find("create or replace function", start + 20)
            body = lower[start:] if end == -1 else lower[start:end]
            self.assertIn("delete from aegis_private.a3_writer_leases_v1", body)
            self.assertIn("holder_identity_root = v_record.lease_holder", body)

    def test_public_execute_is_revoked_for_every_contract_function(self):
        created = set(
            re.findall(
                r"create or replace function aegis_private\.([a-z0-9_]+)\(",
                SQL.lower(),
            )
        )
        revoked = set(
            re.findall(
                r"revoke all on function aegis_private\.([a-z0-9_]+)\(",
                SQL.lower(),
            )
        )
        self.assertEqual(created, revoked)

    def test_sql_does_not_claim_or_implement_exactly_once_transport(self):
        lower = SQL.lower()
        self.assertIn("does not\n-- claim distributed exactly-once execution", lower)
        self.assertNotIn("clock_timestamp(", lower)
        self.assertNotIn("pg_sleep(", lower)


class PostgresDurabilityAdapterParityTests(TestCase):
    def test_acquire_matches_reference_fence_and_receipt_root(self):
        fake = FakeConnection(
            a3_writer_snapshot_v1={
                "generation": 0,
                "active": False,
            },
            a3_try_acquire_writer_v1={
                "ok": True,
                "code": "NONE",
                "lease_generation": 1,
            },
        )
        pg = PostgresWriterLeaseManager(fake)
        lease, receipt = pg.acquire(
            authority_domain="git",
            holder_identity_root=HASH,
            source_commit=COMMIT,
            expected_parent_state=ZERO_HASH,
        )

        ref = WriterLeaseManager()
        ref_lease, ref_receipt = ref.acquire(
            authority_domain="git",
            holder_identity_root=HASH,
            source_commit=COMMIT,
            expected_parent_state=ZERO_HASH,
        )

        self.assertEqual(lease, ref_lease)
        self.assertEqual(receipt.receipt_root, ref_receipt.receipt_root)
        self.assertEqual(receipt.outcome, ADMITTED)
        self.assertEqual(
            [call[0] for call in fake.calls],
            ["a3_writer_snapshot_v1", "a3_try_acquire_writer_v1"],
        )

    def test_active_writer_is_denied_without_mutating_acquire_call(self):
        fake = FakeConnection(
            a3_writer_snapshot_v1={
                "generation": 3,
                "active": True,
                "authority_domain": "git",
            }
        )
        pg = PostgresWriterLeaseManager(fake)
        lease, receipt = pg.acquire(
            authority_domain="git",
            holder_identity_root=HASH,
            source_commit=COMMIT,
            expected_parent_state=ZERO_HASH,
        )
        self.assertIsNone(lease)
        self.assertEqual(receipt.outcome, DENIED)
        self.assertIn("WRITER_ALREADY_ACTIVE", receipt.denial_codes)
        self.assertEqual([call[0] for call in fake.calls], ["a3_writer_snapshot_v1"])

    def test_authorize_preserves_multiple_denial_codes(self):
        fake = FakeConnection(
            a3_authorize_write_v1={
                "ok": False,
                "codes": ["STALE_FENCING_TOKEN", "REPLAYED_AUTHORITATIVE_ACTION"],
            }
        )
        receipt = PostgresWriterLeaseManager(fake).authorize_write(
            authority_domain="git",
            holder_identity_root=HASH,
            fencing_token="9" * 64,
            lease_generation=1,
            expected_parent_state=ZERO_HASH,
            action_digest="8" * 64,
        )
        self.assertEqual(receipt.outcome, DENIED)
        self.assertEqual(
            set(receipt.denial_codes),
            {"STALE_FENCING_TOKEN", "REPLAYED_AUTHORITATIVE_ACTION"},
        )

    def test_durable_root_matches_reference_canonical_hash(self):
        raw = {
            "workflow_identity": "wf",
            "owner": "operator",
            "source_commit": COMMIT,
            "workspace_binding": BINDING,
            "current_phase": "execute",
            "current_authority": ["external"],
            "last_completed_transition": 1,
            "pending_external_action": "idempotency-2",
            "retry_count": 0,
            "next_retry": None,
            "cancellation_state": "ACTIVE",
            "lease_holder": HASH,
            "parent_state_root": ZERO_HASH,
            "current_receipt_root": HASH,
            "failure_state": "",
            "status": "RUNNING",
            "last_heartbeat_generation": 2,
            "used_external_actions": ["idempotency-1", "idempotency-2"],
        }
        fake = FakeConnection(
            a3_execution_snapshot_v1={
                "ok": True,
                "code": "NONE",
                "record": raw,
                "row_revision": 4,
            }
        )
        pg = PostgresDurableExecutionRegistry(fake)
        actual = pg.root("exec")

        record = DurableExecutionRecord(
            "wf",
            "operator",
            COMMIT,
            BINDING,
            "execute",
            ("external",),
            1,
            "idempotency-2",
            0,
            None,
            "ACTIVE",
            HASH,
            ZERO_HASH,
            HASH,
            "",
            "RUNNING",
            2,
            {"idempotency-1", "idempotency-2"},
        )
        body = asdict(record)
        body["used_external_actions"] = sorted(record.used_external_actions)
        expected = canonical_hash("AEGIS_DURABLE_EXECUTION_V1", body)
        self.assertEqual(actual, expected)

    def test_database_error_fails_closed_without_retry(self):
        fake = FakeConnection(
            a3_writer_snapshot_v1=RuntimeError("connection lost after dispatch")
        )
        pg = PostgresWriterLeaseManager(fake)
        with self.assertRaisesRegex(
            SovereignExecutionError, "POSTGRES_DURABILITY_UNAVAILABLE"
        ):
            pg.current("git")
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.commits, 0)
        self.assertEqual(fake.rollbacks, 1)


    def test_candidate_manifest_binds_postgres_durability_sources(self):
        validator = (ROOT / "scripts/validate-automaton3.py").read_text(encoding="utf-8")
        for required in (
            "harness/sdk/postgres_durable_execution.py",
            "harness/sdk/sql/automaton3_postgres_durability_v1.sql",
            "sovereign-omega-v2/python/tests/test_automaton3_postgres_durability.py",
            "docs/security/AUTOMATON3_POSTGRES_DURABILITY_V1.md",
        ):
            self.assertIn(required, validator)

    def test_summary_declares_postgres_contract_without_exact_once_overclaim(self):
        runner = (ROOT / "scripts/run-automaton3-tests.py").read_text(encoding="utf-8")
        self.assertIn('"postgres_durability_contract_asserted": True', runner)
        self.assertIn('"distributed_exact_once_claimed": False', runner)


if __name__ == "__main__":
    main(verbosity=2)
