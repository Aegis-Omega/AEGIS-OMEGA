"""AEGIS Ω — deterministic integer-first cross-domain collision core."""

from __future__ import annotations

import json
import pathlib
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


def _expected_query_key(subject: IntegerSubjectV1, transform: TransformSpecV1) -> str:
    if transform.transform_id == "INTEGER_TO_UNICODE_CODEPOINT_V1":
        return subject.unicode_codepoint_label
    if transform.transform_id == "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1":
        return str(subject.value)
    raise ValueError(f"unsupported external snapshot transform: {transform.transform_id}")


def verify_snapshot_observation(
    *,
    subject: IntegerSubjectV1,
    snapshot: RegistrySnapshotV1,
    transform: TransformSpecV1,
    evidence_class: EvidenceClass,
    normalized_claim: str,
) -> DomainObservationV1:
    """Verify the subject→query-key relation before minting an observation."""
    if evidence_class is EvidenceClass.DERIVED_PROPERTY:
        raise ValueError("external snapshot cannot be classified as DERIVED_PROPERTY")
    expected_key = _expected_query_key(subject, transform)
    if snapshot.query_key != expected_key:
        raise ValueError("snapshot query key does not match transformed subject")
    if transform.transform_id == "INTEGER_TO_UNICODE_CODEPOINT_V1":
        if snapshot.query_key_type != "unicode-codepoint":
            raise ValueError("Unicode transform requires unicode-codepoint query key type")
        if isinstance(snapshot.canonical_result, Mapping):
            result_codepoint = snapshot.canonical_result.get("codepoint")
            if result_codepoint is not None and result_codepoint != expected_key:
                raise ValueError("Unicode result codepoint does not match query key")
    return DomainObservationV1(
        subject_sha256=subject.subject_sha256,
        domain_id=snapshot.registry_id,
        evidence_class=evidence_class,
        transform_id=transform.transform_id,
        transform_criterion_sha256=transform.criterion_sha256,
        evidence_artifact_sha256=snapshot.content_sha256,
        normalized_claim=normalized_claim,
    )


@dataclass(frozen=True)
class FixtureReplayV1:
    subject: IntegerSubjectV1
    provenance: SelectionProvenance
    snapshots: tuple[RegistrySnapshotV1, ...]
    derivations: tuple[DerivationReceiptV1, ...]
    observations: tuple[DomainObservationV1, ...]
    criterion: CollisionCriterionV1
    collision: CollisionReceiptV1
    status_history: tuple[ri.StatusTransitionV1, ...]

    @property
    def current_status(self) -> str | None:
        return self.status_history[-1].next_status if self.status_history else None


def load_fixture_bundle(path: str | pathlib.Path) -> Mapping[str, Any]:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("fixture root must be an object")
    if data.get("schema") != "AEGIS_CROSS_DOMAIN_FIXTURE_V1":
        raise ValueError("unsupported fixture schema")
    return data


def append_collision_status(
    journal: ri.StatusJournalV1,
    next_status: str,
    evidence_receipt_digests: Sequence[str],
    criterion_sha256: str,
    reason: str,
    *,
    null_receipt: NullModelReceiptV1 | None = None,
) -> ri.StatusTransitionV1:
    if next_status == "STRUCTURAL_RELATION":
        raise PermissionError("collision statistics cannot mint STRUCTURAL_RELATION")
    allowed = {
        None: {"OBSERVED"},
        "OBSERVED": {"EXACT_MAPPING"},
        "EXACT_MAPPING": {"CROSS_REGISTRY_COLLISION"},
        "CROSS_REGISTRY_COLLISION": {"NULL_SURVIVED"},
        "NULL_SURVIVED": {"REPLICATED"},
    }
    if next_status not in allowed.get(journal.current_status, set()):
        raise PermissionError(
            f"inadmissible collision status transition: {journal.current_status!r} -> {next_status!r}"
        )
    if next_status == "NULL_SURVIVED":
        if null_receipt is None:
            raise PermissionError("NULL_SURVIVED requires a null-model receipt")
        if null_receipt.criterion_sha256 != criterion_sha256:
            raise PermissionError("null-model receipt criterion mismatch")
        if not null_receipt.promotion_eligible or null_receipt.null_survived is not True:
            raise PermissionError("null-model receipt is not promotion-eligible and surviving")
    return journal.append(
        next_status=next_status,
        evidence_receipt_digests=evidence_receipt_digests,
        criterion_sha256=criterion_sha256,
        reason=reason,
    )


