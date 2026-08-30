"""Deterministic, provenance-bound cross-provider memory synthesis.

Provider outputs are untrusted memory records.  This module can group exact
normalized statements, expose common provenance roots, and preserve explicit
contradictions.  It cannot verify a proposition or grant authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Mapping

from harness.sdk.sovereign_execution import canonical_hash


EVIDENCE_ONLY = "EVIDENCE_ONLY"
ZERO_HASH = "0" * 64
UNKNOWN = "UNKNOWN"
REJECTED = "REJECTED"
QUARANTINED = "QUARANTINED"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+#=-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
AUTHORITY_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4}
CLAIM_KINDS = {
    "OBSERVATION",
    "EXTERNAL_CLAIM",
    "DERIVATION",
    "HYPOTHESIS",
    "PREDICTION",
    "VALIDATED",
    "REFUTED",
}
CANDIDATE_CLAIM_KINDS = {
    "EXTERNAL_CLAIM",
    "DERIVATION",
    "HYPOTHESIS",
    "PREDICTION",
}
PROMPT_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard instructions",
    "system prompt",
    "developer message",
    "approve this claim",
    "<system",
)
MAX_RECORDS = 64
MAX_ID_CHARS = 128
MAX_SUBJECT_BYTES = 16_384
MAX_STATEMENT_BYTES = 16_384
MAX_SOURCE_ARTIFACTS = 32
MAX_PROVENANCE_ROOTS = 32
MAX_SOURCE_ARTIFACT_BYTES = 2_048
MAX_SEQUENCE = (1 << 63) - 1
MEMORY_REQUEST_FIELDS = {
    "event_id",
    "idempotency_key",
    "subject",
    "sequence",
    "records",
    "requested_authority",
    # The live boundary ignores and overwrites this compatibility field.
    "requester_root",
}
MEMORY_RECORD_FIELDS = {
    "record_id",
    "provider_id",
    "model_id",
    "statement",
    "claim_kind",
    "source_artifacts",
    "provenance_roots",
    "provider_output_root",
    "confidence_bps",
    "correlated_failure_group",
    "authority",
    "epistemic_tier",
    "status",
    "contradicts_record_ids",
}


class CrossProviderMemoryError(ValueError):
    """Fail-closed schema/validation error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _string_tuple(value: Any, code: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CrossProviderMemoryError(code)
    return tuple(value)


@dataclass(frozen=True)
class ProviderMemoryRecordV1:
    record_id: str
    provider_id: str
    model_id: str
    statement: str
    claim_kind: str
    source_artifacts: tuple[str, ...]
    provenance_roots: tuple[str, ...]
    provider_output_root: str
    confidence_bps: int
    correlated_failure_group: str
    authority: str = EVIDENCE_ONLY
    epistemic_tier: str = "T2"
    status: str = "CANDIDATE"
    contradicts_record_ids: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProviderMemoryRecordV1":
        if not isinstance(payload, Mapping):
            raise CrossProviderMemoryError("MEMORY_RECORD_SCHEMA_INVALID")
        if set(payload) - MEMORY_RECORD_FIELDS:
            raise CrossProviderMemoryError("MEMORY_RECORD_UNKNOWN_FIELD")
        try:
            return cls(
                record_id=payload["record_id"],
                provider_id=payload["provider_id"],
                model_id=payload["model_id"],
                statement=payload["statement"],
                claim_kind=payload.get("claim_kind", "HYPOTHESIS"),
                source_artifacts=_string_tuple(
                    payload.get("source_artifacts"), "SOURCE_ARTIFACTS_INVALID"
                ),
                provenance_roots=_string_tuple(
                    payload.get("provenance_roots"), "PROVENANCE_ROOTS_INVALID"
                ),
                provider_output_root=payload["provider_output_root"],
                confidence_bps=payload.get("confidence_bps", 0),
                correlated_failure_group=payload.get(
                    "correlated_failure_group", "unknown"
                ),
                authority=payload.get("authority", EVIDENCE_ONLY),
                epistemic_tier=payload.get("epistemic_tier", "T2"),
                status=payload.get("status", "CANDIDATE"),
                contradicts_record_ids=_string_tuple(
                    payload.get("contradicts_record_ids", []),
                    "CONTRADICTION_REFS_INVALID",
                ),
            )
        except (KeyError, TypeError) as exc:
            raise CrossProviderMemoryError("MEMORY_RECORD_SCHEMA_INVALID") from exc


@dataclass(frozen=True)
class CrossProviderMemoryRequestV1:
    event_id: str
    idempotency_key: str
    subject: str
    sequence: int
    records: tuple[ProviderMemoryRecordV1, ...]
    requested_authority: str = "D1"
    requester_root: str = ZERO_HASH

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CrossProviderMemoryRequestV1":
        if not isinstance(payload, Mapping):
            raise CrossProviderMemoryError("MEMORY_REQUEST_SCHEMA_INVALID")
        if set(payload) - MEMORY_REQUEST_FIELDS:
            raise CrossProviderMemoryError("MEMORY_REQUEST_UNKNOWN_FIELD")
        records = payload.get("records")
        if not isinstance(records, list):
            raise CrossProviderMemoryError("MEMORY_RECORDS_INVALID")
        try:
            event_id = payload["event_id"]
            return cls(
                event_id=event_id,
                idempotency_key=payload.get("idempotency_key", event_id),
                subject=payload["subject"],
                sequence=payload["sequence"],
                records=tuple(ProviderMemoryRecordV1.from_mapping(item) for item in records),
                requested_authority=payload.get("requested_authority", "D1"),
            )
        except (KeyError, TypeError) as exc:
            raise CrossProviderMemoryError("MEMORY_REQUEST_SCHEMA_INVALID") from exc


@dataclass(frozen=True)
class CrossProviderCandidateClaimV1:
    claim_id: str
    statement: str
    claim_kind: str
    input_record_ids: tuple[str, ...]
    provider_ids: tuple[str, ...]
    model_ids: tuple[str, ...]
    source_artifacts: tuple[str, ...]
    provenance_roots: tuple[str, ...]
    provider_output_roots: tuple[str, ...]
    correlated_failure_groups: tuple[str, ...]
    provider_count: int
    independent_root_count: int
    reported_confidence_min_bps: int
    reported_confidence_max_bps: int
    confidence_basis: str = "PROVIDER_SELF_REPORTS_NOT_AGGREGATED"
    epistemic_tier: str = "T2"
    status: str = "CANDIDATE"
    authority: str = EVIDENCE_ONLY


@dataclass(frozen=True)
class CrossProviderContradictionV1:
    contradiction_id: str
    left_record_id: str
    right_record_id: str
    left_claim_id: str
    right_claim_id: str
    edge_kind: str = "EXPLICIT_PROVIDER_RECORD_CONTRADICTION"
    status: str = "UNRESOLVED"
    authority: str = EVIDENCE_ONLY


@dataclass(frozen=True)
class CrossProviderSynthesisResultV1:
    knowledge_decision: str
    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    candidate_claims: tuple[CrossProviderCandidateClaimV1, ...]
    contradictions: tuple[CrossProviderContradictionV1, ...]
    provider_count: int
    model_count: int
    record_count: int
    unique_provenance_root_count: int
    common_root_collapse_count: int


@dataclass(frozen=True)
class CrossProviderMemoryReceiptV1:
    schema_version: str
    synthesis_id: str
    event_id: str
    request_digest: str
    subject: str
    sequence: int
    knowledge_decision: str
    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    candidate_claims: tuple[CrossProviderCandidateClaimV1, ...]
    contradictions: tuple[CrossProviderContradictionV1, ...]
    provider_count: int
    model_count: int
    record_count: int
    unique_provenance_root_count: int
    common_root_collapse_count: int
    event_log_root: str
    authority_before: str
    authority_after: str
    requester_root: str
    self_model: dict[str, Any]
    bundle_digest: str

    def __post_init__(self) -> None:
        if self.knowledge_decision not in {UNKNOWN, REJECTED, QUARANTINED}:
            raise CrossProviderMemoryError("MEMORY_KNOWLEDGE_DECISION_INVALID")
        if self.authority_before != self.authority_after:
            raise CrossProviderMemoryError("AUTHORITY_CHANGED")
        if any(claim.status != "CANDIDATE" for claim in self.candidate_claims):
            raise CrossProviderMemoryError("MEMORY_CLAIM_STATUS_INVALID")
        if any(claim.epistemic_tier != "T2" for claim in self.candidate_claims):
            raise CrossProviderMemoryError("MEMORY_CLAIM_TIER_INVALID")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CrossProviderMemoryReceiptV1":
        values = dict(payload)
        values.setdefault("common_root_collapse_count", 0)
        values["reason_codes"] = tuple(values.get("reason_codes", ()))
        values["warnings"] = tuple(values.get("warnings", ()))
        values["candidate_claims"] = tuple(
            CrossProviderCandidateClaimV1(
                **{
                    **item,
                    "input_record_ids": tuple(item.get("input_record_ids", ())),
                    "provider_ids": tuple(item.get("provider_ids", ())),
                    "model_ids": tuple(item.get("model_ids", ())),
                    "source_artifacts": tuple(item.get("source_artifacts", ())),
                    "provenance_roots": tuple(item.get("provenance_roots", ())),
                    "provider_output_roots": tuple(item.get("provider_output_roots", ())),
                    "correlated_failure_groups": tuple(
                        item.get("correlated_failure_groups", ())
                    ),
                }
            )
            for item in values.get("candidate_claims", ())
        )
        values["contradictions"] = tuple(
            CrossProviderContradictionV1(**item)
            for item in values.get("contradictions", ())
        )
        values["self_model"] = dict(values.get("self_model", {}))
        return cls(**values)


@dataclass(frozen=True)
class CrossProviderMemoryReplayV1:
    synthesis_id: str
    integrity_verified: bool
    lineage_verified: bool
    semantic_truth_proven: bool
    bundle_digest: str
    reason_codes: tuple[str, ...]


def _safe_id(name: str, value: Any) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_ID_CHARS
        or not SAFE_ID_RE.fullmatch(value)
    ):
        raise CrossProviderMemoryError(f"{name}_INVALID")


