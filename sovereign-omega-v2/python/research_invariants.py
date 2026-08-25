"""
AEGIS Ω — Zero-Discretion Type Gates v1.

Research invariants are triggered mechanically from declared object types.
A generator may choose a construction; it may not curate which registered
falsifiers the construction must survive.

This module is deliberately separate from gate.py (mutation authority).
It governs mathematical/research admission, not runtime mutation voting.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "AEGIS_ZERO_DISCRETION_TYPE_GATES_V1"

TYPE_GATE_REGISTRY: Mapping[str, tuple[str, ...]] = {
    "DiscretizedSpectralBasisV1": ("spectral-domain-coverage",),
    "OperatorDecompositionV1": ("operator-decomposition-conservation",),
    "RealSkewSymmetricMatrixV1": ("skew-quadratic-identity",),
    "CombinatorialLaplacianV1": ("laplacian-kernel-one",),
    "LinearDualCertificateV1": ("dual-certificate-kkt",),
    "ExponentialAsymptoticFamilyV1": ("exponential-asymptotic-nonvanishing",),
}


def required_gates_for_type(type_signature: str) -> tuple[str, ...]:
    try:
        return TYPE_GATE_REGISTRY[type_signature]
    except KeyError as exc:
        raise KeyError(f"unregistered research object type: {type_signature}") from exc


class GateVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class ResearchStatus(str, Enum):
    CONJECTURED = "CONJECTURED"
    TYPE_CHECKED = "TYPE_CHECKED"
    COMPUTED = "COMPUTED"
    THEOREM = "THEOREM"


def freeze_hash_material(value: Any) -> Any:
    """Recursively detach and freeze material after/before deterministic hashing."""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(k): freeze_hash_material(value[k]) for k in sorted(value)}
        )
    if isinstance(value, (tuple, list)):
        return tuple(freeze_hash_material(v) for v in value)
    if isinstance(value, Enum):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats are not admissible in gate material")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported gate material type: {type(value)!r}")


def _canonical(value: Any) -> Any:
    """Canonical JSON-safe representation; float.hex avoids repr drift."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats are not admissible in gate material")
        return {"__float_hex__": value.hex()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_canonical(v) for v in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported gate material type: {type(value)!r}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def literal_sha256(text: str) -> str:
    """Hash exact UTF-8 bytes. No whitespace normalization by design."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_digest(digest: str, field_name: str) -> None:
    if len(digest) != 64:
        raise ValueError(f"{field_name} must be a 64-hex SHA-256 digest")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a 64-hex SHA-256 digest") from exc


def _shape(matrix: Sequence[Sequence[float]]) -> tuple[int, int]:
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    if any(len(row) != cols for row in matrix):
        raise ValueError("matrix rows must have equal length")
    return rows, cols


def _fro_norm(matrix: Sequence[Sequence[float]]) -> float:
    return math.sqrt(sum(float(v) * float(v) for row in matrix for v in row))


def _sub_matrix(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
) -> list[list[float]]:
    if _shape(left) != _shape(right):
        raise ValueError("matrix shapes differ")
    return [
        [float(a) - float(b) for a, b in zip(lrow, rrow)]
        for lrow, rrow in zip(left, right)
    ]


def _add_matrix(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
) -> list[list[float]]:
    if _shape(left) != _shape(right):
        raise ValueError("matrix shapes differ")
    return [
        [float(a) + float(b) for a, b in zip(lrow, rrow)]
        for lrow, rrow in zip(left, right)
    ]


def _transpose(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    rows, cols = _shape(matrix)
    return [[float(matrix[i][j]) for i in range(rows)] for j in range(cols)]


def _matvec(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
) -> list[float]:
    rows, cols = _shape(matrix)
    if cols != len(vector):
        raise ValueError("matrix/vector dimensions differ")
    return [
        sum(float(matrix[i][j]) * float(vector[j]) for j in range(cols))
        for i in range(rows)
    ]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vector dimensions differ")
    return sum(float(a) * float(b) for a, b in zip(left, right))


@dataclass(frozen=True)
class GateReceipt:
    gate_id: str
    gate_version: str
    type_signature: str
    object_digest: str
    verdict: GateVerdict
    observation: Mapping[str, Any]
    witness_sha256: str
    elapsed_ns: int

    def __post_init__(self) -> None:
        _check_digest(self.object_digest, "object_digest")
        _check_digest(self.witness_sha256, "witness_sha256")
        if self.elapsed_ns < 0:
            raise ValueError("elapsed_ns must be non-negative")
        object.__setattr__(self, "observation", freeze_hash_material(self.observation))

    def deterministic_material(self) -> Mapping[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "gate_id": self.gate_id,
            "gate_version": self.gate_version,
            "type_signature": self.type_signature,
            "object_digest": self.object_digest,
            "verdict": self.verdict.value,
            "observation": self.observation,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.deterministic_material())
        payload["observation"] = _canonical(self.observation)
        payload["witness_sha256"] = self.witness_sha256
        payload["elapsed_ns"] = self.elapsed_ns
        return payload


class InvariantViolationError(RuntimeError):
    def __init__(self, receipt: GateReceipt):
        self.receipt = receipt
        super().__init__(
            f"{receipt.gate_id} {receipt.verdict.value}: "
            f"{json.dumps(_canonical(receipt.observation), sort_keys=True)}"
        )


def _receipt(
    *,
    gate_id: str,
    type_signature: str,
    object_digest: str,
    verdict: GateVerdict,
    observation: Mapping[str, Any],
    started_ns: int,
    gate_version: str = "1",
) -> GateReceipt:
    frozen_observation = freeze_hash_material(observation)
    deterministic = {
        "schema": SCHEMA_VERSION,
        "gate_id": gate_id,
        "gate_version": gate_version,
        "type_signature": type_signature,
        "object_digest": object_digest,
        "verdict": verdict.value,
        "observation": frozen_observation,
    }
    return GateReceipt(
        gate_id=gate_id,
        gate_version=gate_version,
        type_signature=type_signature,
        object_digest=object_digest,
        verdict=verdict,
        observation=frozen_observation,
        witness_sha256=sha256_hex(deterministic),
        elapsed_ns=max(0, time.perf_counter_ns() - started_ns),
    )


def _raise_unless_pass(receipt: GateReceipt) -> GateReceipt:
    if receipt.verdict is not GateVerdict.PASS:
        raise InvariantViolationError(receipt)
    return receipt


def spectral_coverage_gate(
    n_f: int,
    h: float,
    target_gamma_max: float,
) -> GateReceipt:
    """
    Type trigger:
      DiscretizedSpectralBasis(N_F, h, target_gamma_max)
        -> N_F*pi/h >= target_gamma_max

    The formula is a registered convention of this nominal type, not inferred
    from an arbitrary object named "spectral".
    """
    started = time.perf_counter_ns()
    material = {
        "n_f": n_f,
        "h": h,
        "target_gamma_max": target_gamma_max,
        "cutoff_convention": "N_F*pi/h",
    }
    object_digest = sha256_hex(material)
    try:
        if n_f <= 0 or h <= 0.0 or target_gamma_max < 0.0:
            return _receipt(
                gate_id="spectral-domain-coverage",
                type_signature="DiscretizedSpectralBasisV1",
                object_digest=object_digest,
                verdict=GateVerdict.ERROR,
                observation={"reason": "invalid-domain-parameters"},
                started_ns=started,
            )
        cutoff = n_f * math.pi / h
        verdict = GateVerdict.PASS if cutoff >= target_gamma_max else GateVerdict.FAIL
        return _receipt(
            gate_id="spectral-domain-coverage",
            type_signature="DiscretizedSpectralBasisV1",
            object_digest=object_digest,
            verdict=verdict,
            observation={
                "n_f": n_f,
                "h": h,
                "cutoff": cutoff,
                "target_gamma_max": target_gamma_max,
                "margin": cutoff - target_gamma_max,
            },
            started_ns=started,
        )
    except Exception as exc:
        return _receipt(
            gate_id="spectral-domain-coverage",
            type_signature="DiscretizedSpectralBasisV1",
            object_digest=object_digest,
            verdict=GateVerdict.ERROR,
            observation={"reason": type(exc).__name__, "message": str(exc)},
            started_ns=started,
        )


def operator_decomposition_gate(
    operator: Sequence[Sequence[float]],
    parts: Sequence[Sequence[Sequence[float]]],
    tolerance: float,
) -> GateReceipt:
    started = time.perf_counter_ns()
    material = {"operator": operator, "parts": parts, "tolerance": tolerance}
    object_digest = sha256_hex(material)
    try:
        rows, cols = _shape(operator)
        if tolerance < 0.0:
            raise ValueError("tolerance must be non-negative")
        total = [[0.0 for _ in range(cols)] for _ in range(rows)]
        for part in parts:
            if _shape(part) != (rows, cols):
                raise ValueError("decomposition part shape mismatch")
            for i in range(rows):
                for j in range(cols):
                    total[i][j] += float(part[i][j])
        residual = _fro_norm(_sub_matrix(total, operator))
        verdict = GateVerdict.PASS if residual <= tolerance else GateVerdict.FAIL
        return _receipt(
            gate_id="operator-decomposition-conservation",
            type_signature="OperatorDecompositionV1",
            object_digest=object_digest,
            verdict=verdict,
            observation={
                "residual_fro": residual,
                "tolerance": tolerance,
                "part_count": len(parts),
                "shape": [rows, cols],
            },
            started_ns=started,
        )
    except Exception as exc:
        return _receipt(
            gate_id="operator-decomposition-conservation",
            type_signature="OperatorDecompositionV1",
            object_digest=object_digest,
            verdict=GateVerdict.ERROR,
            observation={"reason": type(exc).__name__, "message": str(exc)},
            started_ns=started,
        )


def skew_quadratic_gate(
    matrix: Sequence[Sequence[float]],
    witness_vectors: Sequence[Sequence[float]] = (),
    tolerance: float = 0.0,
) -> GateReceipt:
    """
    Validate A^T = -A numerically and, when witnesses are supplied, check x^T A x.
    For an exact real skew-symmetric matrix the latter is identically zero.
    """
    started = time.perf_counter_ns()
    material = {
        "matrix": matrix,
        "witness_vectors": witness_vectors,
        "tolerance": tolerance,
    }
    object_digest = sha256_hex(material)
    try:
        rows, cols = _shape(matrix)
        if rows != cols:
            raise ValueError("skew-symmetric matrix must be square")
        if tolerance < 0.0:
            raise ValueError("tolerance must be non-negative")

        skew_residual = _fro_norm(_add_matrix(matrix, _transpose(matrix)))
        values: list[float] = []
        for vector in witness_vectors:
            if len(vector) != rows:
                raise ValueError("witness vector dimension mismatch")
            values.append(_dot(vector, _matvec(matrix, vector)))
        max_abs_quadratic = max((abs(v) for v in values), default=0.0)

        verdict = (
            GateVerdict.PASS
            if skew_residual <= tolerance and max_abs_quadratic <= tolerance
            else GateVerdict.FAIL
        )
        return _receipt(
            gate_id="skew-quadratic-identity",
            type_signature="RealSkewSymmetricMatrixV1",
            object_digest=object_digest,
            verdict=verdict,
            observation={
                "skew_residual_fro": skew_residual,
                "max_abs_xTAx": max_abs_quadratic,
                "witness_count": len(values),
                "tolerance": tolerance,
            },
            started_ns=started,
        )
    except Exception as exc:
        return _receipt(
            gate_id="skew-quadratic-identity",
            type_signature="RealSkewSymmetricMatrixV1",
            object_digest=object_digest,
            verdict=GateVerdict.ERROR,
            observation={"reason": type(exc).__name__, "message": str(exc)},
            started_ns=started,
        )


def laplacian_kernel_gate(
    laplacian: Sequence[Sequence[float]],
    tolerance: float = 0.0,
) -> GateReceipt:
    started = time.perf_counter_ns()
    material = {"laplacian": laplacian, "tolerance": tolerance}
    object_digest = sha256_hex(material)
    try:
        rows, cols = _shape(laplacian)
        if rows != cols:
            raise ValueError("laplacian must be square")
        if tolerance < 0.0:
            raise ValueError("tolerance must be non-negative")
        residual_vector = _matvec(laplacian, [1.0] * cols)
        residual_inf = max((abs(v) for v in residual_vector), default=0.0)
        verdict = GateVerdict.PASS if residual_inf <= tolerance else GateVerdict.FAIL
        return _receipt(
            gate_id="laplacian-kernel-one",
            type_signature="CombinatorialLaplacianV1",
            object_digest=object_digest,
            verdict=verdict,
            observation={
                "residual_inf": residual_inf,
                "tolerance": tolerance,
                "dimension": rows,
            },
            started_ns=started,
        )
    except Exception as exc:
        return _receipt(
            gate_id="laplacian-kernel-one",
            type_signature="CombinatorialLaplacianV1",
            object_digest=object_digest,
            verdict=GateVerdict.ERROR,
            observation={"reason": type(exc).__name__, "message": str(exc)},
            started_ns=started,
        )


def dual_certificate_gate(
    a_matrix: Sequence[Sequence[float]],
    y: Sequence[float],
    c: Sequence[float],
    primal_objective: float,
    dual_objective: float,
    residual_tolerance: float = 1e-12,
    gap_tolerance: float = 1e-12,
) -> GateReceipt:
    """
    Verify a supplied dual certificate. Complexity scales with certificate size;
    it is verification, not an optimization solve.
    """
    started = time.perf_counter_ns()
    material = {
        "a_matrix": a_matrix,
        "y": y,
        "c": c,
        "primal_objective": primal_objective,
        "dual_objective": dual_objective,
        "residual_tolerance": residual_tolerance,
        "gap_tolerance": gap_tolerance,
    }
    object_digest = sha256_hex(material)
    try:
        rows, cols = _shape(a_matrix)
        if len(y) != rows or len(c) != cols:
            raise ValueError("dual certificate dimensions differ")
        aty = _matvec(_transpose(a_matrix), y)
        residual_inf = max(
            (abs(float(lhs) - float(rhs)) for lhs, rhs in zip(aty, c)),
            default=0.0,
        )
        min_y = min((float(v) for v in y), default=0.0)
        gap = abs(float(primal_objective) - float(dual_objective))
        verdict = (
            GateVerdict.PASS
            if residual_inf <= residual_tolerance
            and min_y >= -residual_tolerance
            and gap <= gap_tolerance
            else GateVerdict.FAIL
        )
        return _receipt(
            gate_id="dual-certificate-kkt",
            type_signature="LinearDualCertificateV1",
            object_digest=object_digest,
            verdict=verdict,
            observation={
                "residual_inf": residual_inf,
                "min_y": min_y,
                "duality_gap": gap,
                "residual_tolerance": residual_tolerance,
                "gap_tolerance": gap_tolerance,
            },
            started_ns=started,
        )
    except Exception as exc:
        return _receipt(
            gate_id="dual-certificate-kkt",
            type_signature="LinearDualCertificateV1",
            object_digest=object_digest,
            verdict=GateVerdict.ERROR,
            observation={"reason": type(exc).__name__, "message": str(exc)},
            started_ns=started,
        )


def exponential_asymptotic_gate(
    amplitude: float,
    exponential_rate: float,
    claimed_uniform_lower_bound: float,
) -> GateReceipt:
    """
    Registered narrow asymptotic family:
        f(h) ~ amplitude * exp(exponential_rate * h).

    A positive uniform lower bound is structurally incompatible with a finite,
    positive amplitude and negative exponential rate. This does NOT pretend to
    decide arbitrary asymptotics.
    """
    started = time.perf_counter_ns()
    material = {
        "family": "amplitude*exp(rate*h)",
        "amplitude": amplitude,
        "exponential_rate": exponential_rate,
        "claimed_uniform_lower_bound": claimed_uniform_lower_bound,
    }
    object_digest = sha256_hex(material)
    try:
        if amplitude < 0.0 or claimed_uniform_lower_bound < 0.0:
            raise ValueError("amplitude and lower bound must be non-negative")
        contradiction = (
            claimed_uniform_lower_bound > 0.0
            and amplitude > 0.0
            and exponential_rate < 0.0
        )
        return _receipt(
            gate_id="exponential-asymptotic-nonvanishing",
            type_signature="ExponentialAsymptoticFamilyV1",
            object_digest=object_digest,
            verdict=GateVerdict.FAIL if contradiction else GateVerdict.PASS,
            observation={
                "amplitude": amplitude,
                "exponential_rate": exponential_rate,
                "claimed_uniform_lower_bound": claimed_uniform_lower_bound,
                "contradiction": contradiction,
            },
            started_ns=started,
        )
    except Exception as exc:
        return _receipt(
            gate_id="exponential-asymptotic-nonvanishing",
            type_signature="ExponentialAsymptoticFamilyV1",
            object_digest=object_digest,
            verdict=GateVerdict.ERROR,
            observation={"reason": type(exc).__name__, "message": str(exc)},
            started_ns=started,
        )


@dataclass(frozen=True)
class SpectralBasis:
    n_f: int
    h: float
    target_gamma_max: float
    gate_receipts: tuple[GateReceipt, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        receipt = _raise_unless_pass(
            spectral_coverage_gate(self.n_f, self.h, self.target_gamma_max)
        )
        object.__setattr__(self, "gate_receipts", (receipt,))

    @property
    def nyquist_cutoff(self) -> float:
        return self.n_f * math.pi / self.h

    @property
    def object_digest(self) -> str:
        return self.gate_receipts[0].object_digest


@dataclass(frozen=True)
class OperatorDecomposition:
    operator: Sequence[Sequence[float]]
    parts: Sequence[Sequence[Sequence[float]]]
    tolerance: float
    gate_receipts: tuple[GateReceipt, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        receipt = _raise_unless_pass(
            operator_decomposition_gate(self.operator, self.parts, self.tolerance)
        )
        object.__setattr__(self, "gate_receipts", (receipt,))


@dataclass(frozen=True)
class CriterionEpoch:
    criterion_text: str
    criterion_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "criterion_sha256", literal_sha256(self.criterion_text))

    def same_epoch_as(self, other: "CriterionEpoch") -> bool:
        return self.criterion_sha256 == other.criterion_sha256


@dataclass(frozen=True)
class AdmissionTicket:
    stage_id: str
    subject_digest: str
    required_gate_ids: tuple[str, ...]
    receipt_digests: tuple[str, ...]
    ticket_sha256: str


class AdmissionController:
    """
    Fail-closed stage admission. Missing, FAIL, ERROR, stale-subject, or duplicate
    required receipts block admission.
    """

    @staticmethod
    def admit(
        *,
        stage_id: str,
        subject_digest: str,
        required_gate_ids: Iterable[str],
        receipts: Sequence[GateReceipt],
    ) -> AdmissionTicket:
        _check_digest(subject_digest, "subject_digest")
        required = tuple(sorted(set(required_gate_ids)))
        by_id: dict[str, GateReceipt] = {}
        for receipt in receipts:
            if receipt.gate_id in by_id:
                raise ValueError(f"duplicate receipt for gate {receipt.gate_id}")
            by_id[receipt.gate_id] = receipt

        missing = [gate_id for gate_id in required if gate_id not in by_id]
        if missing:
            raise PermissionError(f"missing required gate receipts: {missing}")

        for gate_id in required:
            receipt = by_id[gate_id]
            if receipt.verdict is not GateVerdict.PASS:
                raise PermissionError(
                    f"gate {gate_id} is {receipt.verdict.value}; stage blocked"
                )
            if receipt.object_digest != subject_digest:
                raise PermissionError(
                    f"stale/spliced receipt for {gate_id}: subject digest mismatch"
                )

        receipt_digests = tuple(by_id[gate_id].witness_sha256 for gate_id in required)
        material = {
            "schema": "AEGIS_RESEARCH_ADMISSION_TICKET_V1",
            "stage_id": stage_id,
            "subject_digest": subject_digest,
            "required_gate_ids": required,
            "receipt_digests": receipt_digests,
        }
        return AdmissionTicket(
            stage_id=stage_id,
            subject_digest=subject_digest,
            required_gate_ids=required,
            receipt_digests=receipt_digests,
            ticket_sha256=sha256_hex(material),
        )


@dataclass(frozen=True)
class StatusRecord:
    claim_id: str
    status: ResearchStatus
    evidence_sha256: str | None = None
    criterion_sha256: str | None = None
    n: int | None = None
    tolerance: float | None = None
    verifier_id: str | None = None

    @classmethod
    def conjectured(cls, claim_id: str) -> "StatusRecord":
        return cls(claim_id=claim_id, status=ResearchStatus.CONJECTURED)

    @classmethod
    def type_checked(
        cls,
        claim_id: str,
        receipts: Sequence[GateReceipt],
    ) -> "StatusRecord":
        if not receipts:
            raise ValueError("TYPE_CHECKED requires at least one gate receipt")
        if any(r.verdict is not GateVerdict.PASS for r in receipts):
            raise ValueError("TYPE_CHECKED requires only PASS receipts")
        digest = sha256_hex([r.deterministic_material() for r in receipts])
        return cls(
            claim_id=claim_id,
            status=ResearchStatus.TYPE_CHECKED,
            evidence_sha256=digest,
            verifier_id=SCHEMA_VERSION,
        )

    @classmethod
    def computed(
        cls,
        *,
        claim_id: str,
        output_sha256: str,
        criterion_epoch: CriterionEpoch,
        n: int,
        tolerance: float,
        verifier_id: str,
    ) -> "StatusRecord":
        _check_digest(output_sha256, "output_sha256")
        if n <= 0:
            raise ValueError("COMPUTED requires n > 0")
        if tolerance < 0.0:
            raise ValueError("COMPUTED requires tolerance >= 0")
        if not verifier_id:
            raise ValueError("COMPUTED requires verifier_id")
        return cls(
            claim_id=claim_id,
            status=ResearchStatus.COMPUTED,
            evidence_sha256=output_sha256,
            criterion_sha256=criterion_epoch.criterion_sha256,
            n=n,
            tolerance=tolerance,
            verifier_id=verifier_id,
        )

    @classmethod
    def theorem(
        cls,
        *,
        claim_id: str,
        proof_sha256: str,
        checker_receipt_sha256: str,
        verifier_id: str,
    ) -> "StatusRecord":
        """
        THEOREM is not a prose label. It requires both a proof artifact digest
        and an independent checker receipt digest.
        """
        _check_digest(proof_sha256, "proof_sha256")
        _check_digest(checker_receipt_sha256, "checker_receipt_sha256")
        if not verifier_id:
            raise ValueError("THEOREM requires verifier_id")
        combined = sha256_hex(
            {
                "proof_sha256": proof_sha256,
                "checker_receipt_sha256": checker_receipt_sha256,
                "verifier_id": verifier_id,
            }
        )
        return cls(
            claim_id=claim_id,
            status=ResearchStatus.THEOREM,
            evidence_sha256=combined,
            verifier_id=verifier_id,
        )


@dataclass(frozen=True)
class RelationBindingV1:
    relation_id: str
    participants: Mapping[str, str]
    relation_digest: str


def bind_relation(relation_id: str, participants: Mapping[str, str]) -> RelationBindingV1:
    """Bind a late relation to role-sensitive participant digests."""
    if not relation_id:
        raise ValueError("relation_id must be non-empty")
    if not participants:
        raise ValueError("relation requires at least one participant")
    normalized: dict[str, str] = {}
    for raw_role, digest in participants.items():
        role = str(raw_role)
        if not role:
            raise ValueError("relation participant role must be non-empty")
        _check_digest(digest, f"participant[{role}]")
        normalized[role] = digest
    frozen_participants = freeze_hash_material(dict(sorted(normalized.items())))
    material = {
        "schema": "AEGIS_RELATION_BINDING_V1",
        "relation_id": relation_id,
        "participants": frozen_participants,
    }
    return RelationBindingV1(
        relation_id=relation_id,
        participants=frozen_participants,
        relation_digest=sha256_hex(material),
    )


def relation_gate_receipt(
    *,
    gate_id: str,
    relation: RelationBindingV1,
    verdict: GateVerdict,
    observation: Mapping[str, Any],
    gate_version: str = "1",
) -> GateReceipt:
    """Reuse GateReceipt for a late-bound relation; no second authority type."""
    return _receipt(
        gate_id=gate_id,
        type_signature="RelationBindingV1",
        object_digest=relation.relation_digest,
        verdict=verdict,
        observation=observation,
        started_ns=time.perf_counter_ns(),
        gate_version=gate_version,
    )


@dataclass(frozen=True)
class StatusTransitionV1:
    claim_id: str
    previous_status: str | None
    next_status: str
    evidence_receipt_digests: tuple[str, ...]
    criterion_sha256: str | None
    reason: str
    previous_transition_sha256: str | None
    transition_sha256: str


class StatusJournalV1:
    """Append-only hash-chained status history supporting explicit demotion."""

    def __init__(self, claim_id: str):
        if not claim_id:
            raise ValueError("claim_id must be non-empty")
        self._claim_id = claim_id
        self._history: list[StatusTransitionV1] = []

    @property
    def history(self) -> tuple[StatusTransitionV1, ...]:
        return tuple(self._history)

    @property
    def current_status(self) -> str | None:
        return self._history[-1].next_status if self._history else None

    @staticmethod
    def _material(
        *,
        claim_id: str,
        previous_status: str | None,
        next_status: str,
        evidence_receipt_digests: Sequence[str],
        criterion_sha256: str | None,
        reason: str,
        previous_transition_sha256: str | None,
    ) -> Mapping[str, Any]:
        return {
            "schema": "AEGIS_STATUS_TRANSITION_V1",
            "claim_id": claim_id,
            "previous_status": previous_status,
            "next_status": next_status,
            "evidence_receipt_digests": tuple(evidence_receipt_digests),
            "criterion_sha256": criterion_sha256,
            "reason": reason,
            "previous_transition_sha256": previous_transition_sha256,
        }

    def append(
        self,
        next_status: str,
        evidence_receipt_digests: Sequence[str],
        criterion_sha256: str | None,
        reason: str,
    ) -> StatusTransitionV1:
        if not next_status:
            raise ValueError("next_status must be non-empty")
        if not reason:
            raise ValueError("reason must be non-empty")
        evidence = tuple(evidence_receipt_digests)
        for digest in evidence:
            _check_digest(digest, "evidence_receipt_digest")
        if criterion_sha256 is not None:
            _check_digest(criterion_sha256, "criterion_sha256")
        previous = self._history[-1] if self._history else None
        previous_status = previous.next_status if previous else None
        previous_sha = previous.transition_sha256 if previous else None
        material = self._material(
            claim_id=self._claim_id,
            previous_status=previous_status,
            next_status=next_status,
            evidence_receipt_digests=evidence,
            criterion_sha256=criterion_sha256,
            reason=reason,
            previous_transition_sha256=previous_sha,
        )
        transition = StatusTransitionV1(
            claim_id=self._claim_id,
            previous_status=previous_status,
            next_status=next_status,
            evidence_receipt_digests=evidence,
            criterion_sha256=criterion_sha256,
            reason=reason,
            previous_transition_sha256=previous_sha,
            transition_sha256=sha256_hex(material),
        )
        self._history.append(transition)
        return transition

    @classmethod
    def verify(cls, history: Sequence[StatusTransitionV1]) -> bool:
        previous: StatusTransitionV1 | None = None
        try:
            for transition in history:
                if not transition.claim_id or not transition.next_status or not transition.reason:
                    return False
                for digest in transition.evidence_receipt_digests:
                    _check_digest(digest, "evidence_receipt_digest")
                if transition.criterion_sha256 is not None:
                    _check_digest(transition.criterion_sha256, "criterion_sha256")
                expected_previous_status = previous.next_status if previous else None
                expected_previous_sha = previous.transition_sha256 if previous else None
                if transition.previous_status != expected_previous_status:
                    return False
                if transition.previous_transition_sha256 != expected_previous_sha:
                    return False
                if previous is not None and transition.claim_id != previous.claim_id:
                    return False
                material = cls._material(
                    claim_id=transition.claim_id,
                    previous_status=transition.previous_status,
                    next_status=transition.next_status,
                    evidence_receipt_digests=transition.evidence_receipt_digests,
                    criterion_sha256=transition.criterion_sha256,
                    reason=transition.reason,
                    previous_transition_sha256=transition.previous_transition_sha256,
                )
                if sha256_hex(material) != transition.transition_sha256:
                    return False
                previous = transition
            return True
        except (TypeError, ValueError):
            return False
