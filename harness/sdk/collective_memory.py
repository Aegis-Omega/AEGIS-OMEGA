"""UCI-6 admitted collective-memory public contract.

The original RED-tested implementation is retained in the internal
``_collective_memory_base`` module.  This public layer adds the UCI-6 memory
pre-state invariant discovered by adversarial review: every projection/control
request commits the exact memory event sequence and event root that existed
before admission, and mutation rechecks that pair inside the same SQLite
``BEGIN IMMEDIATE`` transaction.

Memory remains evidence only.  Neither canonical memory nor retrieval becomes
an authority or truth claim.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass

from harness.sdk import _collective_memory_base as _base
from harness.sdk.atomic_admission import (
    AdmissionRecordV1,
    LocalSqliteAtomicAdmissionStoreV1,
    uci5_admission_policy_commitment,
)
from harness.sdk.sovereign_execution import canonical_bytes, canonical_hash
from harness.sdk.transition_receipts import TransitionIdentity

# Stable public constants/classes whose semantics are unchanged from the first
# UCI-6 implementation.
QUARANTINED_MEMORY_RECORD_KIND = _base.QUARANTINED_MEMORY_RECORD_KIND
MEMORY_PROJECTION_REQUEST_KIND = _base.MEMORY_PROJECTION_REQUEST_KIND
CANONICAL_MEMORY_RECORD_KIND = _base.CANONICAL_MEMORY_RECORD_KIND
MEMORY_CONTROL_REQUEST_KIND = _base.MEMORY_CONTROL_REQUEST_KIND
MEMORY_CONTROL_RECORD_KIND = _base.MEMORY_CONTROL_RECORD_KIND

EVIDENCE_ONLY = _base.EVIDENCE_ONLY
ACTIVE = _base.ACTIVE
REVOKED = _base.REVOKED
SUPERSEDED = _base.SUPERSEDED
REVOKE = _base.REVOKE
SUPERSEDE = _base.SUPERSEDE

ZERO_MEMORY_EVENT_ROOT = _base.ZERO_MEMORY_EVENT_ROOT
MEMORY_CLASSES = _base.MEMORY_CLASSES
UCI6_EPISTEMIC_TIER = _base.UCI6_EPISTEMIC_TIER

CollectiveMemoryError = _base.CollectiveMemoryError
QuarantinedEvidenceMemoryRecordV1 = _base.QuarantinedEvidenceMemoryRecordV1
CanonicalMemoryRecordV1 = _base.CanonicalMemoryRecordV1
MemoryControlRecordV1 = _base.MemoryControlRecordV1
MemoryStateV1 = _base.MemoryStateV1
EffectiveMemoryViewV1 = _base.EffectiveMemoryViewV1

UCI6_MEMORY_POLICY_V1 = {
    **_base.UCI6_MEMORY_POLICY_V1,
    "memory_prestate_binding": "REQUIRED",
}


def uci6_memory_policy_commitment() -> str:
    return canonical_hash("AEGIS_MEMORY_POLICY_COMMITMENT_V1", UCI6_MEMORY_POLICY_V1)


def _require_memory_prestate(sequence: int, event_root: str) -> None:
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise CollectiveMemoryError("MEMORY_PRESTATE_SEQUENCE_INVALID")
    _base._require_hash("expected_memory_event_root", event_root)
    if sequence == 0 and event_root != ZERO_MEMORY_EVENT_ROOT:
        raise CollectiveMemoryError("MEMORY_PRESTATE_GENESIS_ROOT_INVALID")
    if sequence > 0 and event_root == ZERO_MEMORY_EVENT_ROOT:
        raise CollectiveMemoryError("MEMORY_PRESTATE_EVENT_ROOT_MISSING")


@dataclass(frozen=True)
class MemoryProjectionRequestV1:
    request_kind: str
    quarantine_root: str
    content_digest: str
    memory_class: str
    epistemic_tier: str
    memory_policy_commitment: str
    expected_memory_sequence: int
    expected_memory_event_root: str
    nonce: str

    def __post_init__(self) -> None:
        if self.request_kind != MEMORY_PROJECTION_REQUEST_KIND:
            raise CollectiveMemoryError("MEMORY_PROJECTION_REQUEST_KIND_MISMATCH")
        _base._require_hash("quarantine_root", self.quarantine_root)
        _base._require_hash("content_digest", self.content_digest)
        _base._require_memory_class(self.memory_class)
        _base._require_tier(self.epistemic_tier)
        _base._require_hash("memory_policy_commitment", self.memory_policy_commitment)
        _require_memory_prestate(self.expected_memory_sequence, self.expected_memory_event_root)
        _base._require_nonce(self.nonce)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_MEMORY_PROJECTION_REQUEST_V1", asdict(self))


@dataclass(frozen=True)
class MemoryControlRequestV1:
    request_kind: str
    operation: str
    target_memory_root: str
    replacement_memory_root: str | None
    memory_policy_commitment: str
    expected_memory_sequence: int
    expected_memory_event_root: str
    nonce: str

    def __post_init__(self) -> None:
        if self.request_kind != MEMORY_CONTROL_REQUEST_KIND:
            raise CollectiveMemoryError("MEMORY_CONTROL_REQUEST_KIND_MISMATCH")
        if self.operation not in {REVOKE, SUPERSEDE}:
            raise CollectiveMemoryError("MEMORY_CONTROL_OPERATION_UNSUPPORTED")
        _base._require_hash("target_memory_root", self.target_memory_root)
        _base._require_hash("memory_policy_commitment", self.memory_policy_commitment)
        _require_memory_prestate(self.expected_memory_sequence, self.expected_memory_event_root)
        _base._require_nonce(self.nonce)
        if self.operation == REVOKE:
            if self.replacement_memory_root is not None:
                raise CollectiveMemoryError("MEMORY_REVOKE_REPLACEMENT_FORBIDDEN")
        else:
            if self.replacement_memory_root is None:
                raise CollectiveMemoryError("MEMORY_SUPERSEDE_REPLACEMENT_REQUIRED")
            _base._require_hash("replacement_memory_root", self.replacement_memory_root)
            if self.replacement_memory_root == self.target_memory_root:
                raise CollectiveMemoryError("MEMORY_SUPERSEDE_SELF")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_MEMORY_CONTROL_REQUEST_V1", asdict(self))


class LocalSqliteCollectiveMemoryStoreV1(_base.LocalSqliteCollectiveMemoryStoreV1):
    """Local SQLite memory reference with admission + memory-prestate binding."""

    @staticmethod
    def _verify_admitted_action(
        *,
        action_root: str,
        transition: TransitionIdentity,
        admission_record: AdmissionRecordV1,
        admission_store: LocalSqliteAtomicAdmissionStoreV1,
    ) -> None:
        _base.LocalSqliteCollectiveMemoryStoreV1._verify_admitted_action(
            action_root=action_root,
            transition=transition,
            admission_record=admission_record,
            admission_store=admission_store,
        )
        # UCI-5 currently has no rotation API, but UCI-6 still refuses to consume
        # an admitted action after policy/epoch/fence control-plane drift.
        admission_state = admission_store.read_state()
        if admission_state.admission_policy_commitment != admission_record.admission_policy_commitment:
            raise CollectiveMemoryError("MEMORY_ADMISSION_POLICY_STALE")
        if admission_state.authority_epoch != admission_record.authority_epoch:
            raise CollectiveMemoryError("MEMORY_ADMISSION_AUTHORITY_EPOCH_STALE")
        if admission_state.fence_commitment != admission_record.fence_commitment:
            raise CollectiveMemoryError("MEMORY_ADMISSION_FENCE_STALE")
        if admission_record.admission_policy_commitment != uci5_admission_policy_commitment():
            raise CollectiveMemoryError("MEMORY_UCI5_POLICY_MISMATCH")

    @staticmethod
    def _require_current_memory_prestate(current: MemoryStateV1, *, sequence: int, event_root: str) -> None:
        if current.sequence != sequence or current.last_event_root != event_root:
            raise CollectiveMemoryError("MEMORY_PRESTATE_MISMATCH")

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
            # Replay classification has precedence over stale-prestate reporting.
            # This preserves a stable machine code for an exact duplicate and for
            # the losing contender after BEGIN IMMEDIATE serializes a race.
            duplicate = connection.execute(
                "SELECT 1 FROM canonical_records WHERE projection_request_root = ?",
                (request.root,),
            ).fetchone()
            if duplicate is not None:
                raise CollectiveMemoryError("MEMORY_PROJECTION_REPLAY")
            if self._admitted_binding_replayed(connection, transition.root, admission_record.root):
                raise CollectiveMemoryError("MEMORY_ADMITTED_ACTION_REPLAY")
            self._require_current_memory_prestate(
                current,
                sequence=request.expected_memory_sequence,
                event_root=request.expected_memory_event_root,
            )

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
            self._require_current_memory_prestate(
                current,
                sequence=request.expected_memory_sequence,
                event_root=request.expected_memory_event_root,
            )

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