def validate_request(request: CrossProviderMemoryRequestV1) -> None:
    _safe_id("MEMORY_EVENT_ID", request.event_id)
    _safe_id("MEMORY_IDEMPOTENCY_KEY", request.idempotency_key)
    if not isinstance(request.subject, str) or not request.subject.strip():
        raise CrossProviderMemoryError("MEMORY_SUBJECT_REQUIRED")
    if len(request.subject.encode("utf-8")) > MAX_SUBJECT_BYTES:
        raise CrossProviderMemoryError("MEMORY_SUBJECT_TOO_LARGE")
    if (
        isinstance(request.sequence, bool)
        or not isinstance(request.sequence, int)
        or not 1 <= request.sequence <= MAX_SEQUENCE
    ):
        raise CrossProviderMemoryError("MEMORY_SEQUENCE_INVALID")
    if request.requested_authority not in AUTHORITY_ORDER:
        raise CrossProviderMemoryError("REQUESTED_AUTHORITY_INVALID")
    if not isinstance(request.requester_root, str) or not SHA256_RE.fullmatch(
        request.requester_root
    ):
        raise CrossProviderMemoryError("REQUESTER_ROOT_INVALID")
    if not 1 <= len(request.records) <= MAX_RECORDS:
        raise CrossProviderMemoryError("MEMORY_RECORD_COUNT_INVALID")

    record_ids: set[str] = set()
    for record in request.records:
        for name, value in (
            ("MEMORY_RECORD_ID", record.record_id),
            ("MEMORY_PROVIDER_ID", record.provider_id),
            ("MEMORY_MODEL_ID", record.model_id),
            ("CORRELATED_FAILURE_GROUP", record.correlated_failure_group),
        ):
            _safe_id(name, value)
        if record.record_id in record_ids:
            raise CrossProviderMemoryError("DUPLICATE_MEMORY_RECORD_ID")
        record_ids.add(record.record_id)
        if not isinstance(record.statement, str) or not record.statement.strip():
            raise CrossProviderMemoryError("MEMORY_STATEMENT_REQUIRED")
        if len(record.statement.encode("utf-8")) > MAX_STATEMENT_BYTES:
            raise CrossProviderMemoryError("MEMORY_STATEMENT_TOO_LARGE")
        if record.claim_kind not in CLAIM_KINDS:
            raise CrossProviderMemoryError("MEMORY_CLAIM_KIND_INVALID")
        if not 1 <= len(record.source_artifacts) <= MAX_SOURCE_ARTIFACTS:
            raise CrossProviderMemoryError("SOURCE_ARTIFACT_COUNT_INVALID")
        if any(
            not artifact.strip()
            or "\x00" in artifact
            or len(artifact.encode("utf-8")) > MAX_SOURCE_ARTIFACT_BYTES
            for artifact in record.source_artifacts
        ):
            raise CrossProviderMemoryError("SOURCE_ARTIFACT_INVALID")
        if not 1 <= len(record.provenance_roots) <= MAX_PROVENANCE_ROOTS:
            raise CrossProviderMemoryError("PROVENANCE_ROOT_COUNT_INVALID")
        if any(not SHA256_RE.fullmatch(root) for root in record.provenance_roots):
            raise CrossProviderMemoryError("PROVENANCE_ROOT_INVALID")
        if not isinstance(record.provider_output_root, str) or not SHA256_RE.fullmatch(
            record.provider_output_root
        ):
            raise CrossProviderMemoryError("PROVIDER_OUTPUT_ROOT_INVALID")
        if (
            isinstance(record.confidence_bps, bool)
            or not isinstance(record.confidence_bps, int)
            or not 0 <= record.confidence_bps <= 10_000
        ):
            raise CrossProviderMemoryError("MEMORY_CONFIDENCE_INVALID")
        if not all(SAFE_ID_RE.fullmatch(item) for item in record.contradicts_record_ids):
            raise CrossProviderMemoryError("CONTRADICTION_REF_INVALID")
        if record.record_id in record.contradicts_record_ids:
            raise CrossProviderMemoryError("SELF_CONTRADICTION_REF_INVALID")

    for record in request.records:
        if any(item not in record_ids for item in record.contradicts_record_ids):
            raise CrossProviderMemoryError("CONTRADICTION_REF_UNKNOWN")


