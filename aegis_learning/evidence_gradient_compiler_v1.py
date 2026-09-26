"""AEGIS Evidence Gradient Compiler v1.

Deterministic research-only compiler for heterogeneous evidence.

Security boundary:
`WitnessStatus.VERIFIED` is never sufficient by itself. A verified witness must
carry an exact, self-consistent `VerifiedWitnessReceiptV1`. This closes the prior
fail-open path where any caller could manufacture positive-gradient authority by
supplying an arbitrary non-empty source_ref and arbitrary 64-hex digest.

The receipt binds source identity, verifier policy, executed provider/run,
non-zero execution, artifact identity, and the evidence digest. A structurally
valid receipt is still NOT admitted automatically: its self-hash must also be
listed in `CompilerPolicy.admitted_verified_receipt_sha256s`. This makes the
external trust/admission boundary explicit and default-deny. Provider
authenticity/attestation remains an upstream trust boundary; this compiler
validates exact binding and refuses positive-gradient authority unless the
upstream-admitted receipt hash is present.

Learning dispositions:
- POSITIVE: every required transition is verified, receipt-bound, and
  sufficiently independent; a receipt-bound kernel witness is mandatory when
  policy requires one.
- CONTRASTIVE_ONLY: independently witnessed semantic disagreement. Useful as a
  falsifier/negative sample, never as a positive target.
- QUARANTINE: missing, stale, infrastructure-only, zero-step, unbound, or
  otherwise incomplete evidence. No positive gradient authority.

LZ78 representation-volatility telemetry affects sampling priority only. It
never upgrades epistemic authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
import re
from typing import Mapping, Sequence

SCHEMA = "AEGIS_EVIDENCE_GRADIENT_COMPILER_V1"
VERIFIED_RECEIPT_SCHEMA = "AEGIS_VERIFIED_WITNESS_RECEIPT_V1"
PPM = 1_000_000
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_REF = re.compile(
    r"^(?P<repository>[^@\s]+)@(?P<head>[0-9a-f]{40}):(?P<path>.+)$"
)


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


class ExecutionStatus(str, Enum):
    EXECUTED_PASS = "EXECUTED_PASS"
    EXECUTED_FAIL = "EXECUTED_FAIL"
    NOT_RUN = "NOT_RUN"
    HISTORICAL = "HISTORICAL"


class LearningDisposition(str, Enum):
    POSITIVE = "POSITIVE"
    CONTRASTIVE_ONLY = "CONTRASTIVE_ONLY"
    QUARANTINE = "QUARANTINE"


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class VerifiedWitnessReceiptV1:
    """Exact provenance/execution binding for one VERIFIED witness.

    This object is intentionally stricter than a free-form evidence digest.
    Its own SHA-256 is deterministic and covers every authority-relevant field.
    A witness is provenance-complete only when this receipt validates exactly
    against the witness.

    This receipt proves deterministic binding/integrity. Authenticity of an
    external provider result (for example GitHub artifact attestation) remains
    an upstream verifier responsibility and should itself be represented by the
    artifact/policy commitments bound here.
    """

    source_ref: str
    source_head_sha: str
    source_blob_sha: str
    evidence_sha256: str
    verifier_policy_sha256: str
    execution_provider: str
    execution_run_id: str
    executed_steps: int
    execution_status: ExecutionStatus
    artifact_sha256: str
    receipt_sha256: str = ""

    def payload(self) -> dict[str, object]:
        return {
            "schema": VERIFIED_RECEIPT_SCHEMA,
            "source_ref": self.source_ref,
            "source_head_sha": self.source_head_sha,
            "source_blob_sha": self.source_blob_sha,
            "evidence_sha256": self.evidence_sha256,
            "verifier_policy_sha256": self.verifier_policy_sha256,
            "execution_provider": self.execution_provider,
            "execution_run_id": self.execution_run_id,
            "executed_steps": self.executed_steps,
            "execution_status": self.execution_status.value,
            "artifact_sha256": self.artifact_sha256,
        }

    def computed_sha256(self) -> str:
        return sha256_hex(canonical_json_bytes(self.payload()))

    @classmethod
    def build(
        cls,
        *,
        source_ref: str,
        source_head_sha: str,
        source_blob_sha: str,
        evidence_sha256: str,
        verifier_policy_sha256: str,
        execution_provider: str,
        execution_run_id: str,
        executed_steps: int,
        execution_status: ExecutionStatus,
        artifact_sha256: str,
    ) -> "VerifiedWitnessReceiptV1":
        unsigned = cls(
            source_ref=source_ref,
            source_head_sha=source_head_sha,
            source_blob_sha=source_blob_sha,
            evidence_sha256=evidence_sha256,
            verifier_policy_sha256=verifier_policy_sha256,
            execution_provider=execution_provider,
            execution_run_id=execution_run_id,
            executed_steps=executed_steps,
            execution_status=execution_status,
            artifact_sha256=artifact_sha256,
        )
        return replace(unsigned, receipt_sha256=unsigned.computed_sha256())

    def validation_errors(self, witness: "Witness") -> tuple[str, ...]:
        errors: list[str] = []
        match = _SOURCE_REF.fullmatch(self.source_ref)
        if match is None:
            errors.append("SOURCE_REF_NOT_EXACT_REPO_HEAD_PATH")
        else:
            if match.group("head") != self.source_head_sha:
                errors.append("SOURCE_REF_HEAD_MISMATCH")
            if not match.group("path").strip():
                errors.append("SOURCE_REF_PATH_EMPTY")

        if _HEX40.fullmatch(self.source_head_sha) is None:
            errors.append("SOURCE_HEAD_SHA_INVALID")
        if _HEX40.fullmatch(self.source_blob_sha) is None:
            errors.append("SOURCE_BLOB_SHA_INVALID")
        if _HEX64.fullmatch(self.evidence_sha256) is None:
            errors.append("EVIDENCE_SHA256_INVALID")
        if _HEX64.fullmatch(self.verifier_policy_sha256) is None:
            errors.append("VERIFIER_POLICY_SHA256_INVALID")
        if _HEX64.fullmatch(self.artifact_sha256) is None:
            errors.append("ARTIFACT_SHA256_INVALID")
        if _HEX64.fullmatch(self.receipt_sha256) is None:
            errors.append("RECEIPT_SHA256_INVALID")
        elif self.receipt_sha256 != self.computed_sha256():
            errors.append("RECEIPT_SHA256_MISMATCH")

        if not self.execution_provider.strip():
            errors.append("EXECUTION_PROVIDER_REQUIRED")
        if not self.execution_run_id.strip():
            errors.append("EXECUTION_RUN_ID_REQUIRED")
        if type(self.executed_steps) is not int or self.executed_steps <= 0:
            errors.append("EXECUTED_STEPS_MUST_BE_POSITIVE")
        if self.execution_status is not ExecutionStatus.EXECUTED_PASS:
            errors.append("EXECUTION_STATUS_NOT_PASS")

        if witness.source_ref != self.source_ref:
            errors.append("WITNESS_SOURCE_REF_MISMATCH")
        if witness.evidence_sha256 != self.evidence_sha256:
            errors.append("WITNESS_EVIDENCE_SHA256_MISMATCH")
        return tuple(errors)

    def validates(self, witness: "Witness") -> bool:
        return not self.validation_errors(witness)


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
    verified_receipt: VerifiedWitnessReceiptV1 | None = None

    def provenance_complete(self) -> bool:
        if self.status is not WitnessStatus.VERIFIED:
            return False
        if self.verified_receipt is None:
            return False
        return self.verified_receipt.validates(self)

    def provenance_errors(self) -> tuple[str, ...]:
        if self.status is not WitnessStatus.VERIFIED:
            return ("WITNESS_NOT_VERIFIED",)
        if self.verified_receipt is None:
            return ("VERIFIED_RECEIPT_REQUIRED",)
        return self.verified_receipt.validation_errors(self)


@dataclass(frozen=True)
class CompilerPolicy:
    min_independent_groups: int = 2
    formal_kernel_required: bool = False
    positive_weight_ppm: int = PPM
    contrastive_weight_ppm: int = PPM
    admitted_verified_receipt_sha256s: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.min_independent_groups < 1:
            raise ValueError("MIN_INDEPENDENT_GROUPS_MUST_BE_POSITIVE")
        for value in (self.positive_weight_ppm, self.contrastive_weight_ppm):
            if not 0 <= value <= PPM:
                raise ValueError("WEIGHT_PPM_OUT_OF_RANGE")
        if len(self.admitted_verified_receipt_sha256s) != len(
            set(self.admitted_verified_receipt_sha256s)
        ):
            raise ValueError("ADMITTED_RECEIPT_SHA256S_MUST_BE_UNIQUE")
        for digest in self.admitted_verified_receipt_sha256s:
            if _HEX64.fullmatch(digest) is None:
                raise ValueError("ADMITTED_RECEIPT_SHA256_INVALID")


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
    admitted_receipts = set(policy.admitted_verified_receipt_sha256s)

    def receipt_admitted(w: Witness) -> bool:
        receipt = w.verified_receipt
        return (
            w.provenance_complete()
            and receipt is not None
            and receipt.receipt_sha256 in admitted_receipts
        )

    provenance_incomplete = [w for w in verified if not receipt_admitted(w)]
    verified_bound = [w for w in verified if receipt_admitted(w)]
    verified_groups = sorted({w.independence_group for w in verified_bound})
    formal_verified = any(w.formal_kernel for w in verified_bound)

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

    base_priority = {
        LearningDisposition.POSITIVE: 400_000,
        LearningDisposition.CONTRASTIVE_ONLY: 800_000,
        LearningDisposition.QUARANTINE: 200_000,
    }[disposition]
    sampling_priority = min(PPM, base_priority + volatility // 2)

    witness_rows = []
    for w in witnesses:
        receipt = w.verified_receipt
        witness_rows.append(
            {
                "name": w.name,
                "status": w.status.value,
                "independence_group": w.independence_group,
                "required": w.required,
                "formal_kernel": w.formal_kernel,
                "source_ref": w.source_ref,
                "evidence_sha256": w.evidence_sha256,
                "receipt_structurally_valid": w.provenance_complete(),
                "receipt_admitted": receipt_admitted(w)
                    if w.status is WitnessStatus.VERIFIED else False,
                "provenance_complete": receipt_admitted(w)
                    if w.status is WitnessStatus.VERIFIED else False,
                "provenance_errors": (
                    list(w.provenance_errors())
                    if not w.provenance_complete()
                    else ([] if receipt_admitted(w) else ["VERIFIED_RECEIPT_NOT_ADMITTED"])
                ) if w.status is WitnessStatus.VERIFIED else [],
                "verified_receipt_sha256": (
                    receipt.receipt_sha256 if receipt is not None else ""
                ),
                "executed_steps": (
                    receipt.executed_steps if receipt is not None else 0
                ),
                "execution_status": (
                    receipt.execution_status.value if receipt is not None else ""
                ),
                "failure_kind": w.failure_kind.value,
                "detail": w.detail,
            }
        )

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
        "admitted_verified_receipt_sha256s": sorted(admitted_receipts),
        "representation_sha256": sha256_hex(representation),
        "lz78_density_ppm": current_lz,
        "lz78_volatility_ppm": volatility,
        "witnesses": witness_rows,
        "metadata": dict(metadata or {}),
        "authority_effect": "NONE",
    }
    receipt["receipt_sha256"] = sha256_hex(canonical_json_bytes(receipt))
    return receipt