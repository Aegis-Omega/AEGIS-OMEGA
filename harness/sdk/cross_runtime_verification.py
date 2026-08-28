"""AEGIS Ω cross-runtime verification receipt v1.

This module binds execution evidence to the exact source identity that was
executed. Components whose authority depends on a concrete external artifact
can additionally bind a SHA-256 evidence identity into the aggregate receipt.
A local PASS count is retained as evidence but cannot acquire remote or
exact-head authority without the required source/execution/artifact binding.

This module does not prove scientific claims, global Weil positivity, or RH.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
from typing import Any, Iterable, Optional


_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RuntimeEvidenceV1:
    component: str
    required: bool
    source_repo: str
    source_commit: Optional[str]
    execution_commit: Optional[str]
    execution_status: str
    observed_passes: Optional[int]
    observed_failures: Optional[int]
    evidence_origin: str
    remote_reference_commit: Optional[str] = None
    evidence_kind: Optional[str] = None
    evidence_sha256: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.component:
            raise ValueError("component must be non-empty")
        if not self.source_repo:
            raise ValueError("source_repo must be non-empty")
        for name, value in (
            ("source_commit", self.source_commit),
            ("execution_commit", self.execution_commit),
            ("remote_reference_commit", self.remote_reference_commit),
        ):
            if value is not None and not _SHA1_RE.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase 40-hex Git commit SHA")
        for name, value in (
            ("observed_passes", self.observed_passes),
            ("observed_failures", self.observed_failures),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be nonnegative")

        if self.evidence_sha256 is not None and not _SHA256_RE.fullmatch(self.evidence_sha256):
            raise ValueError("evidence_sha256 must be a lowercase 64-hex SHA-256 digest")
        if self.evidence_sha256 is not None and not self.evidence_kind:
            raise ValueError("evidence_kind must be non-empty when evidence_sha256 is provided")
        if self.evidence_kind is not None and not self.evidence_kind:
            raise ValueError("evidence_kind must be non-empty when provided")

    def binding_status(self) -> str:
        if (
            self.source_commit is not None
            and self.execution_commit is not None
            and self.source_commit != self.execution_commit
        ):
            return "SOURCE_EXECUTION_MISMATCH"

        if self.evidence_origin == "REMOTE_EXACT_HEAD_ARTIFACT_REPLAY":
            if self.evidence_sha256 is None or self.evidence_kind is None:
                return "REMOTE_ARTIFACT_UNBOUND"
            if (
                self.source_commit is not None
                and self.execution_commit == self.source_commit
                and self.execution_status == "PASS"
                and self.observed_failures in (0, None)
            ):
                return "REMOTE_EXACT_HEAD_VERIFIED"

        if (
            self.evidence_origin == "REMOTE_EXACT_HEAD_REPLAY"
            and self.source_commit is not None
            and self.execution_commit == self.source_commit
            and self.execution_status == "PASS"
            and self.observed_failures in (0, None)
        ):
            return "REMOTE_EXACT_HEAD_VERIFIED"

        if self.source_commit is not None and self.execution_commit is None:
            return "REMOTE_SOURCE_UNREPLAYED"

        if (
            self.evidence_origin in {
                "LOCAL_WORKING_ENVIRONMENT_UNBOUND",
                "OPERATOR_REPORTED_LOCAL_WORKING_ENVIRONMENT_UNBOUND",
            }
            or (self.execution_status == "PASS" and self.source_commit is None)
        ):
            return "LOCAL_VERIFIED_UNBOUND"

        if self.execution_status != "PASS":
            return "EXECUTION_NOT_PASS"

        return "UNBOUND_OR_UNRECOGNIZED"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["binding_status"] = self.binding_status()
        data["remote_reference_grants_authority"] = False
        return data


@dataclass(frozen=True)
class CrossRuntimeVerificationReceiptV1:
    components: tuple[dict[str, Any], ...]
    overall_status: str
    all_required_components_exact_head_bound: bool
    global_weil_positivity_proven: bool = False
    rh_proven: bool = False
    receipt_version: str = "CrossRuntimeVerificationReceiptV1"
    receipt_sha256: str = field(default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_version": self.receipt_version,
            "components": [dict(component) for component in self.components],
            "overall_status": self.overall_status,
            "all_required_components_exact_head_bound": self.all_required_components_exact_head_bound,
            "global_weil_positivity_proven": self.global_weil_positivity_proven,
            "rh_proven": self.rh_proven,
            "receipt_sha256": self.receipt_sha256,
        }


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_cross_runtime_receipt(
    evidence: Iterable[RuntimeEvidenceV1],
) -> CrossRuntimeVerificationReceiptV1:
    entries = list(evidence)
    if not entries:
        raise ValueError("at least one runtime evidence entry is required")

    names = [entry.component for entry in entries]
    if len(set(names)) != len(names):
        raise ValueError("component names must be unique")

    component_dicts = tuple(
        entry.to_dict() for entry in sorted(entries, key=lambda item: item.component)
    )
    required = [entry for entry in entries if entry.required]
    all_bound = bool(required) and all(
        entry.binding_status() == "REMOTE_EXACT_HEAD_VERIFIED" for entry in required
    )
    overall = "ESTABLISHED" if all_bound else "BLOCKED_UNBOUND_COMPONENT"

    unsigned = {
        "receipt_version": "CrossRuntimeVerificationReceiptV1",
        "components": [dict(component) for component in component_dicts],
        "overall_status": overall,
        "all_required_components_exact_head_bound": all_bound,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
    }
    digest = hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()

    return CrossRuntimeVerificationReceiptV1(
        components=component_dicts,
        overall_status=overall,
        all_required_components_exact_head_bound=all_bound,
        receipt_sha256=digest,
    )
