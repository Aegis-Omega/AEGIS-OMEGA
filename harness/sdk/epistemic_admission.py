from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ClaimStatus(str, Enum):
    VERIFIED = "VERIFIED"
    DERIVED = "DERIVED"
    ATTESTED = "ATTESTED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    NOT_CHECKED = "NOT_CHECKED"


class FieldProvenance(str, Enum):
    DECLARED = "DECLARED"
    DERIVED = "DERIVED"
    ATTESTED = "ATTESTED"
    VERIFIED = "VERIFIED"


class Route(str, Enum):
    SERVE = "SERVE"
    REVIEW = "REVIEW"
    QUARANTINE = "QUARANTINE"


class FailureLocus(str, Enum):
    NARRATOR = "NARRATOR"
    ADMISSION_POLICY = "ADMISSION_POLICY"
    PROVENANCE_SYSTEM = "PROVENANCE_SYSTEM"
    CONTENT_VERIFIER = "CONTENT_VERIFIER"
    CITATION_ENTAILMENT_FAILURE = "CITATION_ENTAILMENT_FAILURE"
    ENFORCEMENT = "ENFORCEMENT"
    ENUMERATION_PROCEDURE = "ENUMERATION_PROCEDURE"
    SUBJECT_BINDING = "SUBJECT_BINDING"
    NONE_ESTABLISHED = "NONE_ESTABLISHED"


@dataclass(frozen=True)
class SubjectBindingV1:
    subject_type: str
    subject_id: str


@dataclass(frozen=True)
class LoadBearingFieldV1:
    name: str
    value: Any
    load_bearing: bool
    provenance: FieldProvenance


@dataclass(frozen=True)
class SourceBindingV1:
    source_id: str
    provenance_integrity: bool | None
    entails_claim: bool | None


@dataclass(frozen=True)
class RetrievalObservationV1:
    query: str
    found: bool
    asserted_outcome: str


@dataclass(frozen=True)
class EpistemicClaimV1:
    claim_id: str
    claim_text: str
    status: ClaimStatus
    subject: SubjectBindingV1
    authority_scope: str
    evidence_window: str
    load_bearing_fields: list[LoadBearingFieldV1] = field(default_factory=list)
    sources: list[SourceBindingV1] = field(default_factory=list)
    retrieval_observations: list[RetrievalObservationV1] = field(default_factory=list)
    verification_complete: bool = False
    historically_valid: bool | None = None
    enumeration_complete: bool = True
    authorship_resolved: bool = True


@dataclass(frozen=True)
class AdmissionDecisionV1:
    route: Route
    claim_id: str
    subject_match: bool
    violations: tuple[str, ...]
    failure_loci: tuple[FailureLocus, ...]
    current_applicability: bool
    historically_valid: bool | None


def _append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def evaluate_claim(
    claim: EpistemicClaimV1,
    *,
    current_subject_sha: str | None = None,
) -> AdmissionDecisionV1:
    """Evaluate one claim deterministically.

    This executes admission-policy checks only. The result is evidence about those
    checks and never grants effect or production admission authority.
    """
    quarantine: list[str] = []
    review: list[str] = []
    loci: list[FailureLocus] = []

    subject_match = (
        current_subject_sha is None
        or claim.subject.subject_type != "git_commit"
        or claim.subject.subject_id == current_subject_sha
    )
    current_applicability = subject_match

    if not subject_match:
        quarantine.append("EXACT_SUBJECT_MISMATCH")
        _append_unique(loci, FailureLocus.SUBJECT_BINDING)

    for item in claim.load_bearing_fields:
        if item.load_bearing and item.provenance is FieldProvenance.DECLARED:
            quarantine.append(f"DECLARED_LOAD_BEARING_FIELD:{item.name}")
            _append_unique(loci, FailureLocus.ADMISSION_POLICY)

    for source in claim.sources:
        if source.provenance_integrity is False:
            quarantine.append(f"SOURCE_PROVENANCE_FAILED:{source.source_id}")
            _append_unique(loci, FailureLocus.PROVENANCE_SYSTEM)
        elif source.provenance_integrity is None:
            review.append(f"SOURCE_PROVENANCE_UNRESOLVED:{source.source_id}")
            _append_unique(loci, FailureLocus.PROVENANCE_SYSTEM)

        if source.entails_claim is False:
            quarantine.append(f"SOURCE_DOES_NOT_ENTAIL_CLAIM:{source.source_id}")
            _append_unique(loci, FailureLocus.CITATION_ENTAILMENT_FAILURE)
        elif source.entails_claim is None:
            review.append(f"SOURCE_ENTAILMENT_UNRESOLVED:{source.source_id}")
            _append_unique(loci, FailureLocus.CITATION_ENTAILMENT_FAILURE)

    for observation in claim.retrieval_observations:
        if not observation.found and observation.asserted_outcome.upper() == "NONEXISTENT":
            quarantine.append(f"SEARCH_MISS_ESCALATED_TO_NONEXISTENCE:{observation.query}")
            _append_unique(loci, FailureLocus.CONTENT_VERIFIER)

    if not claim.enumeration_complete:
        review.append("ENUMERATION_INCOMPLETE")
        _append_unique(loci, FailureLocus.ENUMERATION_PROCEDURE)

    if not claim.authorship_resolved and any(f.load_bearing for f in claim.load_bearing_fields):
        quarantine.append("UNRESOLVED_AUTHORSHIP_FOR_LOAD_BEARING_INPUT")
        _append_unique(loci, FailureLocus.PROVENANCE_SYSTEM)

    if not claim.verification_complete:
        review.append("VERIFICATION_INCOMPLETE")
        _append_unique(loci, FailureLocus.CONTENT_VERIFIER)

    if claim.status in {ClaimStatus.INFERRED, ClaimStatus.ASSUMED, ClaimStatus.NOT_CHECKED}:
        review.append(f"NON_VERIFIED_STATUS:{claim.status.value}")

    if quarantine:
        route = Route.QUARANTINE
        violations = tuple(quarantine + review)
    elif review:
        route = Route.REVIEW
        violations = tuple(review)
    else:
        route = Route.SERVE
        violations = ()

    if not loci:
        loci = [FailureLocus.NONE_ESTABLISHED]

    return AdmissionDecisionV1(
        route=route,
        claim_id=claim.claim_id,
        subject_match=subject_match,
        violations=violations,
        failure_loci=tuple(loci),
        current_applicability=current_applicability,
        historically_valid=claim.historically_valid,
    )
