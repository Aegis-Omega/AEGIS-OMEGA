"""AEGIS Ω — deterministic prospective cross-domain epoch primitives.

This module freezes the Epoch V1 protocol before subject generation and binds
each generated integer to an exact draw position.  It performs no network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import cross_domain_collision as cdc
import cross_domain_coverage as cov
import research_invariants as ri


EPOCH_ID_V1 = "PROSPECTIVE_UNICODE_NCBI_EPOCH_V1"
PARENT_COLLISION_SCHEMA_ID = "AEGIS_CROSS_DOMAIN_COLLISION_V1"
GENERATOR_ID_V1 = "PY_RANDOM_UNIFORM_INT_V1"
GENERATOR_VERSION_V1 = "PYTHON_RANDOM_MT19937_RANDINT_V1"
DUPLICATE_POLICY_V1 = "POSITIONAL_DRAWS_WITH_REPLACEMENT_V1"
COVERAGE_POLICY_V1 = "REQUIRE_ALL_FROZEN_REGISTRIES_V1"
REGISTRY_IDS_V1 = ("unicode", "ncbi-gene")
TRANSFORM_ID_V1 = "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1"
TRANSFORM_CRITERION_SHA256_V1 = ri.literal_sha256("integer identity external lookup key v1")
UNICODE_SOURCE_LOCATOR_V1 = "https://www.unicode.org/Public/17.0.0/ucd/extracted/DerivedGeneralCategory.txt"


def _adapter_digest(
    registry_id: str,
    positive_rule: str,
    negative_rule: str,
    ambiguous_rule: str,
) -> str:
    adapter = cov.RegistryAdapterContractV1(
        registry_id=registry_id,
        adapter_version="PROSPECTIVE_EPOCH_V1",
        query_key_type="integer-decimal",
        transform_id=TRANSFORM_ID_V1,
        transform_criterion_sha256=TRANSFORM_CRITERION_SHA256_V1,
        positive_result_rule_id=positive_rule,
        negative_result_rule_id=negative_rule,
        ambiguous_result_rule_id=ambiguous_rule,
        canonicalization_rule_id="CANONICAL_JSON_V1",
        contract_text=f"prospective epoch v1 {registry_id} source-bound adapter",
    )
    return adapter.contract_sha256


UNICODE_ADAPTER_SHA256_V1 = _adapter_digest(
    "unicode",
    "UNICODE_GENERAL_CATEGORY_NOT_CN_V1",
    "UNICODE_GENERAL_CATEGORY_CN_V1",
    "UNICODE_OUT_OF_RANGE_NOT_ESTABLISHED_V1",
)
NCBI_ADAPTER_SHA256_V1 = _adapter_digest(
    "ncbi-gene",
    "NCBI_ESEARCH_UID_PRESENT_V1",
    "NCBI_ESEARCH_UID_ABSENT_V1",
    "NCBI_ESEARCH_NOT_ESTABLISHED_V1",
)

UNICODE_SOURCE_MATERIAL_V1 = {
    "schema": "AEGIS_UNICODE_SOURCE_CONTRACT_V1",
    "source_id": "unicode-ucd",
    "release": "17.0.0",
    "source_locator": UNICODE_SOURCE_LOCATOR_V1,
    "parser_version": "1",
    "positive_rule_id": "UNICODE_GENERAL_CATEGORY_NOT_CN_V1",
    "negative_rule_id": "UNICODE_GENERAL_CATEGORY_CN_V1",
    "ambiguous_rule_id": "UNICODE_OUT_OF_RANGE_NOT_ESTABLISHED_V1",
}
NCBI_SOURCE_MATERIAL_V1 = {
    "schema": "AEGIS_NCBI_GENE_SOURCE_CONTRACT_V1",
    "source_id": "ncbi-gene-esearch",
    "database": "gene",
    "endpoint_family": "esearch.fcgi",
    "response_mode": "json",
    "search_field": "UID",
    "parser_version": "1",
    "max_batch_size": 100,
    "batch_rule_id": "SORTED_UNIQUE_UID_OR_QUERY_V1",
    "positive_rule_id": "NCBI_ESEARCH_UID_PRESENT_V1",
    "negative_rule_id": "NCBI_ESEARCH_UID_ABSENT_V1",
    "ambiguous_rule_id": "NCBI_ESEARCH_NOT_ESTABLISHED_V1",
}
UNICODE_SOURCE_SHA256_V1 = ri.sha256_hex(UNICODE_SOURCE_MATERIAL_V1)
NCBI_SOURCE_SHA256_V1 = ri.sha256_hex(NCBI_SOURCE_MATERIAL_V1)


@dataclass(frozen=True)
class ProspectiveEpochV1:
    epoch_id: str
    parent_collision_schema_id: str
    universe_min: int
    universe_max: int
    registry_ids: tuple[str, ...]
    registry_adapter_contract_sha256s: tuple[str, ...]
    source_contract_sha256s: tuple[str, ...]
    score_function_id: str
    independence_rule_id: str
    generator_id: str
    generator_version: str
    seed: int
    subject_count: int
    duplicate_policy_id: str
    coverage_policy_id: str
    promotion_threshold: None
    freeze_reason: str
    epoch_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer, not bool")
        if isinstance(self.subject_count, bool) or not isinstance(self.subject_count, int):
            raise TypeError("subject_count must be an integer, not bool")
        if self.subject_count <= 0:
            raise ValueError("subject_count must be positive")
        if self.universe_min != 0 or self.universe_max != 100000:
            raise ValueError("Epoch V1 universe must be exactly [0, 100000]")
        if tuple(self.registry_ids) != REGISTRY_IDS_V1:
            raise ValueError("Epoch V1 registry set must be exactly Unicode + NCBI Gene")
        if len(self.registry_adapter_contract_sha256s) != 2 or len(self.source_contract_sha256s) != 2:
            raise ValueError("Epoch V1 requires exactly two adapter/source contract digests")
        for digest in self.registry_adapter_contract_sha256s + self.source_contract_sha256s:
            ri._check_digest(digest, "epoch contract digest")
        if self.promotion_threshold is not None:
            raise ValueError("Epoch V1 is descriptive and requires promotion_threshold=None")
        object.__setattr__(self, "registry_ids", tuple(self.registry_ids))
        object.__setattr__(self, "registry_adapter_contract_sha256s", tuple(self.registry_adapter_contract_sha256s))
        object.__setattr__(self, "source_contract_sha256s", tuple(self.source_contract_sha256s))
        object.__setattr__(self, "epoch_sha256", ri.sha256_hex(_epoch_material(self)))


def _epoch_material(epoch: ProspectiveEpochV1) -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_PROSPECTIVE_EPOCH_V1",
        "epoch_id": epoch.epoch_id,
        "parent_collision_schema_id": epoch.parent_collision_schema_id,
        "universe_min": epoch.universe_min,
        "universe_max": epoch.universe_max,
        "registry_ids": epoch.registry_ids,
        "registry_adapter_contract_sha256s": epoch.registry_adapter_contract_sha256s,
        "source_contract_sha256s": epoch.source_contract_sha256s,
        "score_function_id": epoch.score_function_id,
        "independence_rule_id": epoch.independence_rule_id,
        "generator_id": epoch.generator_id,
        "generator_version": epoch.generator_version,
        "seed": epoch.seed,
        "subject_count": epoch.subject_count,
        "duplicate_policy_id": epoch.duplicate_policy_id,
        "coverage_policy_id": epoch.coverage_policy_id,
        "promotion_threshold": epoch.promotion_threshold,
        "freeze_reason": epoch.freeze_reason,
    }


def make_epoch_v1(*, seed: int, subject_count: int = 1000) -> ProspectiveEpochV1:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer, not bool")
    if isinstance(subject_count, bool) or not isinstance(subject_count, int):
        raise TypeError("subject_count must be an integer, not bool")
    if subject_count <= 0:
        raise ValueError("subject_count must be positive")
    return ProspectiveEpochV1(
        epoch_id=EPOCH_ID_V1,
        parent_collision_schema_id=PARENT_COLLISION_SCHEMA_ID,
        universe_min=0,
        universe_max=100000,
        registry_ids=REGISTRY_IDS_V1,
        registry_adapter_contract_sha256s=(UNICODE_ADAPTER_SHA256_V1, NCBI_ADAPTER_SHA256_V1),
        source_contract_sha256s=(UNICODE_SOURCE_SHA256_V1, NCBI_SOURCE_SHA256_V1),
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        generator_id=GENERATOR_ID_V1,
        generator_version=GENERATOR_VERSION_V1,
        seed=seed,
        subject_count=subject_count,
        duplicate_policy_id=DUPLICATE_POLICY_V1,
        coverage_policy_id=COVERAGE_POLICY_V1,
        promotion_threshold=None,
        freeze_reason="freeze Unicode 17.0.0 + NCBI Gene prospective collision census before generation",
    )


def verify_epoch(epoch: ProspectiveEpochV1) -> None:
    if not isinstance(epoch, ProspectiveEpochV1):
        raise TypeError("expected ProspectiveEpochV1")
    ri._check_digest(epoch.epoch_sha256, "epoch_sha256")
    if ri.sha256_hex(_epoch_material(epoch)) != epoch.epoch_sha256:
        raise ValueError("prospective epoch digest mismatch")
    if epoch.epoch_id != EPOCH_ID_V1 or epoch.registry_ids != REGISTRY_IDS_V1:
        raise ValueError("unsupported prospective epoch semantics")
    if epoch.generator_id != GENERATOR_ID_V1 or epoch.generator_version != GENERATOR_VERSION_V1:
        raise ValueError("unsupported prospective generator semantics")
    if epoch.duplicate_policy_id != DUPLICATE_POLICY_V1 or epoch.coverage_policy_id != COVERAGE_POLICY_V1:
        raise ValueError("unsupported prospective epoch policies")


def epoch_collision_criterion(epoch: ProspectiveEpochV1) -> cdc.CollisionCriterionV1:
    verify_epoch(epoch)
    return cdc.CollisionCriterionV1(
        universe_min=epoch.universe_min,
        universe_max=epoch.universe_max,
        registry_set=epoch.registry_ids,
        transform_set=(TRANSFORM_ID_V1,),
        independence_rule_id=epoch.independence_rule_id,
        score_function_id=epoch.score_function_id,
        control_generator_id=epoch.generator_id,
        control_seed=epoch.seed,
        control_count=epoch.subject_count,
        promotion_threshold=None,
        criterion_text=f"prospective-epoch-v1:{epoch.epoch_id}",
    )


@dataclass(frozen=True)
class SubjectGenerationReceiptV1:
    epoch_sha256: str
    draw_index: int
    value: int
    subject_sha256: str
    generated_sequence_sha256: str
    generator_id: str
    generator_version: str
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        ri._check_digest(self.epoch_sha256, "epoch_sha256")
        ri._check_digest(self.subject_sha256, "subject_sha256")
        ri._check_digest(self.generated_sequence_sha256, "generated_sequence_sha256")
        if isinstance(self.draw_index, bool) or not isinstance(self.draw_index, int) or self.draw_index < 0:
            raise ValueError("draw_index must be a non-negative integer")
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("generated value must be an integer")
        object.__setattr__(self, "receipt_sha256", ri.sha256_hex(_generation_material(self)))


def _generation_material(receipt: SubjectGenerationReceiptV1) -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_SUBJECT_GENERATION_RECEIPT_V1",
        "epoch_sha256": receipt.epoch_sha256,
        "draw_index": receipt.draw_index,
        "value": receipt.value,
        "subject_sha256": receipt.subject_sha256,
        "generated_sequence_sha256": receipt.generated_sequence_sha256,
        "generator_id": receipt.generator_id,
        "generator_version": receipt.generator_version,
    }


def _generated_values(epoch: ProspectiveEpochV1) -> tuple[int, ...]:
    return cdc.generate_controls(epoch_collision_criterion(epoch))


def generate_subject_receipts(epoch: ProspectiveEpochV1) -> tuple[SubjectGenerationReceiptV1, ...]:
    values = _generated_values(epoch)
    sequence_sha256 = ri.sha256_hex(values)
    receipts = tuple(
        SubjectGenerationReceiptV1(
            epoch_sha256=epoch.epoch_sha256,
            draw_index=index,
            value=value,
            subject_sha256=cdc.IntegerSubjectV1(value).subject_sha256,
            generated_sequence_sha256=sequence_sha256,
            generator_id=epoch.generator_id,
            generator_version=epoch.generator_version,
        )
        for index, value in enumerate(values)
    )
    for receipt in receipts:
        verify_subject_generation_receipt(epoch, receipt)
    return receipts


def verify_subject_generation_receipt(epoch: ProspectiveEpochV1, receipt: SubjectGenerationReceiptV1) -> None:
    verify_epoch(epoch)
    if not isinstance(receipt, SubjectGenerationReceiptV1):
        raise TypeError("expected SubjectGenerationReceiptV1")
    if receipt.epoch_sha256 != epoch.epoch_sha256:
        raise ValueError("generation receipt epoch mismatch")
    if not 0 <= receipt.draw_index < epoch.subject_count:
        raise ValueError("generation draw index outside epoch")
    values = _generated_values(epoch)
    expected_value = values[receipt.draw_index]
    if receipt.value != expected_value:
        raise ValueError("generation receipt value does not match deterministic draw")
    expected_subject = cdc.IntegerSubjectV1(expected_value).subject_sha256
    if receipt.subject_sha256 != expected_subject:
        raise ValueError("generation receipt subject digest mismatch")
    expected_sequence_sha256 = ri.sha256_hex(values)
    if receipt.generated_sequence_sha256 != expected_sequence_sha256:
        raise ValueError("generation sequence digest mismatch")
    if receipt.generator_id != epoch.generator_id or receipt.generator_version != epoch.generator_version:
        raise ValueError("generation receipt generator mismatch")
    ri._check_digest(receipt.receipt_sha256, "receipt_sha256")
    if ri.sha256_hex(_generation_material(receipt)) != receipt.receipt_sha256:
        raise ValueError("generation receipt digest mismatch")