def request_digest(request: CrossProviderMemoryRequestV1) -> str:
    from dataclasses import asdict

    return canonical_hash("AEGIS_CROSS_PROVIDER_MEMORY_REQUEST_V1", asdict(request))


def _normalize_statement(statement: str) -> str:
    return unicodedata.normalize("NFKC", " ".join(statement.split())).casefold()


def _common_root_collapse_count(
    records: tuple[ProviderMemoryRecordV1, ...],
) -> int:
    providers_by_statement_root: dict[tuple[str, str], set[str]] = {}
    for record in records:
        normalized = _normalize_statement(record.statement)
        for root in set(record.provenance_roots):
            providers_by_statement_root.setdefault((normalized, root), set()).add(
                record.provider_id
            )
    return sum(
        max(0, len(providers) - 1)
        for providers in providers_by_statement_root.values()
    )


def synthesize(
    request: CrossProviderMemoryRequestV1,
    *,
    authority_ceiling: str,
) -> CrossProviderSynthesisResultV1:
    """Group records deterministically without inferring truth or equivalence."""
    validate_request(request)
    if authority_ceiling not in AUTHORITY_ORDER:
        raise CrossProviderMemoryError("AUTHORITY_CEILING_INVALID")

    common_root_collapse_count = _common_root_collapse_count(request.records)

    if AUTHORITY_ORDER[request.requested_authority] > AUTHORITY_ORDER[authority_ceiling]:
        return CrossProviderSynthesisResultV1(
            knowledge_decision=REJECTED,
            reason_codes=("AUTHORITY_ESCALATION_DENIED",),
            warnings=(),
            candidate_claims=(),
            contradictions=(),
            provider_count=len({record.provider_id for record in request.records}),
            model_count=len(
                {(record.provider_id, record.model_id) for record in request.records}
            ),
            record_count=len(request.records),
            unique_provenance_root_count=len(
                {root for record in request.records for root in record.provenance_roots}
            ),
            common_root_collapse_count=common_root_collapse_count,
        )

    warnings: list[str] = []
    reasons: list[str] = []
    output_root_owners: dict[str, set[str]] = {}
    for record in request.records:
        output_root_owners.setdefault(record.provider_output_root, set()).add(
            record.record_id
        )
    generated_output_roots = set(output_root_owners)
    dependency_graph: dict[str, set[str]] = {
        record.record_id: set() for record in request.records
    }
    generated_root_used = False
    for record in request.records:
        for root in record.provenance_roots:
            owners = output_root_owners.get(root, set())
            if owners:
                generated_root_used = True
                dependency_graph[record.record_id].update(owners)
    if generated_root_used:
        reasons.append("GENERATED_MEMORY_USED_AS_EVIDENCE_ROOT")

    visiting: set[str] = set()
    visited: set[str] = set()

    def _has_cycle(record_id: str) -> bool:
        if record_id in visiting:
            return True
        if record_id in visited:
            return False
        visiting.add(record_id)
        for dependency in dependency_graph[record_id]:
            if _has_cycle(dependency):
                return True
        visiting.remove(record_id)
        visited.add(record_id)
        return False

    if any(_has_cycle(record_id) for record_id in sorted(dependency_graph)):
        reasons.append("PROVENANCE_CYCLE_REJECTED")

    groups: dict[str, list[ProviderMemoryRecordV1]] = {}
    for record in sorted(request.records, key=lambda item: item.record_id):
        groups.setdefault(_normalize_statement(record.statement), []).append(record)
        if len(set(record.provenance_roots)) != len(record.provenance_roots):
            warnings.append("DUPLICATE_EVIDENCE_DEDUPLICATED")
        if record.authority != EVIDENCE_ONLY:
            reasons.append("PROVIDER_MEMORY_AUTHORITY_CLAIM_REJECTED")
        if record.epistemic_tier != "T2":
            reasons.append("PROVIDER_TIER_CLAIM_NOT_ADMITTED")
        if record.status != "CANDIDATE":
            reasons.append("PROVIDER_STATUS_CLAIM_NOT_ADMITTED")
        if record.claim_kind not in CANDIDATE_CLAIM_KINDS:
            reasons.append("PROVIDER_CLAIM_KIND_NOT_ADMITTED")
        lowered = record.statement.casefold()
        if any(marker in lowered for marker in PROMPT_INJECTION_MARKERS):
            reasons.append("PROMPT_INJECTION_CONTENT_DETECTED")

    output_roots = [record.provider_output_root for record in request.records]
    if len(set(output_roots)) != len(output_roots):
        warnings.append("DUPLICATE_PROVIDER_OUTPUT_ROOT")

    candidates: list[CrossProviderCandidateClaimV1] = []
    record_to_claim: dict[str, str] = {}
    for normalized, records in sorted(groups.items()):
        record_ids = tuple(sorted(record.record_id for record in records))
        providers = tuple(sorted({record.provider_id for record in records}))
        models = tuple(
            sorted({f"{record.provider_id}:{record.model_id}" for record in records})
        )
        roots = tuple(
            sorted({root for record in records for root in record.provenance_roots})
        )
        source_artifacts = tuple(
            sorted(
                {artifact for record in records for artifact in record.source_artifacts}
            )
        )
        provider_output_roots = tuple(
            sorted({record.provider_output_root for record in records})
        )
        failure_groups = tuple(
            sorted({record.correlated_failure_group for record in records})
        )
        claim_kinds = {record.claim_kind for record in records}
        claim_kind = (
            next(iter(claim_kinds))
            if len(claim_kinds) == 1 and claim_kinds <= CANDIDATE_CLAIM_KINDS
            else "EXTERNAL_CLAIM"
        )
        if len(claim_kinds) > 1:
            warnings.append("CLAIM_KIND_DISAGREEMENT_NOT_RESOLVED")
        statement = min(" ".join(record.statement.split()) for record in records)
        claim_id = "claim-" + canonical_hash(
            "AEGIS_CROSS_PROVIDER_CANDIDATE_CLAIM_V1",
            {
                "subject": request.subject.strip(),
                "normalized_statement": normalized,
                "record_ids": record_ids,
                "provenance_roots": roots,
            },
        )[:24]
        for record_id in record_ids:
            record_to_claim[record_id] = claim_id
        candidates.append(
            CrossProviderCandidateClaimV1(
                claim_id=claim_id,
                statement=statement,
                claim_kind=claim_kind,
                input_record_ids=record_ids,
                provider_ids=providers,
                model_ids=models,
                source_artifacts=source_artifacts,
                provenance_roots=roots,
                provider_output_roots=provider_output_roots,
                correlated_failure_groups=failure_groups,
                provider_count=len(providers),
                independent_root_count=len(
                    set(roots) - generated_output_roots
                ),
                reported_confidence_min_bps=min(
                    record.confidence_bps for record in records
                ),
                reported_confidence_max_bps=max(
                    record.confidence_bps for record in records
                ),
            )
        )
        providers_by_root: dict[str, set[str]] = {}
        for record in records:
            for root in record.provenance_roots:
                providers_by_root.setdefault(root, set()).add(record.provider_id)
        if any(len(root_providers) > 1 for root_providers in providers_by_root.values()):
            warnings.append("COMMON_PROVENANCE_ROOT_NOT_INDEPENDENT")
        provider_by_group: dict[str, set[str]] = {}
        for record in records:
            provider_by_group.setdefault(record.correlated_failure_group, set()).add(
                record.provider_id
            )
        if any(len(group_providers) > 1 for group_providers in provider_by_group.values()):
            warnings.append("CORRELATED_PROVIDER_AGREEMENT")

    contradiction_pairs: set[tuple[str, str]] = set()
    for record in request.records:
        for other in record.contradicts_record_ids:
            contradiction_pairs.add(tuple(sorted((record.record_id, other))))
    contradictions = tuple(
        CrossProviderContradictionV1(
            contradiction_id="contradiction-"
            + canonical_hash(
                "AEGIS_CROSS_PROVIDER_CONTRADICTION_V1",
                {"left_record_id": left, "right_record_id": right},
            )[:24],
            left_record_id=left,
            right_record_id=right,
            left_claim_id=record_to_claim[left],
            right_claim_id=record_to_claim[right],
        )
        for left, right in sorted(contradiction_pairs)
    )
    if contradictions:
        reasons.append("MEMORY_CONTRADICTION_UNRESOLVED")
    provider_count = len({record.provider_id for record in request.records})
    if provider_count < 2:
        reasons.append("PROVIDER_DIVERSITY_INSUFFICIENT")

    quarantine_reasons = {
        "GENERATED_MEMORY_USED_AS_EVIDENCE_ROOT",
        "PROVENANCE_CYCLE_REJECTED",
        "PROVIDER_MEMORY_AUTHORITY_CLAIM_REJECTED",
        "PROVIDER_TIER_CLAIM_NOT_ADMITTED",
        "PROVIDER_STATUS_CLAIM_NOT_ADMITTED",
        "PROVIDER_CLAIM_KIND_NOT_ADMITTED",
        "PROMPT_INJECTION_CONTENT_DETECTED",
        "MEMORY_CONTRADICTION_UNRESOLVED",
    }
    unsafe = any(reason in quarantine_reasons for reason in reasons)
    reasons.append("SYNTHESIS_REQUIRES_VERIFICATION")
    decision = QUARANTINED if unsafe else UNKNOWN
    return CrossProviderSynthesisResultV1(
        knowledge_decision=decision,
        reason_codes=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
        candidate_claims=tuple(candidates),
        contradictions=contradictions,
        provider_count=provider_count,
        model_count=len(
            {(record.provider_id, record.model_id) for record in request.records}
        ),
        record_count=len(request.records),
        unique_provenance_root_count=len(
            {root for record in request.records for root in record.provenance_roots}
        ),
        common_root_collapse_count=common_root_collapse_count,
    )
