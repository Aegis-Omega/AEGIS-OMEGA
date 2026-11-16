"""Require TWO actual computations before issuing a bounded finite evidence receipt.

The original AEGIS global receipt replay validates traceability and repeatable
producer behavior; an independent finite Boolean semantic checker recomputes
each model from MHP-derived formal bytes. Neither alone is sufficient for this
explicit dual-evidence result.

Not an authority/admission gate. No claims about natural-language fidelity,
trusted-source deployment or category-theoretic global sections.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from harness.sdk.holon_finite_certificate_checker import (
    CHECK_PASS, IndependentFiniteCertificateCheckerV1,
)
from harness.sdk.holon_finite_global_model import (
    DENIED as GLOBAL_DENIED, SAT, UNSAT,
    FiniteGlobalModelReceiptV1,
    FiniteGlobalReceiptReplayVerifierV1,
)
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash, require_hash

DOMAIN_CHECK = "AEGIS_HOLON_FINITE_DUAL_EVIDENCE_CHECK_V1"
DOMAIN_RECEIPT = "AEGIS_HOLON_FINITE_DUAL_EVIDENCE_RECEIPT_V1"
PASS = "PASS_DUAL_FINITE_EVIDENCE_ONLY"
DENIED = "FAIL_DUAL_FINITE_EVIDENCE_DENIED"


@dataclass(frozen=True)
class DualFiniteEvidenceVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class DualFiniteEvidenceReceiptV1:
    global_receipt_root: str
    problem_root: str
    meaning_receipt_root: str
    global_model_kind: str
    producer_replay_verification_root: str
    independent_semantic_verification_root: str
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-finite-dual-evidence.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOMAIN_RECEIPT, asdict(self))


class DualFiniteEvidenceVerifierV1:
    """Issue a read-only evidence record only after two matching validations.

    Both checks must read back exact original evidence. The producer replay
    and independent calculation have different failure modes, but still share
    provenance, parser and hash dependencies. This does not claim fully
    independent formal kernels or production acceptance.
    """

    def __init__(
        self, *,
        producer_replay: FiniteGlobalReceiptReplayVerifierV1,
        independent: IndependentFiniteCertificateCheckerV1,
    ) -> None:
        self.producer_replay = producer_replay
        self.independent = independent

    def verify(
        self, receipt_root: str
    ) -> tuple[DualFiniteEvidenceVerificationV1, DualFiniteEvidenceReceiptV1 | None]:
        def deny(code: str):
            return DualFiniteEvidenceVerificationV1(DENIED, (code,), None), None

        try:
            require_hash("receipt_root", receipt_root)
        except (ValueError, TypeError):
            return deny("DUAL_RECEIPT_ROOT_INVALID")
        first, original = self.producer_replay.verify(receipt_root)
        if (first.status not in (SAT, UNSAT)
                or not isinstance(original, FiniteGlobalModelReceiptV1)
                or original.root != receipt_root
                or original.authority_class != NO_AUTHORITY):
            return deny("DUAL_PRODUCER_REPLAY_DENIED")
        second, independently_checked = self.independent.verify(receipt_root)
        if (second.status != CHECK_PASS
                or not isinstance(independently_checked, FiniteGlobalModelReceiptV1)
                or independently_checked.root != receipt_root
                or independently_checked.authority_class != NO_AUTHORITY):
            return deny("DUAL_INDEPENDENT_SEMANTICS_DENIED")
        if (independently_checked != original
                or first.verification_root != original.verification_root
                or second.verification_root != original.verification_root
                or original.model_kind != first.status):
            return deny("DUAL_RESULT_IDENTITY_MISMATCH")
        root = canonical_hash(DOMAIN_CHECK, {
            "global_receipt_root": receipt_root,
            "problem_root": original.problem_root,
            "meaning_receipt_root": original.meaning_receipt_root,
            "global_model_kind": original.model_kind,
            "producer_replay_verification_root": first.verification_root,
            "independent_semantic_verification_root": second.verification_root,
            "status": PASS,
        })
        result = DualFiniteEvidenceReceiptV1(
            receipt_root,
            original.problem_root,
            original.meaning_receipt_root,
            original.model_kind,
            first.verification_root,
            second.verification_root,
            root,
        )
        return DualFiniteEvidenceVerificationV1(PASS, (), root), result
