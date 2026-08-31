"""AEGIS Harness SDK — residual entailment evidence kernel v2.

Implements exact discrete subtraction, mutual-dependency isolation, retry-chain
binding, and dual evidence classes. This module is evidence-only: receipts carry
``authority_class == "NONE"`` and cannot grant canonical admission or execution.

The repository's canonical ``harness.sdk.sovereign_execution.canonical_hash`` is
reused rather than redefining a parallel hashing scheme. ``timestamp_utc`` is
observational metadata and is deliberately excluded from deterministic receipt
roots, matching the sovereign execution invariant for timestamps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

from harness.sdk.sovereign_execution import canonical_hash

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NO_AUTHORITY = "NONE"


class EvidenceClass(str, Enum):
    DERIVED = "DERIVED"
    ATTESTED = "ATTESTED"


class IsolationFailureMode(str, Enum):
    NONE = "NONE"
    MUTUAL_DEPENDENCY_DETECTED = "MUTUAL_DEPENDENCY_DETECTED"
    CIRCULAR_CONTEXT_LEAK = "CIRCULAR_CONTEXT_LEAK"


def _require_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{name}:INVALID_SHA256")


def _require_nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}:EMPTY")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name}:CONTROL_CHARACTER")


def _callable_identity(func: Callable[..., object]) -> dict[str, str]:
    return {
        "module": getattr(func, "__module__", "<unknown>"),
        "qualname": getattr(func, "__qualname__", getattr(func, "__name__", "<unknown>")),
    }


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class WitnessVote:
    judge_id: str
    vote: bool
    raw_response_digest: str
    signature: str

    def __post_init__(self) -> None:
        _require_nonempty("judge_id", self.judge_id)
        if not isinstance(self.vote, bool):
            raise ValueError("vote:BOOLEAN_REQUIRED")
        _require_sha256("raw_response_digest", self.raw_response_digest)
        _require_sha256("signature", self.signature)

    def to_dict(self) -> Dict[str, object]:
        return {
            "judge_id": self.judge_id,
            "raw_response_digest": self.raw_response_digest,
            "signature": self.signature,
            "vote": self.vote,
        }


@dataclass(frozen=True)
class PerAtomVerdict:
    atom_digest: str
    atom_content: str
    entailed_by_corpus_alone: bool
    entailed_by_corpus_plus_residual: bool
    evaluator_signature: str
    evaluator_signature_pass2: str
    witness_votes_pass1: Tuple[WitnessVote, ...] = ()
    witness_votes_pass2: Tuple[WitnessVote, ...] = ()

    def __post_init__(self) -> None:
        _require_sha256("atom_digest", self.atom_digest)
        _require_nonempty("atom_content", self.atom_content)
        if not isinstance(self.entailed_by_corpus_alone, bool):
            raise ValueError("entailed_by_corpus_alone:BOOLEAN_REQUIRED")
        if not isinstance(self.entailed_by_corpus_plus_residual, bool):
            raise ValueError("entailed_by_corpus_plus_residual:BOOLEAN_REQUIRED")
        _require_sha256("evaluator_signature", self.evaluator_signature)
        _require_sha256("evaluator_signature_pass2", self.evaluator_signature_pass2)

    def is_strictly_novel(self) -> bool:
        return (not self.entailed_by_corpus_alone) and (not self.entailed_by_corpus_plus_residual)

    def to_dict(self) -> Dict[str, object]:
        return {
            "atom_content": self.atom_content,
            "atom_digest": self.atom_digest,
            "entailed_by_corpus_alone": self.entailed_by_corpus_alone,
            "entailed_by_corpus_plus_residual": self.entailed_by_corpus_plus_residual,
            "evaluator_signature": self.evaluator_signature,
            "evaluator_signature_pass2": self.evaluator_signature_pass2,
            "witness_votes_pass1": [vote.to_dict() for vote in self.witness_votes_pass1],
            "witness_votes_pass2": [vote.to_dict() for vote in self.witness_votes_pass2],
        }


@dataclass(frozen=True)
class QuorumConfig:
    required_n: int
    total_m: int

    def __post_init__(self) -> None:
        if isinstance(self.required_n, bool) or not isinstance(self.required_n, int):
            raise ValueError("required_n:INTEGER_REQUIRED")
        if isinstance(self.total_m, bool) or not isinstance(self.total_m, int):
            raise ValueError("total_m:INTEGER_REQUIRED")
        if self.required_n <= 0 or self.total_m <= 0 or self.required_n > self.total_m:
            raise ValueError("QUORUM_CONFIG_INVALID")

    def is_satisfied(self, votes: Tuple[WitnessVote, ...], expected_outcome: bool) -> bool:
        if len(votes) != self.total_m:
            return False
        if len({vote.judge_id for vote in votes}) != self.total_m:
            return False
        matching = sum(1 for vote in votes if vote.vote == expected_outcome)
        return matching >= self.required_n

    def to_dict(self) -> Dict[str, int]:
        return {"required_n": self.required_n, "total_m": self.total_m}


@dataclass(frozen=True)
class ResidualEntailmentReceiptV2:
    claim_digest: str
    claim_atom_digests: Tuple[str, ...]
    corpus_snapshot_digest: str
    atomizer_contract_digest: str
    evidence_class: EvidenceClass
    per_atom_verdicts: Tuple[PerAtomVerdict, ...]
    entailed_atom_digests: Tuple[str, ...]
    residual_atom_digests: Tuple[str, ...]
    residual_digest: str
    isolation_failure_mode: IsolationFailureMode
    quorum_config: Optional[QuorumConfig]
    attempt_index: int
    previous_attempt_sha256: Optional[str]
    verifier_binding: str
    timestamp_utc: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.residual-entailment-receipt.v2"

    def __post_init__(self) -> None:
        for name in (
            "claim_digest",
            "corpus_snapshot_digest",
            "atomizer_contract_digest",
            "residual_digest",
            "verifier_binding",
        ):
            _require_sha256(name, getattr(self, name))
        for digest in self.claim_atom_digests:
            _require_sha256("claim_atom_digest", digest)
        for digest in self.entailed_atom_digests:
            _require_sha256("entailed_atom_digest", digest)
        for digest in self.residual_atom_digests:
            _require_sha256("residual_atom_digest", digest)
        if isinstance(self.attempt_index, bool) or not isinstance(self.attempt_index, int):
            raise ValueError("attempt_index:INTEGER_REQUIRED")
        if self.previous_attempt_sha256 is not None:
            _require_sha256("previous_attempt_sha256", self.previous_attempt_sha256)
        _require_nonempty("timestamp_utc", self.timestamp_utc)

    def compute_receipt_hash(self) -> str:
        payload = {
            "atomizer_contract_digest": self.atomizer_contract_digest,
            "attempt_index": self.attempt_index,
            "authority_class": self.authority_class,
            "claim_atom_digests": list(self.claim_atom_digests),
            "claim_digest": self.claim_digest,
            "corpus_snapshot_digest": self.corpus_snapshot_digest,
            "entailed_atom_digests": list(self.entailed_atom_digests),
            "evidence_class": self.evidence_class.value,
            "isolation_failure_mode": self.isolation_failure_mode.value,
            "per_atom_verdicts": [verdict.to_dict() for verdict in self.per_atom_verdicts],
            "previous_attempt_sha256": self.previous_attempt_sha256,
            "quorum_config": self.quorum_config.to_dict() if self.quorum_config else None,
            "residual_atom_digests": list(self.residual_atom_digests),
            "residual_digest": self.residual_digest,
            "schema_version": self.schema_version,
            "verifier_binding": self.verifier_binding,
        }
        return canonical_hash("RESIDUAL_ENTAILMENT_RECEIPT_V2", payload)


EvaluatorReturnType = Tuple[bool, str, List[WitnessVote]]


class ResidualVerifierEngineV2:
    def __init__(
        self,
        atomizer: Callable[[str], List[str]],
        atomizer_contract_digest: str,
        entailment_evaluator: Callable[[str, Set[str]], EvaluatorReturnType],
        evidence_class: EvidenceClass,
        quorum_config: Optional[QuorumConfig] = None,
        history_lock_roots: Optional[Set[str]] = None,
        evaluator_contract_digest: Optional[str] = None,
    ):
        if not isinstance(evidence_class, EvidenceClass):
            raise ValueError("evidence_class:INVALID")
        _require_sha256("atomizer_contract_digest", atomizer_contract_digest)
        if evidence_class == EvidenceClass.ATTESTED and quorum_config is None:
            raise ValueError("ATTESTED evidence class requires an explicit QuorumConfig.")
        if evidence_class == EvidenceClass.DERIVED and quorum_config is not None:
            raise ValueError("DERIVED evidence class cannot carry QuorumConfig.")

        self.atomizer = atomizer
        self.atomizer_contract_digest = atomizer_contract_digest
        self.entailment_evaluator = entailment_evaluator
        self.evidence_class = evidence_class
        self.quorum_config = quorum_config
        self.history_lock_roots = set(history_lock_roots or set())
        for root in self.history_lock_roots:
            _require_sha256("history_lock_root", root)

        if evaluator_contract_digest is None:
            evaluator_contract_digest = canonical_hash(
                "RESIDUAL_EVALUATOR_CALLABLE_ID_V2",
                _callable_identity(entailment_evaluator),
            )
        _require_sha256("evaluator_contract_digest", evaluator_contract_digest)
        self.evaluator_contract_digest = evaluator_contract_digest
        self.verifier_binding = canonical_hash(
            "RESIDUAL_VERIFIER_CONFIG_V2",
            {
                "atomizer_contract_digest": self.atomizer_contract_digest,
                "evaluator_contract_digest": self.evaluator_contract_digest,
                "evidence_class": self.evidence_class.value,
                "quorum_config": self.quorum_config.to_dict() if self.quorum_config else None,
                "schema_version": "aegis.residual-verifier.v2",
            },
        )

    @staticmethod
    def _raise_duplicate_atoms(raw_atoms: List[str], atom_digests: List[str]) -> None:
        if len(raw_atoms) != len(set(atom_digests)):
            raise ValueError("DUPLICATE_ATOMS")

    @staticmethod
    def _merge_failure(
        current: IsolationFailureMode,
        new: IsolationFailureMode,
    ) -> IsolationFailureMode:
        priority = {
            IsolationFailureMode.NONE: 0,
            IsolationFailureMode.MUTUAL_DEPENDENCY_DETECTED: 1,
            IsolationFailureMode.CIRCULAR_CONTEXT_LEAK: 2,
        }
        return new if priority[new] > priority[current] else current

    def _classify_verdicts(
        self,
        verdicts: Tuple[PerAtomVerdict, ...],
    ) -> tuple[Tuple[str, ...], Tuple[str, ...], IsolationFailureMode]:
        entailed: List[str] = []
        residual: List[str] = []
        failure = IsolationFailureMode.NONE

        for verdict in verdicts:
            if verdict.is_strictly_novel():
                if verdict.atom_digest in self.history_lock_roots:
                    failure = self._merge_failure(failure, IsolationFailureMode.CIRCULAR_CONTEXT_LEAK)
                    entailed.append(verdict.atom_digest)
                else:
                    residual.append(verdict.atom_digest)
            else:
                entailed.append(verdict.atom_digest)
                if (not verdict.entailed_by_corpus_alone) and verdict.entailed_by_corpus_plus_residual:
                    failure = self._merge_failure(
                        failure,
                        IsolationFailureMode.MUTUAL_DEPENDENCY_DETECTED,
                    )

        return tuple(sorted(entailed)), tuple(sorted(residual)), failure

    def execute_subtraction(
        self,
        claim: str,
        corpus: Set[str],
        attempt_index: int = 0,
        previous_attempt_sha256: Optional[str] = None,
        timestamp_utc: Optional[str] = None,
    ) -> ResidualEntailmentReceiptV2:
        _require_nonempty("claim", claim)
        if isinstance(attempt_index, bool) or not isinstance(attempt_index, int) or attempt_index < 0:
            raise ValueError("ATTEMPT_INDEX_INVALID")
        if attempt_index == 0 and previous_attempt_sha256 is not None:
            raise ValueError("PREVIOUS_ATTEMPT_UNEXPECTED")
        if attempt_index > 0:
            if previous_attempt_sha256 is None or not SHA256_RE.fullmatch(previous_attempt_sha256):
                raise ValueError("PREVIOUS_ATTEMPT_SHA256_INVALID")

        raw_atoms = self.atomizer(claim)
        if not raw_atoms:
            raise ValueError("ATOMIZATION_EMPTY")
        for atom in raw_atoms:
            _require_nonempty("atom", atom)
        atom_digests = [canonical_hash("ATOM", atom) for atom in raw_atoms]
        self._raise_duplicate_atoms(raw_atoms, atom_digests)
        atom_map = dict(zip(atom_digests, raw_atoms))
        sorted_atom_digests = sorted(atom_digests)

        claim_digest = canonical_hash("CLAIM", claim)
        corpus_snapshot_digest = canonical_hash("CORPUS", sorted(corpus))

        pass1_results: Dict[str, EvaluatorReturnType] = {}
        first_pass_novel_digests: Set[str] = set()

        for atom_digest in sorted_atom_digests:
            atom_text = atom_map[atom_digest]
            entailed, evaluator_signature, votes = self.entailment_evaluator(atom_text, set(corpus))
            if not isinstance(entailed, bool):
                raise ValueError("EVALUATOR_OUTCOME_BOOLEAN_REQUIRED")
            _require_sha256("evaluator_signature", evaluator_signature)
            pass1_results[atom_digest] = (entailed, evaluator_signature, list(votes))
            if not entailed:
                first_pass_novel_digests.add(atom_digest)

        verdicts: List[PerAtomVerdict] = []
        for atom_digest in sorted_atom_digests:
            atom_text = atom_map[atom_digest]
            entailed_pass1, signature_pass1, votes_pass1 = pass1_results[atom_digest]
            other_novel_atoms = {
                atom_map[digest]
                for digest in first_pass_novel_digests
                if digest != atom_digest
            }
            augmented_corpus = set(corpus).union(other_novel_atoms)
            entailed_pass2, signature_pass2, votes_pass2 = self.entailment_evaluator(
                atom_text,
                augmented_corpus,
            )
            if not isinstance(entailed_pass2, bool):
                raise ValueError("EVALUATOR_OUTCOME_BOOLEAN_REQUIRED")
            _require_sha256("evaluator_signature_pass2", signature_pass2)

            verdicts.append(
                PerAtomVerdict(
                    atom_digest=atom_digest,
                    atom_content=atom_text,
                    entailed_by_corpus_alone=entailed_pass1,
                    entailed_by_corpus_plus_residual=entailed_pass2,
                    evaluator_signature=signature_pass1,
                    evaluator_signature_pass2=signature_pass2,
                    witness_votes_pass1=tuple(votes_pass1),
                    witness_votes_pass2=tuple(votes_pass2),
                )
            )

        verdict_tuple = tuple(verdicts)
        entailed_digests, residual_digests, isolation_failure = self._classify_verdicts(verdict_tuple)
        residual_digest = canonical_hash("RESIDUAL_SET", list(residual_digests))

        return ResidualEntailmentReceiptV2(
            claim_digest=claim_digest,
            claim_atom_digests=tuple(sorted_atom_digests),
            corpus_snapshot_digest=corpus_snapshot_digest,
            atomizer_contract_digest=self.atomizer_contract_digest,
            evidence_class=self.evidence_class,
            per_atom_verdicts=verdict_tuple,
            entailed_atom_digests=entailed_digests,
            residual_atom_digests=residual_digests,
            residual_digest=residual_digest,
            isolation_failure_mode=isolation_failure,
            quorum_config=self.quorum_config,
            attempt_index=attempt_index,
            previous_attempt_sha256=previous_attempt_sha256,
            verifier_binding=self.verifier_binding,
            timestamp_utc=timestamp_utc or _now_utc(),
        )

    @staticmethod
    def _verify_vote_token(vote: WitnessVote) -> bool:
        """Verify the deterministic v2 witness integrity token.

        This is not a public-key signature scheme. Deployments claiming external
        cryptographic attestation must wrap/replace this boundary with a trusted
        key registry and signature verifier; the receipt itself does not mint that
        trust merely from a SHA-256 token.
        """
        expected = canonical_hash(
            "WITNESS_SIG",
            {
                "judge_id": vote.judge_id,
                "raw_response_digest": vote.raw_response_digest,
                "vote": vote.vote,
            },
        )
        return vote.signature == expected

    def _verify_quorum_votes(
        self,
        votes: Tuple[WitnessVote, ...],
        expected_outcome: bool,
        atom_digest: str,
        pass_index: int,
        errors: List[str],
    ) -> None:
        assert self.quorum_config is not None
        if len(votes) != self.quorum_config.total_m:
            errors.append(f"QUORUM_TOTAL_M_MISMATCH:{pass_index}:{atom_digest}")
        if len({vote.judge_id for vote in votes}) != len(votes):
            errors.append(f"QUORUM_DISTINCT_JUDGES_REQUIRED:{pass_index}:{atom_digest}")
        if not self.quorum_config.is_satisfied(votes, expected_outcome):
            errors.append(f"QUORUM_THRESHOLD_FAILURE:{pass_index}:{atom_digest}")
        for vote in votes:
            if not self._verify_vote_token(vote):
                errors.append(f"WITNESS_TOKEN_INVALID:{pass_index}:{atom_digest}:{vote.judge_id}")

    def verify_residual_entailment(
        self,
        claim: str,
        corpus: Set[str],
        receipt: ResidualEntailmentReceiptV2,
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if canonical_hash("CLAIM", claim) != receipt.claim_digest:
            errors.append("CLAIM_DIGEST_MISMATCH")
        if canonical_hash("CORPUS", sorted(corpus)) != receipt.corpus_snapshot_digest:
            errors.append("CORPUS_SNAPSHOT_DIGEST_MISMATCH")
        if receipt.atomizer_contract_digest != self.atomizer_contract_digest:
            errors.append("ATOMIZER_CONTRACT_MISMATCH")
        if receipt.evidence_class != self.evidence_class:
            errors.append("EVIDENCE_CLASS_MISMATCH")
        if receipt.verifier_binding != self.verifier_binding:
            errors.append("VERIFIER_BINDING_MISMATCH")
        if receipt.authority_class != NO_AUTHORITY:
            errors.append("AUTHORITY_CLASS_VIOLATION")

        if receipt.attempt_index < 0:
            errors.append("ATTEMPT_INDEX_INVALID")
        elif receipt.attempt_index == 0:
            if receipt.previous_attempt_sha256 is not None:
                errors.append("PREVIOUS_ATTEMPT_UNEXPECTED")
        else:
            if receipt.previous_attempt_sha256 is None or not SHA256_RE.fullmatch(receipt.previous_attempt_sha256):
                errors.append("PREVIOUS_ATTEMPT_SHA256_INVALID")

        recomputed_atoms = self.atomizer(claim)
        recomputed_atom_digests = [canonical_hash("ATOM", atom) for atom in recomputed_atoms]
        if len(recomputed_atoms) != len(set(recomputed_atom_digests)):
            errors.append("DUPLICATE_ATOMS")
        expected_atom_digests = tuple(sorted(recomputed_atom_digests))
        if expected_atom_digests != receipt.claim_atom_digests:
            errors.append("ATOMIZATION_MISMATCH")

        verdict_digests = tuple(verdict.atom_digest for verdict in receipt.per_atom_verdicts)
        if verdict_digests != tuple(sorted(verdict_digests)):
            errors.append("PER_ATOM_ORDER_MISMATCH")
        if verdict_digests != receipt.claim_atom_digests:
            errors.append("PER_ATOM_COVERAGE_MISMATCH")

        atom_map = {canonical_hash("ATOM", atom): atom for atom in recomputed_atoms}
        for verdict in receipt.per_atom_verdicts:
            if canonical_hash("ATOM", verdict.atom_content) != verdict.atom_digest:
                errors.append(f"ATOM_CONTENT_DIGEST_MISMATCH:{verdict.atom_digest}")
            expected_content = atom_map.get(verdict.atom_digest)
            if expected_content is None or expected_content != verdict.atom_content:
                errors.append(f"ATOM_CONTENT_BINDING_MISMATCH:{verdict.atom_digest}")

        expected_entailed, expected_residual, expected_failure = self._classify_verdicts(
            receipt.per_atom_verdicts
        )
        if expected_entailed != receipt.entailed_atom_digests:
            errors.append("ENTAILED_CLASSIFICATION_MISMATCH")
        if expected_residual != receipt.residual_atom_digests:
            errors.append("RESIDUAL_CLASSIFICATION_MISMATCH")
        if set(receipt.entailed_atom_digests).intersection(receipt.residual_atom_digests):
            errors.append("ATOM_PARTITION_OVERLAP")
        if set(receipt.entailed_atom_digests).union(receipt.residual_atom_digests) != set(receipt.claim_atom_digests):
            errors.append("ATOM_PARTITION_INCOMPLETE")
        if canonical_hash("RESIDUAL_SET", list(receipt.residual_atom_digests)) != receipt.residual_digest:
            errors.append("RESIDUAL_DIGEST_MISMATCH")
        if expected_failure != receipt.isolation_failure_mode:
            errors.append("ISOLATION_FAILURE_MODE_MISMATCH")
        if receipt.isolation_failure_mode != IsolationFailureMode.NONE:
            errors.append(f"ISOLATION_FAULT:{receipt.isolation_failure_mode.value}")

        if receipt.evidence_class == EvidenceClass.DERIVED:
            if receipt.quorum_config is not None:
                errors.append("DERIVED_QUORUM_FORBIDDEN")
            try:
                fresh_receipt = self.execute_subtraction(
                    claim=claim,
                    corpus=set(corpus),
                    attempt_index=receipt.attempt_index,
                    previous_attempt_sha256=receipt.previous_attempt_sha256,
                    timestamp_utc=receipt.timestamp_utc,
                )
            except ValueError as exc:
                errors.append(f"DERIVED_REEXECUTION_ERROR:{exc}")
            else:
                if fresh_receipt.compute_receipt_hash() != receipt.compute_receipt_hash():
                    errors.append("DERIVED_REEXECUTION_HASH_MISMATCH")

        elif receipt.evidence_class == EvidenceClass.ATTESTED:
            if receipt.quorum_config is None:
                errors.append("ATTESTATION_QUORUM_MISSING")
            elif self.quorum_config is None or receipt.quorum_config != self.quorum_config:
                errors.append("ATTESTATION_QUORUM_CONFIG_MISMATCH")
            else:
                for verdict in receipt.per_atom_verdicts:
                    self._verify_quorum_votes(
                        verdict.witness_votes_pass1,
                        verdict.entailed_by_corpus_alone,
                        verdict.atom_digest,
                        1,
                        errors,
                    )
                    self._verify_quorum_votes(
                        verdict.witness_votes_pass2,
                        verdict.entailed_by_corpus_plus_residual,
                        verdict.atom_digest,
                        2,
                        errors,
                    )

        return len(errors) == 0, sorted(set(errors))
