"""AEGIS Evidence Gradient Compiler v1.

Deterministic research-only compiler for heterogeneous evidence.

Learning dispositions:
- POSITIVE: every required transition is verified, provenance-complete, and
  sufficiently independent; a kernel-verified formal witness is mandatory when
  policy requires one.
- CONTRASTIVE_ONLY: independently witnessed semantic disagreement. Useful as a
  falsifier/negative sample, never as a positive target.
- QUARANTINE: missing, stale, infrastructure-only, or otherwise incomplete
  evidence. No positive gradient authority.

LZ78 representation-volatility telemetry affects sampling priority only. It
never upgrades epistemic authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Mapping, Sequence

SCHEMA = "AEGIS_EVIDENCE_GRADIENT_COMPILER_V1"
PPM = 1_000_000
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class WitnessStatus(str, Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"
    STALE = "STALE"


class FailureKind(str, Enum):
    NONE = "NONE"
    SEMANTIC_DISAGREEMENT = "SEMANTIC_DISAGREEMENT"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    PROVENANCE = "PROVENANCE"
    EXECUTION = "EXECUTION"


class LearningDisposition(str, Enum):
    POSITIVE = "POSITIVE"
    CONTRASTIVE_ONLY = "CONTRASTIVE_ONLY"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class Witness:
    name: str
    status: WitnessStatus
    independence_group: str
    required: bool = True
    formal_kernel: bool = False
    source_ref: str = ""
    evidence_sha256: str = ""
    failure_kind: FailureKind = FailureKind.NONE
    detail: str = ""

    def provenance_complete(self) -> bool:
        if self.status is not WitnessStatus.VERIFIED:
            return False
        return bool(self.source_ref) and _HEX64.fullmatch(self.evidence_sha256) is not None


@dataclass(frozen=True)
class CompilerPolicy:
    min_independent_groups: int = 2
    formal_kernel_required: bool = False
    positive_weight_ppm: int = PPM
    contrastive_weight_ppm: int = PPM

    def validate(self) -> None:
        if self.min_independent_groups < 1:
            raise ValueError("MIN_INDEPENDENT_GROUPS_MUST_BE_POSITIVE")
        for value in (self.positive_weight_ppm, self.contrastive_weight_ppm):
            if not 0 <= value <= PPM:
                raise ValueError("WEIGHT_PPM_OUT_OF_RANGE")


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lz78_phrase_count(data: bytes) -> int:
    """Return deterministic LZ78 phrase count for a byte sequence."""
    if not data:
        return 0
    dictionary: set[bytes] = set()
    i = 0
    phrases = 0
    n = len(data)
    while i < n:
        j = i + 1
        while j <= n and data[i:j] in dictionary:
            j += 1
        phrase = data[i:min(j, n)]
        dictionary.add(phrase)
        phrases += 1
        i += len(phrase)
    return phrases


def lz78_density_ppm(data: bytes) -> int:
    if not data:
        return 0
    return min(PPM, lz78_phrase_count(data) * PPM // len(data))


def _normalise_source_head(source_head_sha: str) -> str:
    if _HEX40.fullmatch(source_head_sha) is None:
        raise ValueError("SOURCE_HEAD_SHA_MUST_BE_LOWERCASE_HEX40")
    return source_head_sha


def compile_evidence_gradient(
    *,
    example_id: str,
    source_head_sha: str,
    witnesses: Sequence[Witness],
    representation: bytes = b"",
    previous_representation: bytes | None = None,
    policy: CompilerPolicy = CompilerPolicy(),
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Compile evidence into a fail-closed learning disposition."""
    policy.validate()
    source_head_sha = _normalise_source_head(source_head_sha)
    if not example_id:
        raise ValueError("EXAMPLE_ID_REQUIRED")
    if not witnesses:
        raise ValueError("AT_LEAST_ONE_WITNESS_REQUIRED")

    names = [w.name for w in witnesses]
    if len(names) != len(set(names)):
        raise ValueError("WITNESS_NAMES_MUST_BE_UNIQUE")

    required = [w for w in witnesses if w.required]
    if not required:
        raise ValueError("AT_LEAST_ONE_REQUIRED_WITNESS")

    semantic_failures = [
        w for w in required
        if w.status is WitnessStatus.FAILED
        and w.failure_kind is FailureKind.SEMANTIC_DISAGREEMENT
    ]
    incomplete = [
        w for w in required
        if w.status in (WitnessStatus.UNVERIFIED, WitnessStatus.STALE)
        or (
            w.status is WitnessStatus.FAILED
            and w.failure_kind is not FailureKind.SEMANTIC_DISAGREEMENT
        )
    ]
    verified = [w for w in required if w.status is WitnessStatus.VERIFIED]
    provenance_incomplete = [w for w in verified if not w.provenance_complete()]
    verified_groups = sorted({w.independence_group for w in verified})
    formal_verified = any(
        w.formal_kernel and w.provenance_complete() for w in verified
    )

    if semantic_failures:
        disposition = LearningDisposition.CONTRASTIVE_ONLY
        reason = "INDEPENDENT_SEMANTIC_DISAGREEMENT"
    elif incomplete or provenance_incomplete:
        disposition = LearningDisposition.QUARANTINE
        reason = "INCOMPLETE_OR_UNBOUND_EVIDENCE"
    elif len(verified_groups) < policy.min_independent_groups:
        disposition = LearningDisposition.QUARANTINE
        reason = "INSUFFICIENT_INDEPENDENT_WITNESS_GROUPS"
    elif policy.formal_kernel_required and not formal_verified:
        disposition = LearningDisposition.QUARANTINE
        reason = "FORMAL_KERNEL_WITNESS_REQUIRED"
    else:
        disposition = LearningDisposition.POSITIVE
        reason = "ALL_REQUIRED_TRANSITIONS_VERIFIED"

    positive_weight = (
        policy.positive_weight_ppm
        if disposition is LearningDisposition.POSITIVE else 0
    )
    contrastive_weight = (
        policy.contrastive_weight_ppm
        if disposition is LearningDisposition.CONTRASTIVE_ONLY else 0
    )

    current_lz = lz78_density_ppm(representation)
    previous_lz = (
        lz78_density_ppm(previous_representation or b"")
        if previous_representation is not None
        else current_lz
    )
    volatility = abs(current_lz - previous_lz)

    # Sampling priority is authority-neutral. Falsifiers and volatile examples
    # may be prioritized for inspection/training queues without being promoted.
    base_priority = {
        LearningDisposition.POSITIVE: 400_000,
        LearningDisposition.CONTRASTIVE_ONLY: 800_000,
        LearningDisposition.QUARANTINE: 200_000,
    }[disposition]
    sampling_priority = min(PPM, base_priority + volatility // 2)

    witness_rows = [
        {
            "name": w.name,
            "status": w.status.value,
            "independence_group": w.independence_group,
            "required": w.required,
            "formal_kernel": w.formal_kernel,
            "source_ref": w.source_ref,
            "evidence_sha256": w.evidence_sha256,
            "provenance_complete": w.provenance_complete(),
            "failure_kind": w.failure_kind.value,
            "detail": w.detail,
        }
        for w in witnesses
    ]

    receipt: dict[str, object] = {
        "schema": SCHEMA,
        "example_id": example_id,
        "source_head_sha": source_head_sha,
        "disposition": disposition.value,
        "reason": reason,
        "positive_gradient_weight_ppm": positive_weight,
        "contrastive_weight_ppm": contrastive_weight,
        "sampling_priority_ppm": sampling_priority,
        "verified_independence_groups": verified_groups,
        "formal_kernel_verified": formal_verified,
        "formal_kernel_required": policy.formal_kernel_required,
        "representation_sha256": sha256_hex(representation),
        "lz78_density_ppm": current_lz,
        "lz78_volatility_ppm": volatility,
        "witnesses": witness_rows,
        "metadata": dict(metadata or {}),
        "authority_effect": "NONE",
    }
    receipt["receipt_sha256"] = sha256_hex(canonical_json_bytes(receipt))
    return receipt
