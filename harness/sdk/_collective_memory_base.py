"""UCI-6 admitted collective-memory reference.

Memory is evidence, never authority. Arbitrary evidence can enter quarantine,
but canonical evidence memory and its revocation/supersession controls require
an exact action-digest binding to a UCI-5 AdmissionRecord that is re-read from
the trusted local admission store.

This is a local SQLite reference only. It does not establish authenticated
database tamper resistance, distributed linearizability, semantic truth, or
production memory admission.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from harness.sdk.atomic_admission import (
    AdmissionRecordV1,
    AtomicAdmissionError,
    LocalSqliteAtomicAdmissionStoreV1,
    uci5_admission_policy_commitment,
)
from harness.sdk.sovereign_execution import canonical_bytes, canonical_hash
from harness.sdk.transition_receipts import TransitionIdentity

QUARANTINED_MEMORY_RECORD_KIND = "QUARANTINED_EVIDENCE_MEMORY_RECORD_V1"
MEMORY_PROJECTION_REQUEST_KIND = "MEMORY_PROJECTION_REQUEST_V1"
CANONICAL_MEMORY_RECORD_KIND = "CANONICAL_MEMORY_RECORD_V1"
MEMORY_CONTROL_REQUEST_KIND = "MEMORY_CONTROL_REQUEST_V1"
MEMORY_CONTROL_RECORD_KIND = "MEMORY_CONTROL_RECORD_V1"

EVIDENCE_ONLY = "EVIDENCE_ONLY"
ACTIVE = "ACTIVE"
REVOKED = "REVOKED"
SUPERSEDED = "SUPERSEDED"
REVOKE = "REVOKE"
SUPERSEDE = "SUPERSEDE"

ZERO_MEMORY_EVENT_ROOT = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MEMORY_CLASSES = frozenset({"EVIDENCE", "WORK_RESULT", "CALIBRATION", "CAPABILITY"})
UCI6_EPISTEMIC_TIER = "T2"

UCI6_MEMORY_POLICY_V1 = {
    "policy_id": "AEGIS_UCI6_MEMORY_POLICY_V1",
    "quarantine_write": "EVIDENCE_ONLY_NO_AUTHORITY",
    "canonical_projection": "REQUIRES_UCI5_ADMITTED_ACTION",
    "control_event": "REQUIRES_UCI5_ADMITTED_ACTION",
    "retrieval_authority": "EVIDENCE_ONLY",
    "canonical_truth_claim": "FORBIDDEN",
    "self_authorization": "FORBIDDEN",
    "epistemic_tier": UCI6_EPISTEMIC_TIER,
    "tier_promotion_during_projection": "FORBIDDEN",
    "destructive_delete": "FORBIDDEN",
    "accepted_uci5_admission_policy_commitment": uci5_admission_policy_commitment(),
    "production_memory_backend": "NOT_ESTABLISHED",
}


class CollectiveMemoryError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise CollectiveMemoryError(f"{name}:INVALID_SHA256")


def _require_string(name: str, value: str, *, max_length: int = 512) -> None:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise CollectiveMemoryError(f"{name}:INVALID_STRING")


def _require_nonce(value: str) -> None:
    _require_string("nonce", value, max_length=128)


def _require_memory_class(value: str) -> None:
    if value not in MEMORY_CLASSES:
        raise CollectiveMemoryError("MEMORY_CLASS_UNSUPPORTED")


def _require_tier(value: str, *, quarantine: bool = False) -> None:
    if value != UCI6_EPISTEMIC_TIER:
        code = "QUARANTINE_EPISTEMIC_TIER_UNSUPPORTED" if quarantine else "MEMORY_EPISTEMIC_TIER_UNSUPPORTED"
        raise CollectiveMemoryError(code)


def uci6_memory_policy_commitment() -> str:
    return canonical_hash("AEGIS_MEMORY_POLICY_COMMITMENT_V1", UCI6_MEMORY_POLICY_V1)


@dataclass(frozen=True)
class QuarantinedEvidenceMemoryRecordV1:
    record_kind: str
    content_digest: str
    media_type: str
    producer_ref: str
    source_ref: str
    memory_class: str
    epistemic_tier: str
    authority: str
    authority_weight_bps: int

    def __post_init__(self) -> None:
        if self.record_kind != QUARANTINED_MEMORY_RECORD_KIND:
            raise CollectiveMemoryError("QUARANTINE_RECORD_KIND_MISMATCH")
        _require_hash("content_digest", self.content_digest)
        _require_string("media_type", self.media_type, max_length=128)
        _require_string("producer_ref", self.producer_ref)
        _require_string("source_ref", self.source_ref)
        _require_memory_class(self.memory_class)
        _require_tier(self.epistemic_tier, quarantine=True)
        if self.authority != EVIDENCE_ONLY or self.authority_weight_bps != 0:
            raise CollectiveMemoryError("QUARANTINE_AUTHORITY_FORBIDDEN")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_QUARANTINED_MEMORY_RECORD_V1", asdict(self))


@dataclass(frozen=True)
class MemoryProjectionRequestV1:
    request_kind: str
    quarantine_root: str
    content_digest: str
    memory_class: str
    epistemic_tier: str
    memory_policy_commitment: str
    nonce: str

    def __post_init__(self) -> None:
        if self.request_kind != MEMORY_PROJECTION_REQUEST_KIND:
            raise CollectiveMemoryError("MEMORY_PROJECTION_REQUEST_KIND_MISMATCH")
        _require_hash("quarantine_root", self.quarantine_root)
        _require_hash("content_digest", self.content_digest)
        _require_memory_class(self.memory_class)
        _require_tier(self.epistemic_tier)
        _require_hash("memory_policy_commitment", self.memory_policy_commitment)
        _require_nonce(self.nonce)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_MEMORY_PROJECTION_REQUEST_V1", asdict(self))


@dataclass(frozen=True)
class CanonicalMemoryRecordV1:
    record_kind: str
    projection_request_root: str
    source_quarantine_root: str
    content_digest: str
    memory_class: str
    epistemic_tier: str
    authority: str
    authority_weight_bps: int
    source_transition_id: str
    source_admission_root: str
    memory_policy_commitment: str
    sequence: int
    prior_memory_event_root: str

    def __post_init__(self) -> None:
        if self.record_kind != CANONICAL_MEMORY_RECORD_KIND:
            raise CollectiveMemoryError("CANONICAL_MEMORY_RECORD_KIND_MISMATCH")
        for name in (
            "projection_request_root",
            "source_quarantine_root",
            "content_digest",
            "source_transition_id",
            "source_admission_root",
            "memory_policy_commitment",
            "prior_memory_event_root",
        ):
            _require_hash(name, getattr(self, name))
        _require_memory_class(self.memory_class)
        _require_tier(self.epistemic_tier)
        if self.authority != EVIDENCE_ONLY or self.authority_weight_bps != 0:
            raise CollectiveMemoryError("CANONICAL_MEMORY_AUTHORITY_FORBIDDEN")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence <= 0:
            raise CollectiveMemoryError("MEMORY_SEQUENCE_INVALID")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_CANONICAL_MEMORY_RECORD_V1", asdict(self))


@dataclass(frozen=True)
class MemoryControlRequestV1:
    request_kind: str
    operation: str
    target_memory_root: str
    replacement_memory_root: str | None
    memory_policy_commitment: str
    nonce: str

    def __post_init__(self) -> None:
        if self.request_kind != MEMORY_CONTROL_REQUEST_KIND:
            raise CollectiveMemoryError("MEMORY_CONTROL_REQUEST_KIND_MISMATCH")
        if self.operation not in {REVOKE, SUPERSEDE}:
            raise CollectiveMemoryError("MEMORY_CONTROL_OPERATION_UNSUPPORTED")
        _require_hash("target_memory_root", self.target_memory_root)
        _require_hash("memory_policy_commitment", self.memory_policy_commitment)
        _require_nonce(self.nonce)
        if self.operation == REVOKE:
            if self.replacement_memory_root is not None:
                raise CollectiveMemoryError("MEMORY_REVOKE_REPLACEMENT_FORBIDDEN")
        else:
            if self.replacement_memory_root is None:
                raise CollectiveMemoryError("MEMORY_SUPERSEDE_REPLACEMENT_REQUIRED")
            _require_hash("replacement_memory_root", self.replacement_memory_root)
            if self.replacement_memory_root == self.target_memory_root:
                raise CollectiveMemoryError("MEMORY_SUPERSEDE_SELF")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_MEMORY_CONTROL_REQUEST_V1", asdict(self))


@dataclass(frozen=True)
class MemoryControlRecordV1:
    record_kind: str
    control_request_root: str
    operation: str
    target_memory_root: str
    replacement_memory_root: str | None
    source_transition_id: str
    source_admission_root: str
    memory_policy_commitment: str
    sequence: int
    prior_memory_event_root: str

    def __post_init__(self) -> None:
        if self.record_kind != MEMORY_CONTROL_RECORD_KIND:
            raise CollectiveMemoryError("MEMORY_CONTROL_RECORD_KIND_MISMATCH")
        if self.operation not in {REVOKE, SUPERSEDE}:
            raise CollectiveMemoryError("MEMORY_CONTROL_OPERATION_UNSUPPORTED")
        for name in (
            "control_request_root",
            "target_memory_root",
            "source_transition_id",
            "source_admission_root",
            "memory_policy_commitment",
            "prior_memory_event_root",
        ):
            _require_hash(name, getattr(self, name))
        if self.operation == REVOKE:
            if self.replacement_memory_root is not None:
                raise CollectiveMemoryError("MEMORY_REVOKE_REPLACEMENT_FORBIDDEN")
        else:
            if self.replacement_memory_root is None:
                raise CollectiveMemoryError("MEMORY_SUPERSEDE_REPLACEMENT_REQUIRED")
            _require_hash("replacement_memory_root", self.replacement_memory_root)
            if self.replacement_memory_root == self.target_memory_root:
                raise CollectiveMemoryError("MEMORY_SUPERSEDE_SELF")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence <= 0:
            raise CollectiveMemoryError("MEMORY_SEQUENCE_INVALID")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_MEMORY_CONTROL_RECORD_V1", asdict(self))


@dataclass(frozen=True)
class MemoryStateV1:
    memory_policy_commitment: str
    sequence: int
    last_event_root: str

    def validate(self) -> None:
        _require_hash("memory_policy_commitment", self.memory_policy_commitment)
        _require_hash("last_event_root", self.last_event_root)
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise CollectiveMemoryError("MEMORY_STATE_SEQUENCE_INVALID")
        if self.sequence == 0 and self.last_event_root != ZERO_MEMORY_EVENT_ROOT:
            raise CollectiveMemoryError("MEMORY_STATE_GENESIS_ROOT_INVALID")
        if self.sequence > 0 and self.last_event_root == ZERO_MEMORY_EVENT_ROOT:
            raise CollectiveMemoryError("MEMORY_STATE_EVENT_ROOT_MISSING")


@dataclass(frozen=True)
class EffectiveMemoryViewV1:
    record: CanonicalMemoryRecordV1
    status: str
    replacement_memory_root: str | None


class LocalSqliteCollectiveMemoryStoreV1:
    def __init__(
        self,
        *,
        db_path: str | Path,
        memory_policy_commitment: str,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        _require_hash("memory_policy_commitment", memory_policy_commitment)
        self._fault_injector = fault_injector
        self._initialize(memory_policy_commitment)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=10.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize(self, memory_policy_commitment: str) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    memory_policy_commitment TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    last_event_root TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS quarantine_records (
                    memory_root TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_records (
                    memory_root TEXT PRIMARY KEY,
                    projection_request_root TEXT NOT NULL UNIQUE,
                    source_transition_id TEXT NOT NULL UNIQUE,
                    source_admission_root TEXT NOT NULL UNIQUE,
                    sequence INTEGER NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_control_records (
                    event_root TEXT PRIMARY KEY,
                    request_root TEXT NOT NULL UNIQUE,
                    source_transition_id TEXT NOT NULL UNIQUE,
                    source_admission_root TEXT NOT NULL UNIQUE,
                    target_memory_root TEXT NOT NULL,
                    replacement_memory_root TEXT,
                    sequence INTEGER NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                )
                """
            )
            row = connection.execute("SELECT * FROM memory_state WHERE singleton = 1").fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO memory_state(singleton, memory_policy_commitment, sequence, last_event_root)
                    VALUES (1, ?, 0, ?)
                    """,
                    (memory_policy_commitment, ZERO_MEMORY_EVENT_ROOT),
                )
            elif str(row["memory_policy_commitment"]) != memory_policy_commitment:
                raise CollectiveMemoryError("MEMORY_STORE_POLICY_CONFLICT")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _state_from_row(row: sqlite3.Row) -> MemoryStateV1:
        state = MemoryStateV1(
            memory_policy_commitment=str(row["memory_policy_commitment"]),
            sequence=int(row["sequence"]),
            last_event_root=str(row["last_event_root"]),
        )
        state.validate()
        return state

    def read_memory_state(self) -> MemoryStateV1:
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM memory_state WHERE singleton = 1").fetchone()
            if row is None:
                raise CollectiveMemoryError("MEMORY_STATE_MISSING")
            return self._state_from_row(row)
        finally:
            connection.close()

    @staticmethod
    def _record_from_payload(kind, payload_json: str, persisted_root: str):
        try:
            payload = json.loads(payload_json)
            if not isinstance(payload, dict):
                raise TypeError("payload must be object")
            record = kind(**payload)
        except (TypeError, ValueError, CollectiveMemoryError, json.JSONDecodeError) as exc:
            raise CollectiveMemoryError("MEMORY_PERSISTED_PAYLOAD_INVALID") from exc
        if record.root != persisted_root:
            raise CollectiveMemoryError("MEMORY_PERSISTED_ROOT_MISMATCH")
        return record

    def quarantine(self, record: QuarantinedEvidenceMemoryRecordV1) -> QuarantinedEvidenceMemoryRecordV1:
        if type(record) is not QuarantinedEvidenceMemoryRecordV1:
            raise CollectiveMemoryError("QUARANTINE_INPUT_TYPE_MISMATCH")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload_json FROM quarantine_records WHERE memory_root = ?",
                (record.root,),
            ).fetchone()
            if row is not None:
                existing = self._record_from_payload(
                    QuarantinedEvidenceMemoryRecordV1,
                    str(row["payload_json"]),
                    record.root,
                )
                if existing != record:
                    raise CollectiveMemoryError("QUARANTINE_ROOT_COLLISION")
                connection.commit()
                return existing
            connection.execute(
                "INSERT INTO quarantine_records(memory_root, payload_json) VALUES (?, ?)",
                (record.root, canonical_bytes(asdict(record)).decode("utf-8")),
            )
            connection.commit()
            return record
        except CollectiveMemoryError:
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise CollectiveMemoryError("MEMORY_TRANSACTION_FAILED") from exc
        finally:
            connection.close()

    def read_quarantine(self, memory_root: str) -> QuarantinedEvidenceMemoryRecordV1 | None:
        _require_hash("memory_root", memory_root)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT payload_json FROM quarantine_records WHERE memory_root = ?",
                (memory_root,),
            ).fetchone()
            if row is None:
                return None
            return self._record_from_payload(
                QuarantinedEvidenceMemoryRecordV1,
                str(row["payload_json"]),
                memory_root,
            )
        finally:
            connection.close()

    def read_canonical(self, memory_root: str) -> CanonicalMemoryRecordV1 | None:
        _require_hash("memory_root", memory_root)
        connection = self._connect()
        try:
            return self._read_canonical_conn(connection, memory_root)
        finally:
            connection.close()

    def _read_canonical_conn(self, connection: sqlite3.Connection, memory_root: str) -> CanonicalMemoryRecordV1 | None:
        row = connection.execute(
            "SELECT payload_json FROM canonical_records WHERE memory_root = ?",
            (memory_root,),
        ).fetchone()
        if row is None:
            return None
        return self._record_from_payload(CanonicalMemoryRecordV1, str(row["payload_json"]), memory_root)

    def quarantine_count(self) -> int:
        return self._count("quarantine_records")

    def canonical_count(self) -> int:
        return self._count("canonical_records")

    def control_count(self) -> int:
        return self._count("memory_control_records")

    def _count(self, table: str) -> int:
        if table not in {"quarantine_records", "canonical_records", "memory_control_records"}:
            raise CollectiveMemoryError("MEMORY_INTERNAL_TABLE_INVALID")
        connection = self._connect()
        try:
            row = connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            return int(row["n"] if row is not None else 0)
        finally:
            connection.close()

    @staticmethod
    def _verify_admitted_action(
        *,
        action_root: str,
        transition: TransitionIdentity,
        admission_record: AdmissionRecordV1,
        admission_store: LocalSqliteAtomicAdmissionStoreV1,
    ) -> None:
        if type(transition) is not TransitionIdentity or type(admission_record) is not AdmissionRecordV1:
            raise CollectiveMemoryError("MEMORY_ADMISSION_INPUT_TYPE_MISMATCH")
        if type(admission_store) is not LocalSqliteAtomicAdmissionStoreV1:
            raise CollectiveMemoryError("MEMORY_ADMISSION_STORE_TYPE_MISMATCH")
        if transition.action_digest != action_root:
            raise CollectiveMemoryError("MEMORY_ACTION_DIGEST_MISMATCH")
        if admission_record.transition_id != transition.root:
            raise CollectiveMemoryError("MEMORY_ADMISSION_TRANSITION_MISMATCH")
        if admission_record.admission_policy_commitment != uci5_admission_policy_commitment():
            raise CollectiveMemoryError("MEMORY_UCI5_POLICY_MISMATCH")
        try:
            persisted = admission_store.read_admission_record(transition.root)
        except AtomicAdmissionError as exc:
            raise CollectiveMemoryError("MEMORY_ADMISSION_STORE_INTEGRITY_FAILURE") from exc
        if persisted is None:
            raise CollectiveMemoryError("MEMORY_ADMISSION_NOT_PERSISTED")
        if persisted.root != admission_record.root:
            raise CollectiveMemoryError("MEMORY_ADMISSION_RECORD_MISMATCH")

    @staticmethod
    def _admitted_binding_replayed(
        connection: sqlite3.Connection,
        transition_id: str,
        admission_root: str,
    ) -> bool:
        canonical = connection.execute(
            """
            SELECT 1 FROM canonical_records
            WHERE source_transition_id = ? OR source_admission_root = ?
            """,
            (transition_id, admission_root),
        ).fetchone()
        if canonical is not None:
            return True
        control = connection.execute(
            """
            SELECT 1 FROM memory_control_records
            WHERE source_transition_id = ? OR source_admission_root = ?
            """,
            (transition_id, admission_root),
        ).fetchone()
        return control is not None

    @staticmethod
    def _update_event_state(
        connection: sqlite3.Connection,
        *,
        prior: MemoryStateV1,
        next_root: str,
    ) -> None:
        cursor = connection.execute(
            """
            UPDATE memory_state
            SET sequence = ?, last_event_root = ?
            WHERE singleton = 1
              AND memory_policy_commitment = ?
              AND sequence = ?
              AND last_event_root = ?
            """,
            (
                prior.sequence + 1,
                next_root,
                prior.memory_policy_commitment,
                prior.sequence,
                prior.last_event_root,
            ),
        )
        if cursor.rowcount != 1:
            raise CollectiveMemoryError("MEMORY_EVENT_COMPARE_AND_SWAP_FAILED")

    def project_canonical(
        self,
        *,
        request: MemoryProjectionRequestV1,
        transition: TransitionIdentity,
        admission_record: AdmissionRecordV1,
        admission_store: LocalSqliteAtomicAdmissionStoreV1,
    ) -> CanonicalMemoryRecordV1:
        if type(request) is not MemoryProjectionRequestV1:
            raise CollectiveMemoryError("MEMORY_PROJECTION_INPUT_TYPE_MISMATCH")
        if request.memory_policy_commitment != uci6_memory_policy_commitment():
            raise CollectiveMemoryError("CURRENT_MEMORY_POLICY_MISMATCH")
        self._verify_admitted_action(
            action_root=request.root,
            transition=transition,
            admission_record=admission_record,
            admission_store=admission_store,
        )
        quarantine = self.read_quarantine(request.quarantine_root)
        if quarantine is None:
            raise CollectiveMemoryError("MEMORY_QUARANTINE_SOURCE_MISSING")
        if (
            quarantine.content_digest != request.content_digest
            or quarantine.memory_class != request.memory_class
            or quarantine.epistemic_tier != request.epistemic_tier
        ):
            raise CollectiveMemoryError("MEMORY_PROJECTION_SOURCE_MISMATCH")
        if request.epistemic_tier != UCI6_EPISTEMIC_TIER:
            raise CollectiveMemoryError("MEMORY_TIER_PROMOTION_FORBIDDEN")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            state_row = connection.execute("SELECT * FROM memory_state WHERE singleton = 1").fetchone()
            if state_row is None:
                raise CollectiveMemoryError("MEMORY_STATE_MISSING")
            current = self._state_from_row(state_row)
            if current.memory_policy_commitment != request.memory_policy_commitment:
                raise CollectiveMemoryError("CURRENT_MEMORY_POLICY_MISMATCH")
            duplicate = connection.execute(
                "SELECT 1 FROM canonical_records WHERE projection_request_root = ?",
                (request.root,),
            ).fetchone()
            if duplicate is not None:
                raise CollectiveMemoryError("MEMORY_PROJECTION_REPLAY")
            if self._admitted_binding_replayed(connection, transition.root, admission_record.root):
                raise CollectiveMemoryError("MEMORY_ADMITTED_ACTION_REPLAY")

            sequence = current.sequence + 1
            record = CanonicalMemoryRecordV1(
                record_kind=CANONICAL_MEMORY_RECORD_KIND,
                projection_request_root=request.root,
                source_quarantine_root=quarantine.root,
                content_digest=quarantine.content_digest,
                memory_class=quarantine.memory_class,
                epistemic_tier=quarantine.epistemic_tier,
                authority=EVIDENCE_ONLY,
                authority_weight_bps=0,
                source_transition_id=transition.root,
                source_admission_root=admission_record.root,
                memory_policy_commitment=current.memory_policy_commitment,
                sequence=sequence,
                prior_memory_event_root=current.last_event_root,
            )
            connection.execute(
                """
                INSERT INTO canonical_records(
                    memory_root, projection_request_root, source_transition_id,
                    source_admission_root, sequence, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.root,
                    request.root,
                    transition.root,
                    admission_record.root,
                    sequence,
                    canonical_bytes(asdict(record)).decode("utf-8"),
                ),
            )
            if self._fault_injector is not None:
                self._fault_injector("AFTER_CANONICAL_INSERT")
            self._update_event_state(connection, prior=current, next_root=record.root)
            connection.commit()
            return record
        except CollectiveMemoryError:
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise CollectiveMemoryError("MEMORY_PROJECTION_REPLAY") from exc
        except Exception as exc:
            connection.rollback()
            raise CollectiveMemoryError("MEMORY_TRANSACTION_FAILED") from exc
        finally:
            connection.close()

    def _effective_view_conn(self, connection: sqlite3.Connection, memory_root: str) -> EffectiveMemoryViewV1:
        record = self._read_canonical_conn(connection, memory_root)
        if record is None:
            raise CollectiveMemoryError("CANONICAL_MEMORY_NOT_FOUND")
        rows = connection.execute(
            "SELECT event_root, payload_json FROM memory_control_records WHERE target_memory_root = ? ORDER BY sequence",
            (memory_root,),
        ).fetchall()
        if not rows:
            return EffectiveMemoryViewV1(record=record, status=ACTIVE, replacement_memory_root=None)
        if len(rows) != 1:
            raise CollectiveMemoryError("MEMORY_CONTROL_HISTORY_INVALID")
        control = self._record_from_payload(
            MemoryControlRecordV1,
            str(rows[0]["payload_json"]),
            str(rows[0]["event_root"]),
        )
        if control.operation == REVOKE:
            return EffectiveMemoryViewV1(record=record, status=REVOKED, replacement_memory_root=None)
        return EffectiveMemoryViewV1(
            record=record,
            status=SUPERSEDED,
            replacement_memory_root=control.replacement_memory_root,
        )

    def get_effective(self, memory_root: str) -> EffectiveMemoryViewV1:
        _require_hash("memory_root", memory_root)
        connection = self._connect()
        try:
            return self._effective_view_conn(connection, memory_root)
        finally:
            connection.close()

    def control_memory(
        self,
        *,
        request: MemoryControlRequestV1,
        transition: TransitionIdentity,
        admission_record: AdmissionRecordV1,
        admission_store: LocalSqliteAtomicAdmissionStoreV1,
    ) -> MemoryControlRecordV1:
        if type(request) is not MemoryControlRequestV1:
            raise CollectiveMemoryError("MEMORY_CONTROL_INPUT_TYPE_MISMATCH")
        if request.memory_policy_commitment != uci6_memory_policy_commitment():
            raise CollectiveMemoryError("CURRENT_MEMORY_POLICY_MISMATCH")
        self._verify_admitted_action(
            action_root=request.root,
            transition=transition,
            admission_record=admission_record,
            admission_store=admission_store,
        )

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            state_row = connection.execute("SELECT * FROM memory_state WHERE singleton = 1").fetchone()
            if state_row is None:
                raise CollectiveMemoryError("MEMORY_STATE_MISSING")
            current = self._state_from_row(state_row)
            if current.memory_policy_commitment != request.memory_policy_commitment:
                raise CollectiveMemoryError("CURRENT_MEMORY_POLICY_MISMATCH")
            duplicate = connection.execute(
                "SELECT 1 FROM memory_control_records WHERE request_root = ?",
                (request.root,),
            ).fetchone()
            if duplicate is not None:
                raise CollectiveMemoryError("MEMORY_CONTROL_REPLAY")
            if self._admitted_binding_replayed(connection, transition.root, admission_record.root):
                raise CollectiveMemoryError("MEMORY_ADMITTED_ACTION_REPLAY")

            target = self._effective_view_conn(connection, request.target_memory_root)
            if target.status != ACTIVE:
                raise CollectiveMemoryError("MEMORY_TARGET_NOT_ACTIVE")
            if request.operation == SUPERSEDE:
                assert request.replacement_memory_root is not None
                replacement = self._effective_view_conn(connection, request.replacement_memory_root)
                if replacement.status != ACTIVE:
                    raise CollectiveMemoryError("MEMORY_REPLACEMENT_NOT_ACTIVE")

            sequence = current.sequence + 1
            record = MemoryControlRecordV1(
                record_kind=MEMORY_CONTROL_RECORD_KIND,
                control_request_root=request.root,
                operation=request.operation,
                target_memory_root=request.target_memory_root,
                replacement_memory_root=request.replacement_memory_root,
                source_transition_id=transition.root,
                source_admission_root=admission_record.root,
                memory_policy_commitment=current.memory_policy_commitment,
                sequence=sequence,
                prior_memory_event_root=current.last_event_root,
            )
            connection.execute(
                """
                INSERT INTO memory_control_records(
                    event_root, request_root, source_transition_id, source_admission_root,
                    target_memory_root, replacement_memory_root, sequence, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.root,
                    request.root,
                    transition.root,
                    admission_record.root,
                    request.target_memory_root,
                    request.replacement_memory_root,
                    sequence,
                    canonical_bytes(asdict(record)).decode("utf-8"),
                ),
            )
            if self._fault_injector is not None:
                self._fault_injector("AFTER_CONTROL_INSERT")
            self._update_event_state(connection, prior=current, next_root=record.root)
            connection.commit()
            return record
        except CollectiveMemoryError:
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise CollectiveMemoryError("MEMORY_CONTROL_REPLAY") from exc
        except Exception as exc:
            connection.rollback()
            raise CollectiveMemoryError("MEMORY_TRANSACTION_FAILED") from exc
        finally:
            connection.close()
