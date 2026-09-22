"""AEGIS Ω Statistical Gödel Machine V1.

This module evaluates self-rewrite proposals but never performs a rewrite.
It is intentionally weaker than a classical Gödel-machine global-optimality
claim: statistical evidence can support bounded improvement, not logical proof
of globally optimal self-modification.

A passing proposal is only ELIGIBLE_FOR_OPERATOR_APPROVAL_ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PASS = "ELIGIBLE_FOR_OPERATOR_APPROVAL_ONLY"
DENY = "DENY"
NO_AUTHORITY = "NONE"

PROTECTED_SURFACES = {
    "OPERATOR_ROOT",
    "AUTHORITY_POLICY",
    "TRUST_ROOTS",
    "SIGNING_ROOTS",
    "EVIDENCE_CLASSIFIER",
    "CLAIM_PROMOTION_POLICY",
}


class RewriteClass(str, Enum):
    FORMAL = "FORMAL"
    STATISTICAL = "STATISTICAL"


@dataclass(frozen=True)
class RewriteProposalV1:
    proposal_id: str
    parent_state_sha256: str
    target_surface: str
    rewrite_class: RewriteClass
    utility_lcb_microunits: int
    semantic_lineage_receipt_sha256: str
    authority_before: str = NO_AUTHORITY
    authority_after: str = NO_AUTHORITY

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise ValueError("PROPOSAL_ID_REQUIRED")
        for value, label in (
            (self.parent_state_sha256, "parent_state_sha256"),
            (self.semantic_lineage_receipt_sha256, "semantic_lineage_receipt_sha256"),
        ):
            if SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{label}: invalid digest")
        if not self.target_surface:
            raise ValueError("TARGET_SURFACE_REQUIRED")
        if type(self.utility_lcb_microunits) is not int:
            raise ValueError("UTILITY_LCB_MUST_BE_INTEGER")
        if self.authority_before != NO_AUTHORITY or self.authority_after != NO_AUTHORITY:
            raise ValueError("SELF_REWRITE_AUTHORITY_EXPANSION_FORBIDDEN")


@dataclass(frozen=True)
class FormalEvidenceV1:
    source_sha256: str
    theorem_receipt_sha256: str
    kernel_verified: bool
    axiom_audit_pass: bool
    sorry_ax_present: bool

    def __post_init__(self) -> None:
        for value, label in (
            (self.source_sha256, "source_sha256"),
            (self.theorem_receipt_sha256, "theorem_receipt_sha256"),
        ):
            if SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{label}: invalid digest")


@dataclass(frozen=True)
class StatisticalEvidenceV1:
    metric_id: str
    sample_count: int
    lower_confidence_bound_microunits: int
    bounded_metric: bool
    independent_verifier: bool
    risk_budget_receipt_sha256: str

    def __post_init__(self) -> None:
        if not self.metric_id:
            raise ValueError("METRIC_ID_REQUIRED")
        if type(self.sample_count) is not int or self.sample_count < 0:
            raise ValueError("INVALID_SAMPLE_COUNT")
        if type(self.lower_confidence_bound_microunits) is not int:
            raise ValueError("LCB_MUST_BE_INTEGER")
        if SHA256_RE.fullmatch(self.risk_budget_receipt_sha256) is None:
            raise ValueError("risk_budget_receipt_sha256: invalid digest")


@dataclass(frozen=True)
class RewriteDecisionV1:
    decision: str
    reason_codes: tuple[str, ...]
    authority_effect: str = NO_AUTHORITY
    automatic_rewrite: bool = False
    global_optimality_claimed: bool = False


def evaluate_rewrite(
    proposal: RewriteProposalV1,
    evidence: FormalEvidenceV1 | StatisticalEvidenceV1,
) -> RewriteDecisionV1:
    reasons: list[str] = []

    def fail(code: str) -> None:
        if code not in reasons:
            reasons.append(code)

    if proposal.target_surface in PROTECTED_SURFACES:
        fail("PROTECTED_SURFACE")
    if proposal.utility_lcb_microunits <= 0:
        fail("NONPOSITIVE_UTILITY_LOWER_BOUND")
    if proposal.authority_before != NO_AUTHORITY or proposal.authority_after != NO_AUTHORITY:
        fail("AUTHORITY_EXPANSION_FORBIDDEN")

    if proposal.rewrite_class == RewriteClass.FORMAL:
        if not isinstance(evidence, FormalEvidenceV1):
            fail("EVIDENCE_CLASS_MISMATCH")
        else:
            if evidence.kernel_verified is not True:
                fail("KERNEL_NOT_VERIFIED")
            if evidence.axiom_audit_pass is not True:
                fail("AXIOM_AUDIT_NOT_PASS")
            if evidence.sorry_ax_present is not False:
                fail("SORRYAX_PRESENT")

    elif proposal.rewrite_class == RewriteClass.STATISTICAL:
        if not isinstance(evidence, StatisticalEvidenceV1):
            fail("EVIDENCE_CLASS_MISMATCH")
        else:
            if evidence.sample_count < 100:
                fail("INSUFFICIENT_SAMPLE_COUNT")
            if evidence.lower_confidence_bound_microunits <= 0:
                fail("STATISTICAL_LCB_NOT_POSITIVE")
            if evidence.lower_confidence_bound_microunits != proposal.utility_lcb_microunits:
                fail("PROPOSAL_EVIDENCE_LCB_MISMATCH")
            if evidence.bounded_metric is not True:
                fail("UNBOUNDED_METRIC")
            if evidence.independent_verifier is not True:
                fail("VERIFIER_NOT_INDEPENDENT")

    else:
        fail("UNSUPPORTED_REWRITE_CLASS")

    return RewriteDecisionV1(
        decision=PASS if not reasons else DENY,
        reason_codes=tuple(reasons),
    )
