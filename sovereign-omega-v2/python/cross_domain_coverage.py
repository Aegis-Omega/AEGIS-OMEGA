"""AEGIS Ω — proof-carrying control-registry coverage primitives.

This module is offline-authoritative. Live/network code may produce immutable
source artifacts elsewhere, but promotion-grade probe evidence is classified
and replayed here under frozen adapter contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

import cross_domain_collision as cdc
import research_invariants as ri


class RegistryProbeOutcomeV1(str, Enum):
    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


SUPPORTED_POSITIVE_RULES = {"MATCH_BOOL_TRUE_V1"}
SUPPORTED_NEGATIVE_RULES = {"MATCH_BOOL_FALSE_V1"}
SUPPORTED_AMBIGUOUS_RULES = {"STATUS_NOT_ESTABLISHED_V1"}
SUPPORTED_CANONICALIZATION_RULES = {"CANONICAL_JSON_V1"}
SUPPORTED_TRANSFORMS = {"INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1"}


@dataclass(frozen=True)
class RegistryAdapterContractV1:
    registry_id: str
    adapter_version: str
    query_key_type: str
    transform_id: str
    transform_criterion_sha256: str
    positive_result_rule_id: str
    negative_result_rule_id: str
    ambiguous_result_rule_id: str
    canonicalization_rule_id: str
    contract_text: str
    contract_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("registry_id", self.registry_id),
            ("adapter_version", self.adapter_version),
            ("query_key_type", self.query_key_type),
            ("transform_id", self.transform_id),
            ("positive_result_rule_id", self.positive_result_rule_id),
            ("negative_result_rule_id", self.negative_result_rule_id),
            ("ambiguous_result_rule_id", self.ambiguous_result_rule_id),
            ("canonicalization_rule_id", self.canonicalization_rule_id),
            ("contract_text", self.contract_text),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        ri._check_digest(self.transform_criterion_sha256, "transform_criterion_sha256")
        object.__setattr__(self, "contract_sha256", ri.sha256_hex(_adapter_material(self)))


def _adapter_material(adapter: RegistryAdapterContractV1) -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_REGISTRY_ADAPTER_CONTRACT_V1",
        "registry_id": adapter.registry_id,
        "adapter_version": adapter.adapter_version,
        "query_key_type": adapter.query_key_type,
        "transform_id": adapter.transform_id,
        "transform_criterion_sha256": adapter.transform_criterion_sha256,
        "positive_result_rule_id": adapter.positive_result_rule_id,
        "negative_result_rule_id": adapter.negative_result_rule_id,
        "ambiguous_result_rule_id": adapter.ambiguous_result_rule_id,
        "canonicalization_rule_id": adapter.canonicalization_rule_id,
        "contract_text": adapter.contract_text,
    }


def verify_registry_adapter_contract(adapter: RegistryAdapterContractV1) -> None:
    if not isinstance(adapter, RegistryAdapterContractV1):
        raise TypeError("expected RegistryAdapterContractV1")
    ri._check_digest(adapter.transform_criterion_sha256, "transform_criterion_sha256")
    ri._check_digest(adapter.contract_sha256, "contract_sha256")
    if adapter.transform_id not in SUPPORTED_TRANSFORMS:
        raise ValueError(f"unsupported adapter transform: {adapter.transform_id}")
    if adapter.positive_result_rule_id not in SUPPORTED_POSITIVE_RULES:
        raise ValueError(f"unsupported positive-result rule: {adapter.positive_result_rule_id}")
    if adapter.negative_result_rule_id not in SUPPORTED_NEGATIVE_RULES:
        raise ValueError(f"unsupported negative-result rule: {adapter.negative_result_rule_id}")
    if adapter.ambiguous_result_rule_id not in SUPPORTED_AMBIGUOUS_RULES:
        raise ValueError(f"unsupported ambiguous-result rule: {adapter.ambiguous_result_rule_id}")
    if adapter.canonicalization_rule_id not in SUPPORTED_CANONICALIZATION_RULES:
        raise ValueError(f"unsupported canonicalization rule: {adapter.canonicalization_rule_id}")
    if ri.sha256_hex(_adapter_material(adapter)) != adapter.contract_sha256:
        raise ValueError("adapter contract digest mismatch")


@dataclass(frozen=True)
class ProbeFailureEvidenceV1:
    failure_class: str
    failure_message: str
    source_locator: str
    source_observed_at: str
    producer_id: str
    evidence_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("failure_class", self.failure_class),
            ("failure_message", self.failure_message),
            ("source_locator", self.source_locator),
            ("source_observed_at", self.source_observed_at),
            ("producer_id", self.producer_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        object.__setattr__(self, "evidence_sha256", ri.sha256_hex(_failure_material(self)))


def _failure_material(evidence: ProbeFailureEvidenceV1) -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_PROBE_FAILURE_EVIDENCE_V1",
        "failure_class": evidence.failure_class,
        "failure_message": evidence.failure_message,
        "source_locator": evidence.source_locator,
        "source_observed_at": evidence.source_observed_at,
        "producer_id": evidence.producer_id,
    }


def _verify_failure_evidence(evidence: ProbeFailureEvidenceV1) -> None:
    if not isinstance(evidence, ProbeFailureEvidenceV1):
        raise TypeError("expected ProbeFailureEvidenceV1")
    ri._check_digest(evidence.evidence_sha256, "evidence_sha256")
    if ri.sha256_hex(_failure_material(evidence)) != evidence.evidence_sha256:
        raise ValueError("failure evidence digest mismatch")


@dataclass(frozen=True)
class RegistryProbeReceiptV1:
    subject_sha256: str
    registry_id: str
    query_key: str
    query_key_type: str
    transform_id: str
    transform_criterion_sha256: str
    registry_version_or_release: str
    adapter_contract_sha256: str
    source_evidence_sha256: str
    outcome: RegistryProbeOutcomeV1
    criterion_sha256: str
    receipt_sha256: str


def _probe_receipt_material(receipt: RegistryProbeReceiptV1) -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_REGISTRY_PROBE_RECEIPT_V1",
        "subject_sha256": receipt.subject_sha256,
        "registry_id": receipt.registry_id,
        "query_key": receipt.query_key,
        "query_key_type": receipt.query_key_type,
        "transform_id": receipt.transform_id,
        "transform_criterion_sha256": receipt.transform_criterion_sha256,
        "registry_version_or_release": receipt.registry_version_or_release,
        "adapter_contract_sha256": receipt.adapter_contract_sha256,
        "source_evidence_sha256": receipt.source_evidence_sha256,
        "outcome": receipt.outcome.value,
        "criterion_sha256": receipt.criterion_sha256,
    }


def verify_registry_probe_receipt(receipt: RegistryProbeReceiptV1) -> None:
    if not isinstance(receipt, RegistryProbeReceiptV1):
        raise TypeError("expected RegistryProbeReceiptV1")
    for name, digest in (
        ("subject_sha256", receipt.subject_sha256),
        ("transform_criterion_sha256", receipt.transform_criterion_sha256),
        ("adapter_contract_sha256", receipt.adapter_contract_sha256),
        ("source_evidence_sha256", receipt.source_evidence_sha256),
        ("criterion_sha256", receipt.criterion_sha256),
        ("receipt_sha256", receipt.receipt_sha256),
    ):
        ri._check_digest(digest, name)
    for name, value in (
        ("registry_id", receipt.registry_id),
        ("query_key", receipt.query_key),
        ("query_key_type", receipt.query_key_type),
        ("transform_id", receipt.transform_id),
        ("registry_version_or_release", receipt.registry_version_or_release),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")
    if not isinstance(receipt.outcome, RegistryProbeOutcomeV1):
        raise ValueError("probe outcome is not canonical")
    if ri.sha256_hex(_probe_receipt_material(receipt)) != receipt.receipt_sha256:
        raise ValueError("registry probe receipt digest mismatch")


def _mint_probe_receipt(
    *,
    subject_sha256: str,
    registry_id: str,
    query_key: str,
    query_key_type: str,
    transform_id: str,
    transform_criterion_sha256: str,
    registry_version_or_release: str,
    adapter_contract_sha256: str,
    source_evidence_sha256: str,
    outcome: RegistryProbeOutcomeV1,
    criterion_sha256: str,
) -> RegistryProbeReceiptV1:
    provisional = RegistryProbeReceiptV1(
        subject_sha256=subject_sha256,
        registry_id=registry_id,
        query_key=query_key,
        query_key_type=query_key_type,
        transform_id=transform_id,
        transform_criterion_sha256=transform_criterion_sha256,
        registry_version_or_release=registry_version_or_release,
        adapter_contract_sha256=adapter_contract_sha256,
        source_evidence_sha256=source_evidence_sha256,
        outcome=outcome,
        criterion_sha256=criterion_sha256,
        receipt_sha256="0" * 64,
    )
    receipt = RegistryProbeReceiptV1(
        subject_sha256=provisional.subject_sha256,
        registry_id=provisional.registry_id,
        query_key=provisional.query_key,
        query_key_type=provisional.query_key_type,
        transform_id=provisional.transform_id,
        transform_criterion_sha256=provisional.transform_criterion_sha256,
        registry_version_or_release=provisional.registry_version_or_release,
        adapter_contract_sha256=provisional.adapter_contract_sha256,
        source_evidence_sha256=provisional.source_evidence_sha256,
        outcome=provisional.outcome,
        criterion_sha256=provisional.criterion_sha256,
        receipt_sha256=ri.sha256_hex(_probe_receipt_material(provisional)),
    )
    verify_registry_probe_receipt(receipt)
    return receipt


def _snapshot_material(snapshot: cdc.RegistrySnapshotV1) -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_REGISTRY_SNAPSHOT_V1",
        "registry_id": snapshot.registry_id,
        "registry_version_or_release": snapshot.registry_version_or_release,
        "query_key": snapshot.query_key,
        "query_key_type": snapshot.query_key_type,
        "result_kind": snapshot.result_kind,
        "canonical_result": snapshot.canonical_result,
        "source_locator": snapshot.source_locator,
        "source_observed_at": snapshot.source_observed_at,
        "ingestion_producer_id": snapshot.ingestion_producer_id,
    }


def _verify_snapshot(snapshot: cdc.RegistrySnapshotV1) -> None:
    if not isinstance(snapshot, cdc.RegistrySnapshotV1):
        raise TypeError("expected RegistrySnapshotV1 source evidence")
    ri._check_digest(snapshot.content_sha256, "content_sha256")
    if ri.sha256_hex(_snapshot_material(snapshot)) != snapshot.content_sha256:
        raise ValueError("registry snapshot digest mismatch")


def _validate_probe_context(
    subject: cdc.IntegerSubjectV1,
    criterion: cdc.CollisionCriterionV1,
    adapter: RegistryAdapterContractV1,
) -> str:
    if not isinstance(subject, cdc.IntegerSubjectV1):
        raise TypeError("expected IntegerSubjectV1")
    if not isinstance(criterion, cdc.CollisionCriterionV1):
        raise TypeError("expected CollisionCriterionV1")
    if cdc.IntegerSubjectV1(subject.value).subject_sha256 != subject.subject_sha256:
        raise ValueError("subject digest does not match subject value")
    verify_registry_adapter_contract(adapter)
    if not criterion.universe_min <= subject.value <= criterion.universe_max:
        raise ValueError("subject outside frozen criterion universe")
    if adapter.registry_id not in criterion.registry_set:
        raise ValueError("adapter registry absent from frozen criterion")
    if adapter.transform_id not in criterion.transform_set:
        raise ValueError("adapter transform absent from frozen criterion")
    if adapter.transform_id != "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1":
        raise ValueError("unsupported query-key transform")
    return str(subject.value)


@dataclass(frozen=True)
class VerifiedRegistryProbeV1:
    subject: cdc.IntegerSubjectV1
    criterion: cdc.CollisionCriterionV1
    receipt: RegistryProbeReceiptV1
    adapter: RegistryAdapterContractV1
    source_snapshot: cdc.RegistrySnapshotV1 | None = None
    failure_evidence: ProbeFailureEvidenceV1 | None = None


def probe_registry_snapshot(
    subject: cdc.IntegerSubjectV1,
    criterion: cdc.CollisionCriterionV1,
    adapter: RegistryAdapterContractV1,
    snapshot: cdc.RegistrySnapshotV1,
) -> VerifiedRegistryProbeV1:
    expected_key = _validate_probe_context(subject, criterion, adapter)
    _verify_snapshot(snapshot)
    if snapshot.registry_id != adapter.registry_id:
        raise ValueError("snapshot registry does not match adapter")
    if snapshot.query_key != expected_key:
        raise ValueError("snapshot query key does not match transformed subject")
    if snapshot.query_key_type != adapter.query_key_type:
        raise ValueError("snapshot query-key type does not match adapter")
    if not isinstance(snapshot.canonical_result, Mapping):
        raise ValueError("snapshot canonical result must be a mapping")
    matched = snapshot.canonical_result.get("match")
    if type(matched) is not bool:
        raise ValueError("snapshot requires a literal boolean match field")
    outcome = RegistryProbeOutcomeV1.MATCH if matched else RegistryProbeOutcomeV1.NO_MATCH
    receipt = _mint_probe_receipt(
        subject_sha256=subject.subject_sha256,
        registry_id=adapter.registry_id,
        query_key=expected_key,
        query_key_type=adapter.query_key_type,
        transform_id=adapter.transform_id,
        transform_criterion_sha256=adapter.transform_criterion_sha256,
        registry_version_or_release=snapshot.registry_version_or_release,
        adapter_contract_sha256=adapter.contract_sha256,
        source_evidence_sha256=snapshot.content_sha256,
        outcome=outcome,
        criterion_sha256=criterion.criterion_sha256,
    )
    return VerifiedRegistryProbeV1(
        subject=subject,
        criterion=criterion,
        receipt=receipt,
        adapter=adapter,
        source_snapshot=snapshot,
    )


def probe_not_established(
    subject: cdc.IntegerSubjectV1,
    criterion: cdc.CollisionCriterionV1,
    adapter: RegistryAdapterContractV1,
    registry_version_or_release: str,
    failure_evidence: ProbeFailureEvidenceV1,
) -> VerifiedRegistryProbeV1:
    expected_key = _validate_probe_context(subject, criterion, adapter)
    if not isinstance(registry_version_or_release, str) or not registry_version_or_release:
        raise ValueError("registry_version_or_release must be non-empty")
    _verify_failure_evidence(failure_evidence)
    receipt = _mint_probe_receipt(
        subject_sha256=subject.subject_sha256,
        registry_id=adapter.registry_id,
        query_key=expected_key,
        query_key_type=adapter.query_key_type,
        transform_id=adapter.transform_id,
        transform_criterion_sha256=adapter.transform_criterion_sha256,
        registry_version_or_release=registry_version_or_release,
        adapter_contract_sha256=adapter.contract_sha256,
        source_evidence_sha256=failure_evidence.evidence_sha256,
        outcome=RegistryProbeOutcomeV1.NOT_ESTABLISHED,
        criterion_sha256=criterion.criterion_sha256,
    )
    return VerifiedRegistryProbeV1(
        subject=subject,
        criterion=criterion,
        receipt=receipt,
        adapter=adapter,
        failure_evidence=failure_evidence,
    )


def verify_verified_probe(probe: VerifiedRegistryProbeV1) -> None:
    if not isinstance(probe, VerifiedRegistryProbeV1):
        raise TypeError("expected VerifiedRegistryProbeV1")
    verify_registry_probe_receipt(probe.receipt)
    verify_registry_adapter_contract(probe.adapter)
    _validate_probe_context(probe.subject, probe.criterion, probe.adapter)
    if probe.receipt.subject_sha256 != probe.subject.subject_sha256:
        raise ValueError("probe receipt subject does not match carried subject")
    if probe.receipt.criterion_sha256 != probe.criterion.criterion_sha256:
        raise ValueError("probe receipt criterion does not match carried criterion")
    if probe.receipt.adapter_contract_sha256 != probe.adapter.contract_sha256:
        raise ValueError("probe adapter digest mismatch")

    has_snapshot = probe.source_snapshot is not None
    has_failure = probe.failure_evidence is not None
    if has_snapshot == has_failure:
        raise ValueError("verified probe requires exactly one source carrier")

    if probe.receipt.outcome in {RegistryProbeOutcomeV1.MATCH, RegistryProbeOutcomeV1.NO_MATCH}:
        if probe.source_snapshot is None:
            raise ValueError("MATCH/NO_MATCH requires source snapshot")
        replayed = probe_registry_snapshot(probe.subject, probe.criterion, probe.adapter, probe.source_snapshot)
    else:
        if probe.failure_evidence is None:
            raise ValueError("NOT_ESTABLISHED requires failure evidence")
        replayed = probe_not_established(
            probe.subject,
            probe.criterion,
            probe.adapter,
            probe.receipt.registry_version_or_release,
            probe.failure_evidence,
        )
    if replayed.receipt != probe.receipt:
        raise ValueError("verified probe replay does not reproduce receipt")
