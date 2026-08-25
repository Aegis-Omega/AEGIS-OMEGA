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
