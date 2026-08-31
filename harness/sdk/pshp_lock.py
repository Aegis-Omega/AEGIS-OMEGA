"""AEGIS Harness SDK — P_SHP lock evidence controller v1.

The controller proposes an in-memory corpus transition after verification of a
ResidualEntailmentReceiptV2. It does not mutate repository state and does not mint
canonical authority. Every lock record carries ``authority_class == "NONE"``;
consequential admission remains the responsibility of the sovereign execution
plane.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from harness.sdk.residual_entailment_v2 import (
    EvidenceClass,
    IsolationFailureMode,
    ResidualEntailmentReceiptV2,
    ResidualVerifierEngineV2,
)
from harness.sdk.sovereign_execution import canonical_hash

NO_AUTHORITY = "NONE"


@dataclass(frozen=True)
class PSHPLockRecordV1:
    lock_id: str
    predecessor_corpus_digest: str
    successor_corpus_digest: str
    receipt_hash: str
    evidence_class: EvidenceClass
    admitted_residual_digests: Tuple[str, ...]
    manual_acknowledged: bool
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    transition_kind: str = field(default="EVIDENCE_ONLY_PROPOSED_CORPUS_TRANSITION", init=False)
    schema_version: str = "aegis.pshp-lock-record.v1"

    def compute_lock_hash(self) -> str:
        payload = {
            "admitted_residual_digests": list(self.admitted_residual_digests),
            "authority_class": self.authority_class,
            "evidence_class": self.evidence_class.value,
            "lock_id": self.lock_id,
            "manual_acknowledged": self.manual_acknowledged,
            "predecessor_corpus_digest": self.predecessor_corpus_digest,
            "receipt_hash": self.receipt_hash,
            "schema_version": self.schema_version,
            "successor_corpus_digest": self.successor_corpus_digest,
            "transition_kind": self.transition_kind,
        }
        return canonical_hash("PSHP_LOCK_RECORD_V1", payload)


class PSHPLockController:
    def __init__(self, verifier_engine: ResidualVerifierEngineV2):
        self.verifier_engine = verifier_engine

    @staticmethod
    def _deny(current_corpus: Set[str], *errors: str):
        return False, None, set(current_corpus), list(errors)

    def attempt_lock(
        self,
        claim: str,
        current_corpus: Set[str],
        receipt: ResidualEntailmentReceiptV2,
        atom_map: Dict[str, str],
        manual_ack: bool = False,
    ) -> Tuple[bool, Optional[PSHPLockRecordV1], Set[str], List[str]]:
        """Verify evidence and propose ``e -> e'`` without granting authority."""
        if not isinstance(manual_ack, bool):
            return self._deny(current_corpus, "MANUAL_ACK_BOOLEAN_REQUIRED")

        valid, verifier_errors = self.verifier_engine.verify_residual_entailment(
            claim,
            set(current_corpus),
            receipt,
        )
        if not valid:
            return False, None, set(current_corpus), list(verifier_errors)

        if receipt.isolation_failure_mode != IsolationFailureMode.NONE:
            return self._deny(
                current_corpus,
                f"LOCK_DENIED_ISOLATION_FAILURE:{receipt.isolation_failure_mode.value}",
            )

        if receipt.evidence_class == EvidenceClass.ATTESTED and not manual_ack:
            return self._deny(current_corpus, "ATTESTED_MANUAL_ACK_REQUIRED")

        if not receipt.residual_atom_digests:
            return self._deny(current_corpus, "EMPTY_RESIDUAL_SET")

        new_atoms: Set[str] = set()
        for residual_digest in receipt.residual_atom_digests:
            if residual_digest not in atom_map:
                return self._deny(current_corpus, f"MISSING_ATOM_CONTENT:{residual_digest}")
            atom_content = atom_map[residual_digest]
            if canonical_hash("ATOM", atom_content) != residual_digest:
                return self._deny(current_corpus, "ATOM_CONTENT_DIGEST_MISMATCH")
            new_atoms.add(atom_content)

        predecessor = set(current_corpus)
        successor = predecessor.union(new_atoms)
        predecessor_digest = canonical_hash("CORPUS", sorted(predecessor))
        successor_digest = canonical_hash("CORPUS", sorted(successor))
        receipt_hash = receipt.compute_receipt_hash()
        lock_seed = canonical_hash(
            "PSHP_LOCK_ID_V1",
            {
                "predecessor_corpus_digest": predecessor_digest,
                "receipt_hash": receipt_hash,
                "successor_corpus_digest": successor_digest,
            },
        )

        lock_record = PSHPLockRecordV1(
            lock_id=f"lock-{lock_seed[:16]}",
            predecessor_corpus_digest=predecessor_digest,
            successor_corpus_digest=successor_digest,
            receipt_hash=receipt_hash,
            evidence_class=receipt.evidence_class,
            admitted_residual_digests=tuple(sorted(receipt.residual_atom_digests)),
            manual_acknowledged=manual_ack,
        )
        return True, lock_record, successor, []
