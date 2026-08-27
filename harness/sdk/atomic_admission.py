"""UCI-5 local transactional atomic-admission reference.

This module is downstream of the frozen UCI-4 proofline. It does not reinterpret
DecisionReceipt, ExecutionReceipt, EffectReceipt, or CompleteVerification. It
recomputes the exact UCI-4 verifier result, then applies a fresh UCI-5 admission
policy to the *current* state/policy/authority-epoch/fence snapshot.

Reference-store scope:
- SQLite on one local database file;
- one transaction commits AdmissionRecord + canonical state, or neither;
- no distributed-linearizability or production-admission claim;
- no external/world mutation is performed here.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from harness.sdk.complete_verifier import (
    COMPLETE_VERIFICATION_RESULT_KIND,
    TRUE,
    CompleteVerificationResult,
    CompleteVerifier,
    complete_verifier_policy_commitment,
)
from harness.sdk.effect_adapters import EffectWitness
from harness.sdk.effect_verifier import EffectVerificationResult
from harness.sdk.sovereign_execution import canonical_bytes, canonical_hash
from harness.sdk.transition_receipts import (
    DecisionReceipt,
    EffectReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    admission_policy_commitment as source_admission_policy_commitment,
)

ADMISSION_RECORD_KIND = "ADMISSION_RECORD_V1"
ZERO_ADMISSION_ROOT = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

UCI5_ADMISSION_POLICY_V1 = {
    "policy_id": "AEGIS_UCI5_ADMISSION_POLICY_V1",
    "accepted_complete_verification_result_kind": COMPLETE_VERIFICATION_RESULT_KIND,
    "accepted_complete_verifier_policy_commitment": complete_verifier_policy_commitment(),
    "accepted_source_admission_policy_commitment": source_admission_policy_commitment(),
    "atomic_admission": "LOCAL_SQLITE_REFERENCE_ONLY",
    "effect_bound_admission": "REFERENCE_ONLY",
    "complete_verification_recompute": "REQUIRED",
    "current_state_match": "REQUIRED",
    "current_policy_match": "REQUIRED",
    "current_authority_epoch_match": "REQUIRED",
    "current_fence_match": "REQUIRED",
    "caller_supplied_next_state": "FORBIDDEN",
    "distributed_linearizability": "NOT_ESTABLISHED",
    "production_admission": "NOT_ESTABLISHED",
}


class AtomicAdmissionError(ValueError):
    """Fail-closed UCI-5 admission error with a stable machine code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise AtomicAdmissionError(f"{name}:INVALID_SHA256")