def replay_fixture_bundle(path: str | pathlib.Path) -> FixtureReplayV1:
    data = load_fixture_bundle(path)
    subject_data = data.get("subject")
    if not isinstance(subject_data, Mapping):
        raise ValueError("fixture subject must be an object")
    subject = IntegerSubjectV1(subject_data["value"])
    provenance = SelectionProvenance(subject_data["provenance"])

    expected = data.get("expected_representations")
    if not isinstance(expected, Mapping):
        raise ValueError("fixture expected_representations must be an object")
    if expected.get("hex_upper") != subject.hex_upper:
        raise ValueError("fixture hexadecimal representation mismatch")
    if expected.get("unicode_codepoint_label") != subject.unicode_codepoint_label:
        raise ValueError("fixture Unicode code-point representation mismatch")

    snapshots: list[RegistrySnapshotV1] = []
    observations: list[DomainObservationV1] = []
    for entry in data.get("external_snapshots", []):
        if not isinstance(entry, Mapping):
            raise ValueError("external snapshot entry must be an object")
        snapshot = RegistrySnapshotV1(
            registry_id=entry["registry_id"],
            registry_version_or_release=entry["registry_version_or_release"],
            query_key=entry["query_key"],
            query_key_type=entry["query_key_type"],
            result_kind=entry["result_kind"],
            canonical_result=entry["canonical_result"],
            source_locator=entry["source_locator"],
            source_observed_at=entry["source_observed_at"],
            ingestion_producer_id=entry["ingestion_producer_id"],
        )
        transform_data = entry["transform"]
        transform = TransformSpecV1(
            transform_id=transform_data["transform_id"],
            transform_version=transform_data["transform_version"],
            input_type=transform_data["input_type"],
            output_type=transform_data["output_type"],
            criterion_text=transform_data["criterion_text"],
        )
        observation = verify_snapshot_observation(
            subject=subject,
            snapshot=snapshot,
            transform=transform,
            evidence_class=EvidenceClass(entry["evidence_class"]),
            normalized_claim=entry["normalized_claim"],
        )
        snapshots.append(snapshot)
        observations.append(observation)

    derivations: list[DerivationReceiptV1] = []
    for entry in data.get("local_derivations", []):
        criterion_sha = ri.literal_sha256(entry["criterion_text"])
        derivation = DerivationReceiptV1(
            subject_sha256=subject.subject_sha256,
            derivation_id=entry["derivation_id"],
            derivation_version=entry["derivation_version"],
            criterion_sha256=criterion_sha,
            canonical_result=entry["canonical_result"],
        )
        derivations.append(derivation)
        observations.append(
            DomainObservationV1(
                subject_sha256=subject.subject_sha256,
                domain_id="number-theory",
                evidence_class=EvidenceClass.DERIVED_PROPERTY,
                transform_id=entry["derivation_id"],
                transform_criterion_sha256=criterion_sha,
                evidence_artifact_sha256=derivation.receipt_sha256,
                normalized_claim=f"local derivation {entry['derivation_id']}",
            )
        )

    criterion_data = data.get("collision_criterion")
    if not isinstance(criterion_data, Mapping):
        raise ValueError("fixture collision_criterion must be an object")
    criterion = CollisionCriterionV1(
        universe_min=criterion_data["universe_min"],
        universe_max=criterion_data["universe_max"],
        registry_set=tuple(criterion_data["registry_set"]),
        transform_set=tuple(criterion_data["transform_set"]),
        independence_rule_id=criterion_data["independence_rule_id"],
        score_function_id=criterion_data["score_function_id"],
        control_generator_id=criterion_data["control_generator_id"],
        control_seed=criterion_data["control_seed"],
        control_count=criterion_data["control_count"],
        promotion_threshold=criterion_data["promotion_threshold"],
        criterion_text=criterion_data["criterion_text"],
    )
    collision = evaluate_collision(subject, provenance, observations, criterion)

    journal = ri.StatusJournalV1(f"cross-domain:{subject.subject_sha256}")
    append_collision_status(
        journal,
        "OBSERVED",
        [collision.receipt_sha256],
        criterion.criterion_sha256,
        "frozen integer observation replayed",
    )
    append_collision_status(
        journal,
        "EXACT_MAPPING",
        [s.content_sha256 for s in snapshots] + [d.receipt_sha256 for d in derivations],
        criterion.criterion_sha256,
        "all frozen external mappings and local derivations replayed",
    )
    if collision.cross_registry_collision:
        append_collision_status(
            journal,
            "CROSS_REGISTRY_COLLISION",
            [collision.receipt_sha256],
            criterion.criterion_sha256,
            "at least two unique frozen external domains matched",
        )

    return FixtureReplayV1(
        subject=subject,
        provenance=provenance,
        snapshots=tuple(snapshots),
        derivations=tuple(derivations),
        observations=tuple(observations),
        criterion=criterion,
        collision=collision,
        status_history=journal.history,
    )
