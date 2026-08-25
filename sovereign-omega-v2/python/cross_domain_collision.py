"""AEGIS Ω — deterministic integer-first cross-domain collision core."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

import research_invariants as ri


class EvidenceClass(str, Enum):
    EXTERNAL_IDENTIFIER_MATCH = "EXTERNAL_IDENTIFIER_MATCH"
    STANDARD_CODEPOINT_MAPPING = "STANDARD_CODEPOINT_MAPPING"
    DERIVED_PROPERTY = "DERIVED_PROPERTY"


class SelectionProvenance(str, Enum):
    RETROSPECTIVE = "RETROSPECTIVE"
    PROSPECTIVE = "PROSPECTIVE"


@dataclass(frozen=True)
class IntegerSubjectV1:
    value: int
    subject_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("IntegerSubjectV1.value must be an integer")
        object.__setattr__(
            self,
            "subject_sha256",
            ri.sha256_hex({"schema": "AEGIS_INTEGER_SUBJECT_V1", "value": self.value}),
        )

    @property
    def hex_upper(self) -> str:
        return ("-" if self.value < 0 else "") + format(abs(self.value), "X")

    @property
    def unicode_codepoint_label(self) -> str:
        if not 0 <= self.value <= 0x10FFFF:
            raise ValueError("integer is outside Unicode code-point range")
        width = 4 if self.value <= 0xFFFF else 6
        return f"U+{self.value:0{width}X}"


@dataclass(frozen=True)
class TransformSpecV1:
    transform_id: str
    transform_version: str
    input_type: str
    output_type: str
    criterion_text: str
    criterion_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("transform_id", self.transform_id),
            ("transform_version", self.transform_version),
            ("input_type", self.input_type),
            ("output_type", self.output_type),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")
        if not self.criterion_text:
            raise ValueError("criterion_text must be non-empty")
        object.__setattr__(self, "criterion_sha256", ri.literal_sha256(self.criterion_text))


@dataclass(frozen=True)
class RegistrySnapshotV1:
    registry_id: str
    registry_version_or_release: str
    query_key: str
    query_key_type: str
    result_kind: str
    canonical_result: Any
    source_locator: str
    source_observed_at: str
    ingestion_producer_id: str
    content_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("registry_id", self.registry_id),
            ("registry_version_or_release", self.registry_version_or_release),
            ("query_key", self.query_key),
            ("query_key_type", self.query_key_type),
            ("result_kind", self.result_kind),
            ("source_locator", self.source_locator),
            ("source_observed_at", self.source_observed_at),
            ("ingestion_producer_id", self.ingestion_producer_id),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")
        material = {
            "schema": "AEGIS_REGISTRY_SNAPSHOT_V1",
            "registry_id": self.registry_id,
            "registry_version_or_release": self.registry_version_or_release,
            "query_key": self.query_key,
            "query_key_type": self.query_key_type,
            "result_kind": self.result_kind,
            "canonical_result": self.canonical_result,
            "source_locator": self.source_locator,
            "source_observed_at": self.source_observed_at,
            "ingestion_producer_id": self.ingestion_producer_id,
        }
        object.__setattr__(self, "content_sha256", ri.sha256_hex(material))


@dataclass(frozen=True)
class DerivationReceiptV1:
    subject_sha256: str
    derivation_id: str
    derivation_version: str
    criterion_sha256: str
    canonical_result: Any
    evidence_class: EvidenceClass = field(init=False, default=EvidenceClass.DERIVED_PROPERTY)
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        ri._check_digest(self.subject_sha256, "subject_sha256")
        ri._check_digest(self.criterion_sha256, "criterion_sha256")
        if not self.derivation_id or not self.derivation_version:
            raise ValueError("derivation_id and derivation_version must be non-empty")
        material = {
            "schema": "AEGIS_DERIVATION_RECEIPT_V1",
            "subject_sha256": self.subject_sha256,
            "derivation_id": self.derivation_id,
            "derivation_version": self.derivation_version,
            "criterion_sha256": self.criterion_sha256,
            "canonical_result": self.canonical_result,
            "evidence_class": self.evidence_class.value,
        }
        object.__setattr__(self, "receipt_sha256", ri.sha256_hex(material))


@dataclass(frozen=True)
class DomainObservationV1:
    subject_sha256: str
    domain_id: str
    evidence_class: EvidenceClass
    transform_id: str
    transform_criterion_sha256: str
    evidence_artifact_sha256: str
    normalized_claim: str
    observation_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        ri._check_digest(self.subject_sha256, "subject_sha256")
        ri._check_digest(self.transform_criterion_sha256, "transform_criterion_sha256")
        ri._check_digest(self.evidence_artifact_sha256, "evidence_artifact_sha256")
        if not self.domain_id or not self.transform_id or not self.normalized_claim:
            raise ValueError("domain_id, transform_id, and normalized_claim must be non-empty")
        material = {
            "schema": "AEGIS_DOMAIN_OBSERVATION_V1",
            "subject_sha256": self.subject_sha256,
            "domain_id": self.domain_id,
            "evidence_class": self.evidence_class.value,
            "transform_id": self.transform_id,
            "transform_criterion_sha256": self.transform_criterion_sha256,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "normalized_claim": self.normalized_claim,
        }
        object.__setattr__(self, "observation_sha256", ri.sha256_hex(material))


@dataclass(frozen=True)
class CollisionCriterionV1:
    universe_min: int
    universe_max: int
    registry_set: tuple[str, ...]
    transform_set: tuple[str, ...]
    independence_rule_id: str
    score_function_id: str
    control_generator_id: str
    control_seed: int
    control_count: int
    promotion_threshold: float | None
    criterion_text: str
    criterion_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.universe_min > self.universe_max:
            raise ValueError("universe_min must not exceed universe_max")
        if self.control_count <= 0:
            raise ValueError("control_count must be positive")
        if len(set(self.registry_set)) != len(self.registry_set):
            raise ValueError("registry_set must contain unique ids")
        if len(set(self.transform_set)) != len(self.transform_set):
            raise ValueError("transform_set must contain unique ids")
        if any(not value for value in self.registry_set + self.transform_set):
            raise ValueError("registry and transform ids must be non-empty")
        for name, value in (
            ("independence_rule_id", self.independence_rule_id),
            ("score_function_id", self.score_function_id),
            ("control_generator_id", self.control_generator_id),
            ("criterion_text", self.criterion_text),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")
        if self.promotion_threshold is not None and not 0.0 <= self.promotion_threshold <= 1.0:
            raise ValueError("promotion_threshold must lie in [0, 1]")
        material = {
            "schema": "AEGIS_COLLISION_CRITERION_V1",
            "universe_min": self.universe_min,
            "universe_max": self.universe_max,
            "registry_set": self.registry_set,
            "transform_set": self.transform_set,
            "independence_rule_id": self.independence_rule_id,
            "score_function_id": self.score_function_id,
            "control_generator_id": self.control_generator_id,
            "control_seed": self.control_seed,
            "control_count": self.control_count,
            "promotion_threshold": self.promotion_threshold,
            "criterion_text": self.criterion_text,
        }
        object.__setattr__(self, "criterion_sha256", ri.sha256_hex(material))


@dataclass(frozen=True)
class CollisionReceiptV1:
    subject_sha256: str
    provenance: SelectionProvenance
    observation_sha256s: tuple[str, ...]
    criterion_sha256: str
    independent_external_domains: tuple[str, ...]
    independent_external_domain_count: int
    score: int
    cross_registry_collision: bool
    receipt_sha256: str


def evaluate_collision(
    subject: IntegerSubjectV1,
    provenance: SelectionProvenance,
    observations: Sequence[DomainObservationV1],
    criterion: CollisionCriterionV1,
) -> CollisionReceiptV1:
    """Evaluate only the frozen V1 domain-independence/score contract."""
    if not criterion.universe_min <= subject.value <= criterion.universe_max:
        raise ValueError("subject is outside the frozen criterion universe")
    if criterion.independence_rule_id != "UNIQUE_DOMAIN_ID_V1":
        raise ValueError("unsupported independence rule")
    if criterion.score_function_id != "UNIQUE_EXTERNAL_DOMAINS_V1":
        raise ValueError("unsupported score function")

    external_classes = {
        EvidenceClass.EXTERNAL_IDENTIFIER_MATCH,
        EvidenceClass.STANDARD_CODEPOINT_MAPPING,
    }
    external_domains: set[str] = set()
    observation_digests: list[str] = []
    for observation in observations:
        if observation.subject_sha256 != subject.subject_sha256:
            raise ValueError("observation subject digest mismatch")
        if observation.transform_id not in criterion.transform_set:
            raise ValueError(f"transform not frozen in criterion: {observation.transform_id}")
        if observation.evidence_class in external_classes:
            if observation.domain_id not in criterion.registry_set:
                raise ValueError(f"external domain not frozen in criterion: {observation.domain_id}")
            external_domains.add(observation.domain_id)
        observation_digests.append(observation.observation_sha256)

    domains = tuple(sorted(external_domains))
    digests = tuple(sorted(observation_digests))
    count = len(domains)
    score = count
    collision = count >= 2
    material = {
        "schema": "AEGIS_COLLISION_RECEIPT_V1",
        "subject_sha256": subject.subject_sha256,
        "provenance": provenance.value,
        "observation_sha256s": digests,
        "criterion_sha256": criterion.criterion_sha256,
        "independent_external_domains": domains,
        "independent_external_domain_count": count,
        "score": score,
        "cross_registry_collision": collision,
    }
    return CollisionReceiptV1(
        subject_sha256=subject.subject_sha256,
        provenance=provenance,
        observation_sha256s=digests,
        criterion_sha256=criterion.criterion_sha256,
        independent_external_domains=domains,
        independent_external_domain_count=count,
        score=score,
        cross_registry_collision=collision,
        receipt_sha256=ri.sha256_hex(material),
    )


def generate_controls(criterion: CollisionCriterionV1) -> tuple[int, ...]:
    if criterion.control_generator_id != "PY_RANDOM_UNIFORM_INT_V1":
        raise ValueError("unsupported control generator")
    rng = random.Random(criterion.control_seed)
    return tuple(
        rng.randint(criterion.universe_min, criterion.universe_max)
        for _ in range(criterion.control_count)
    )


@dataclass(frozen=True)
class NullModelReceiptV1:
    subject_sha256: str
    collision_receipt_sha256: str
    criterion_sha256: str
    observed_score: int
    control_scores_sha256: str
    control_count: int
    extreme_count: int
    p_emp: float
    promotion_eligible: bool
    null_survived: bool | None
    receipt_sha256: str


def evaluate_null_model(
    observed: CollisionReceiptV1,
    criterion: CollisionCriterionV1,
    control_scores: Sequence[int],
    *,
    allow_retrospective_descriptive: bool = False,
) -> NullModelReceiptV1:
    if observed.criterion_sha256 != criterion.criterion_sha256:
        raise ValueError("collision receipt criterion mismatch")
    if len(control_scores) != criterion.control_count:
        raise ValueError("control score count differs from frozen criterion")
    scores = tuple(control_scores)
    if any(isinstance(score, bool) or not isinstance(score, int) or score < 0 for score in scores):
        raise ValueError("control scores must be non-negative integers")
    if observed.provenance is SelectionProvenance.RETROSPECTIVE and not allow_retrospective_descriptive:
        raise PermissionError("retrospective observations are not promotion-eligible")

    extreme = sum(1 for score in scores if score >= observed.score)
    p_emp = (1 + extreme) / (1 + len(scores))
    promotion_eligible = observed.provenance is SelectionProvenance.PROSPECTIVE
    if not promotion_eligible or criterion.promotion_threshold is None:
        null_survived: bool | None = None
    else:
        null_survived = p_emp <= criterion.promotion_threshold

    scores_sha256 = ri.sha256_hex(scores)
    material = {
        "schema": "AEGIS_NULL_MODEL_RECEIPT_V1",
        "subject_sha256": observed.subject_sha256,
        "collision_receipt_sha256": observed.receipt_sha256,
        "criterion_sha256": criterion.criterion_sha256,
        "observed_score": observed.score,
        "control_scores_sha256": scores_sha256,
        "control_count": len(scores),
        "extreme_count": extreme,
        "p_emp": p_emp,
        "promotion_eligible": promotion_eligible,
        "null_survived": null_survived,
    }
    return NullModelReceiptV1(
        subject_sha256=observed.subject_sha256,
        collision_receipt_sha256=observed.receipt_sha256,
        criterion_sha256=criterion.criterion_sha256,
        observed_score=observed.score,
        control_scores_sha256=scores_sha256,
        control_count=len(scores),
        extreme_count=extreme,
        p_emp=p_emp,
        promotion_eligible=promotion_eligible,
        null_survived=null_survived,
        receipt_sha256=ri.sha256_hex(material),
    )