def _require_epoch(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AtomicAdmissionError("AUTHORITY_EPOCH_INVALID")


def uci5_admission_policy_commitment() -> str:
    return canonical_hash("AEGIS_ADMISSION_POLICY_COMMITMENT_V1", UCI5_ADMISSION_POLICY_V1)


@dataclass(frozen=True)
class AdmissionRecordV1:
    record_kind: str
    transition_id: str
    complete_verification_root: str
    source_admission_policy_commitment: str
    admission_policy_commitment: str
    prior_state_commitment: str
    next_state_commitment: str
    authority_epoch: int
    fence_commitment: str
    sequence: int
    prior_admission_root: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.record_kind != ADMISSION_RECORD_KIND:
            raise AtomicAdmissionError("ADMISSION_RECORD_KIND_MISMATCH")
        for name in (
            "transition_id",
            "complete_verification_root",
            "source_admission_policy_commitment",
            "admission_policy_commitment",
            "prior_state_commitment",
            "next_state_commitment",
            "fence_commitment",
            "prior_admission_root",
        ):
            _require_hash(name, getattr(self, name))
        _require_epoch(self.authority_epoch)
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence <= 0:
            raise AtomicAdmissionError("ADMISSION_SEQUENCE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_ADMISSION_RECORD_V1", asdict(self))


@dataclass(frozen=True)
class AtomicAdmissionStateV1:
    state_commitment: str
    admission_policy_commitment: str
    authority_epoch: int
    fence_commitment: str
    sequence: int
    last_admission_root: str

    def validate(self) -> None:
        for name in (
            "state_commitment",
            "admission_policy_commitment",
            "fence_commitment",
            "last_admission_root",
        ):
            _require_hash(name, getattr(self, name))
        _require_epoch(self.authority_epoch)
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise AtomicAdmissionError("ADMISSION_STATE_SEQUENCE_INVALID")
        if self.sequence == 0 and self.last_admission_root != ZERO_ADMISSION_ROOT:
            raise AtomicAdmissionError("ADMISSION_STATE_GENESIS_ROOT_INVALID")
        if self.sequence > 0 and self.last_admission_root == ZERO_ADMISSION_ROOT:
            raise AtomicAdmissionError("ADMISSION_STATE_CHAIN_ROOT_MISSING")


class LocalSqliteAtomicAdmissionStoreV1:
    """Local SQLite reference for effect-bound atomic canonical-state admission."""

    def __init__(
        self,
        *,
        db_path: str | Path,
        initial_state_commitment: str,
        admission_policy_commitment: str,
        authority_epoch: int,
        fence_commitment: str,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        _require_hash("initial_state_commitment", initial_state_commitment)
        _require_hash("admission_policy_commitment", admission_policy_commitment)
        _require_epoch(authority_epoch)
        _require_hash("fence_commitment", fence_commitment)
        self._fault_injector = fault_injector
        self._initialize(
            initial_state_commitment=initial_state_commitment,
            admission_policy_commitment=admission_policy_commitment,
            authority_epoch=authority_epoch,
            fence_commitment=fence_commitment,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize(
        self,
        *,
        initial_state_commitment: str,
        admission_policy_commitment: str,
        authority_epoch: int,
        fence_commitment: str,
    ) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admission_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    state_commitment TEXT NOT NULL,
                    admission_policy_commitment TEXT NOT NULL,
                    authority_epoch INTEGER NOT NULL,
                    fence_commitment TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    last_admission_root TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admission_records (
                    sequence INTEGER PRIMARY KEY,
                    transition_id TEXT NOT NULL UNIQUE,
                    admission_root TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                )
                """
            )
            row = connection.execute(
                "SELECT * FROM admission_state WHERE singleton = 1"
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO admission_state(
                        singleton, state_commitment, admission_policy_commitment,
                        authority_epoch, fence_commitment, sequence, last_admission_root
                    ) VALUES (1, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        initial_state_commitment,
                        admission_policy_commitment,
                        authority_epoch,
                        fence_commitment,
                        ZERO_ADMISSION_ROOT,
                    ),
                )
            else:
                existing = self._state_from_row(row)
                if (
                    existing.sequence == 0
                    and (
                        existing.state_commitment != initial_state_commitment
                        or existing.admission_policy_commitment != admission_policy_commitment
                        or existing.authority_epoch != authority_epoch
                        or existing.fence_commitment != fence_commitment
                    )
                ):
                    raise AtomicAdmissionError("ADMISSION_STORE_INITIALIZATION_CONFLICT")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _state_from_row(row: sqlite3.Row) -> AtomicAdmissionStateV1:
        state = AtomicAdmissionStateV1(
            state_commitment=str(row["state_commitment"]),
            admission_policy_commitment=str(row["admission_policy_commitment"]),
            authority_epoch=int(row["authority_epoch"]),
            fence_commitment=str(row["fence_commitment"]),
            sequence=int(row["sequence"]),
            last_admission_root=str(row["last_admission_root"]),
        )
        state.validate()
        return state

    def read_state(self) -> AtomicAdmissionStateV1:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM admission_state WHERE singleton = 1"
            ).fetchone()
            if row is None:
                raise AtomicAdmissionError("ADMISSION_STATE_MISSING")
            return self._state_from_row(row)
        finally:
            connection.close()

    def record_count(self) -> int:
        connection = self._connect()
        try:
            row = connection.execute("SELECT COUNT(*) AS n FROM admission_records").fetchone()
            return int(row["n"] if row is not None else 0)
        finally:
            connection.close()

    @staticmethod
    def _require_exact_types(
        *,
        transition: TransitionIdentity,
        decision_receipt: DecisionReceipt,
        execution_receipt: ExecutionReceipt,
        effect_witness: EffectWitness,
        effect_verification: EffectVerificationResult,
        effect_receipt: EffectReceipt,
        complete_verification: CompleteVerificationResult,
    ) -> None:
        values = (
            transition,
            decision_receipt,
            execution_receipt,
            effect_witness,
            effect_verification,
            effect_receipt,
            complete_verification,
        )
        expected = (
            TransitionIdentity,
            DecisionReceipt,
            ExecutionReceipt,
            EffectWitness,
            EffectVerificationResult,
            EffectReceipt,
            CompleteVerificationResult,
        )
        if any(type(value) is not kind for value, kind in zip(values, expected)):
            raise AtomicAdmissionError("ATOMIC_ADMISSION_INPUT_TYPE_MISMATCH")

    def compare_and_admit(
        self,
        *,
        transition: TransitionIdentity,
        decision_receipt: DecisionReceipt,
        execution_receipt: ExecutionReceipt,
        effect_witness: EffectWitness,
        effect_verification: EffectVerificationResult,
        effect_receipt: EffectReceipt,
        complete_verification: CompleteVerificationResult,
        expected_current_state: str,
        expected_policy_commitment: str,
        expected_authority_epoch: int,
        expected_fence_commitment: str,
    ) -> AdmissionRecordV1:
        self._require_exact_types(
            transition=transition,
            decision_receipt=decision_receipt,
            execution_receipt=execution_receipt,
            effect_witness=effect_witness,
            effect_verification=effect_verification,
            effect_receipt=effect_receipt,
            complete_verification=complete_verification,
        )
        for name, value in (
            ("expected_current_state", expected_current_state),
            ("expected_policy_commitment", expected_policy_commitment),
            ("expected_fence_commitment", expected_fence_commitment),
        ):
            _require_hash(name, value)
        _require_epoch(expected_authority_epoch)

        active_policy = uci5_admission_policy_commitment()
        accepted_source_policy = str(
            UCI5_ADMISSION_POLICY_V1["accepted_source_admission_policy_commitment"]
        )
        if transition.admission_policy_commitment != accepted_source_policy:
            raise AtomicAdmissionError("SOURCE_ADMISSION_POLICY_NOT_ACCEPTED")
        if expected_policy_commitment != active_policy:
            raise AtomicAdmissionError("CURRENT_ADMISSION_POLICY_MISMATCH")

        recomputed = CompleteVerifier().verify_complete(
            transition=transition,
            decision_receipt=decision_receipt,
            execution_receipt=execution_receipt,
            effect_witness=effect_witness,
            effect_verification=effect_verification,
            effect_receipt=effect_receipt,
        )
        if recomputed.status != TRUE or any(status != TRUE for _, status in recomputed.obligations):
            raise AtomicAdmissionError("COMPLETE_VERIFICATION_NOT_TRUE")
        if complete_verification.status != TRUE:
            raise AtomicAdmissionError("COMPLETE_VERIFICATION_NOT_TRUE")
        if complete_verification.root != recomputed.root:
            raise AtomicAdmissionError("COMPLETE_VERIFICATION_RECOMPUTE_MISMATCH")
        if recomputed.complete_verifier_policy_commitment != str(
            UCI5_ADMISSION_POLICY_V1["accepted_complete_verifier_policy_commitment"]
        ):
            raise AtomicAdmissionError("COMPLETE_VERIFIER_POLICY_NOT_ACCEPTED")
        if effect_receipt.root != recomputed.effect_receipt_root:
            raise AtomicAdmissionError("EFFECT_RECEIPT_COMPLETE_VERIFICATION_MISMATCH")

        next_state_commitment = effect_receipt.post_state_commitment
        _require_hash("next_state_commitment", next_state_commitment)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")

            duplicate = connection.execute(
                "SELECT 1 FROM admission_records WHERE transition_id = ?",
                (transition.root,),
            ).fetchone()
            if duplicate is not None:
                raise AtomicAdmissionError("DUPLICATE_TRANSITION_ADMISSION")

            row = connection.execute(
                "SELECT * FROM admission_state WHERE singleton = 1"
            ).fetchone()
            if row is None:
                raise AtomicAdmissionError("ADMISSION_STATE_MISSING")
            current = self._state_from_row(row)

            if current.state_commitment != expected_current_state:
                raise AtomicAdmissionError("CURRENT_STATE_MISMATCH")
            if current.admission_policy_commitment != expected_policy_commitment:
                raise AtomicAdmissionError("CURRENT_ADMISSION_POLICY_MISMATCH")
            if current.authority_epoch != expected_authority_epoch:
                raise AtomicAdmissionError("CURRENT_AUTHORITY_EPOCH_MISMATCH")
            if current.fence_commitment != expected_fence_commitment:
                raise AtomicAdmissionError("CURRENT_FENCE_MISMATCH")
            if transition.pre_state_commitment != current.state_commitment:
                raise AtomicAdmissionError("TRANSITION_PRE_STATE_MISMATCH")
            if transition.fence_commitment != current.fence_commitment:
                raise AtomicAdmissionError("TRANSITION_FENCE_MISMATCH")

            sequence = current.sequence + 1
            record = AdmissionRecordV1(
                record_kind=ADMISSION_RECORD_KIND,
                transition_id=transition.root,
                complete_verification_root=recomputed.root,
                source_admission_policy_commitment=transition.admission_policy_commitment,
                admission_policy_commitment=active_policy,
                prior_state_commitment=current.state_commitment,
                next_state_commitment=next_state_commitment,
                authority_epoch=current.authority_epoch,
                fence_commitment=current.fence_commitment,
                sequence=sequence,
                prior_admission_root=current.last_admission_root,
            )
            payload_json = canonical_bytes(asdict(record)).decode("utf-8")
            connection.execute(
                """
                INSERT INTO admission_records(sequence, transition_id, admission_root, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (sequence, record.transition_id, record.root, payload_json),
            )

            if self._fault_injector is not None:
                self._fault_injector("AFTER_RECORD_INSERT")

            cursor = connection.execute(
                """
                UPDATE admission_state
                SET state_commitment = ?, sequence = ?, last_admission_root = ?
                WHERE singleton = 1
                  AND state_commitment = ?
                  AND admission_policy_commitment = ?
                  AND authority_epoch = ?
                  AND fence_commitment = ?
                  AND sequence = ?
                  AND last_admission_root = ?
                """,
                (
                    next_state_commitment,
                    sequence,
                    record.root,
                    current.state_commitment,
                    current.admission_policy_commitment,
                    current.authority_epoch,
                    current.fence_commitment,
                    current.sequence,
                    current.last_admission_root,
                ),
            )
            if cursor.rowcount != 1:
                raise AtomicAdmissionError("ATOMIC_COMPARE_AND_SWAP_FAILED")

            connection.commit()
            return record
        except AtomicAdmissionError:
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise AtomicAdmissionError("ATOMIC_ADMISSION_TRANSACTION_FAILED") from exc
        finally:
            connection.close()
