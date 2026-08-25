"""AEGIS Ω — deterministic integer-first cross-domain collision core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

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
