"""
AEGIS Ω — QuantumTourbillon Self-Witness-0.

Epistemic layer: L6_QUANTUM_DIAGNOSTICS.
Authority: NONE. Diagnostic evidence only.

The V1 differential contract is deliberately simulator-only:
`qpp-cpu` analytic expectation values are compared with the CUDA-Q `nvidia`
state-vector backend in FP64. Physical QPUs are shot-based and require a
separate statistical acceptance contract; V1 rejects them rather than silently
changing semantics.

There is no RNG, mock, mathematical fallback, or hard-coded purity metric in
this module. Missing CUDA-Q or unavailable targets fail closed with
BackendUnavailableException.
"""
from __future__ import annotations

import hashlib
import math
import re
import struct
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping

try:
    import rfc8785
except ImportError:  # optional contract dependency; checked before receipt emission
    rfc8785 = None

try:
    import cudaq
    from cudaq import spin

    CUDAQ_AVAILABLE = True
except ImportError:
    cudaq = None
    spin = None
    CUDAQ_AVAILABLE = False


PROTOCOL_VERSION = "QUANTUM_SELF_DIGEST_RECEIPT_V1"
MAPPING_VERSION = "SELF_HASH_U32_BE_TO_ANGLE_V1"
KERNEL_SPEC_VERSION = "SELF_WITNESS_4Q_RY_CZ_RING_RZ_V1"
OBSERVABLE_SET_VERSION = "SELF_WITNESS_OBSERVABLES_V1"
EPISTEMIC_LAYER = "L6_QUANTUM_DIAGNOSTICS"
AUTHORITY_CLASS = "NONE"
AUTHORITY_EFFECT = "NONE"
QUANTUM_PHYSICAL_ADVANTAGE = "NOT_ESTABLISHED"
RH_STATUS = "NOT_PROVEN"

OBSERVABLE_NAMES = (
    "Z0",
    "Z1",
    "Z2",
    "Z3",
    "Z0Z1",
    "Z2Z3",
    "X0X1X2X3",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_TWO_POW_32 = float(1 << 32)
_TWO_PI = 2.0 * math.pi
_TARGET_LOCK = threading.Lock()


class BackendUnavailableException(RuntimeError):
    """Requested CUDA-Q simulator/backend is not operational."""


class ProtocolViolation(RuntimeError):
    """Self-Witness-0 contract was violated; no valid receipt may be emitted."""


@dataclass(frozen=True)
class AngleEncoding:
    words_u32: tuple[int, ...]
    angles_rad: tuple[float, ...]


@dataclass(frozen=True)
class BackendSpec:
    target: str
    execution_mode: str = "ANALYTIC_STATEVECTOR"
    options: tuple[tuple[str, str], ...] = ()

    @classmethod
    def qpp_cpu(cls) -> "BackendSpec":
        return cls(target="qpp-cpu")

    @classmethod
    def nvidia_fp64(cls) -> "BackendSpec":
        return cls(target="nvidia", options=(("option", "fp64"),))

    def option_dict(self) -> dict[str, str]:
        return dict(self.options)

    def payload(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "execution_mode": self.execution_mode,
            "options": self.option_dict(),
        }


@dataclass(frozen=True)
class DifferentialGateTolerance:
    epsilon_max_abs_diff: float = 1e-5

    def __post_init__(self) -> None:
        if not math.isfinite(self.epsilon_max_abs_diff) or self.epsilon_max_abs_diff <= 0.0:
            raise ValueError("epsilon_max_abs_diff must be finite and > 0")


def _require_hash(name: str, value: str, pattern: re.Pattern[str]) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical lowercase hexadecimal")


def map_hash_to_angles(hex_hash: str) -> AngleEncoding:
    """Map one canonical 256-bit digest to eight angles in the half-open [0, 2π)."""
    _require_hash("self_hash", hex_hash, _HEX64)
    raw_bytes = bytes.fromhex(hex_hash)

    words: list[int] = []
    angles: list[float] = []
    for index in range(8):
        chunk = raw_bytes[index * 4 : (index + 1) * 4]
        word = struct.unpack(">I", chunk)[0]
        words.append(word)
        # Divide by 2^32, not 2^32-1. This guarantees max_u32 < 2π.
        angles.append((float(word) / _TWO_POW_32) * _TWO_PI)

    return AngleEncoding(tuple(words), tuple(angles))


def _rfc8785_bytes(payload: Any) -> bytes:
    if rfc8785 is None:
        raise ProtocolViolation("RFC8785 dependency unavailable")
    try:
        return rfc8785.dumps(payload)
    except Exception as exc:  # library raises CanonicalizationError subclasses
        raise ProtocolViolation(f"RFC8785 canonicalization failed: {exc}") from exc


def _sha256_jcs(payload: Any) -> str:
    return hashlib.sha256(_rfc8785_bytes(payload)).hexdigest()


KERNEL_SPEC: Mapping[str, Any] = {
    "version": KERNEL_SPEC_VERSION,
    "qubits": 4,
    "layer_1": ["RY(theta[0],q0)", "RY(theta[1],q1)", "RY(theta[2],q2)", "RY(theta[3],q3)"],
    "entangling_mesh": ["CZ(q0,q1)", "CZ(q1,q2)", "CZ(q2,q3)", "CZ(q3,q0)"],
    "layer_2": ["RZ(theta[4],q0)", "RZ(theta[5],q1)", "RZ(theta[6],q2)", "RZ(theta[7],q3)"],
}

MAPPING_SPEC: Mapping[str, Any] = {
    "version": MAPPING_VERSION,
    "input_bits": 256,
    "chunk_bits": 32,
    "chunk_count": 8,
    "endianness": "big",
    "denominator": 1 << 32,
    "range": "[0,2*pi)",
}

OBSERVABLE_SPEC: Mapping[str, Any] = {
    "version": OBSERVABLE_SET_VERSION,
    "observables": list(OBSERVABLE_NAMES),
}


if CUDAQ_AVAILABLE:

    @cudaq.kernel
    def self_witness_kernel(thetas: list[float]):
        q = cudaq.qvector(4)

        ry(thetas[0], q[0])
        ry(thetas[1], q[1])
        ry(thetas[2], q[2])
        ry(thetas[3], q[3])

        z.ctrl(q[0], q[1])
        z.ctrl(q[1], q[2])
        z.ctrl(q[2], q[3])
        z.ctrl(q[3], q[0])

        rz(thetas[4], q[0])
        rz(thetas[5], q[1])
        rz(thetas[6], q[2])
        rz(thetas[7], q[3])

else:
    self_witness_kernel = None


def _validate_observables(values: Mapping[str, float]) -> dict[str, float]:
    if set(values) != set(OBSERVABLE_NAMES):
        raise ProtocolViolation("observable set does not match Self-Witness-0 V1")

    normalized: dict[str, float] = {}
    for name in OBSERVABLE_NAMES:
        value = float(values[name])
        if not math.isfinite(value):
            raise ProtocolViolation(f"non-finite observable: {name}")
        if abs(value) > 1.0 + 1e-9:
            raise ProtocolViolation(f"observable outside Pauli expectation range: {name}")
        normalized[name] = value
    return normalized


def execute_observable_set(backend: BackendSpec, thetas: tuple[float, ...]) -> dict[str, float]:
    """Execute the fixed observable set on one analytic CUDA-Q simulator target."""
    if not CUDAQ_AVAILABLE or cudaq is None or spin is None or self_witness_kernel is None:
        raise BackendUnavailableException("BACKEND_UNAVAILABLE: CUDA-Q is not installed")
    if backend.execution_mode != "ANALYTIC_STATEVECTOR":
        raise ProtocolViolation("Self-Witness-0 V1 is simulator-only")

    try:
        if not cudaq.has_target(backend.target):
            raise BackendUnavailableException(
                f"BACKEND_UNAVAILABLE: CUDA-Q target {backend.target!r} is not registered"
            )
    except BackendUnavailableException:
        raise
    except Exception as exc:
        raise BackendUnavailableException(
            f"BACKEND_UNAVAILABLE: could not inspect CUDA-Q target {backend.target!r}: {exc}"
        ) from exc

    operators = [
        spin.z(0),
        spin.z(1),
        spin.z(2),
        spin.z(3),
        spin.z(0) * spin.z(1),
        spin.z(2) * spin.z(3),
        spin.x(0) * spin.x(1) * spin.x(2) * spin.x(3),
    ]

    with _TARGET_LOCK:
        try:
            cudaq.set_target(backend.target, **backend.option_dict())
            observed = cudaq.observe(
                self_witness_kernel,
                operators,
                list(thetas),
                shots_count=-1,
            )
            if not isinstance(observed, list):
                observed = [observed]
            if len(observed) != len(OBSERVABLE_NAMES):
                raise ProtocolViolation("CUDA-Q returned an unexpected observable count")
            values = {
                name: float(result.expectation())
                for name, result in zip(OBSERVABLE_NAMES, observed, strict=True)
            }
        except ProtocolViolation:
            raise
        except Exception as exc:
            raise BackendUnavailableException(
                f"BACKEND_UNAVAILABLE: execution on {backend.target!r} failed: {exc}"
            ) from exc
        finally:
            try:
                cudaq.reset_target()
            except Exception as exc:
                raise ProtocolViolation(f"CUDA-Q target reset failed: {exc}") from exc

    return _validate_observables(values)


Executor = Callable[[BackendSpec, tuple[float, ...]], Mapping[str, float]]


class SelfWitnessEngine:
    def __init__(
        self,
        tolerance: DifferentialGateTolerance = DifferentialGateTolerance(),
        executor: Executor | None = None,
    ) -> None:
        self.tolerance = tolerance
        self._executor: Executor = executor or execute_observable_set

    @staticmethod
    def _validate_v1_backends(backend_a: BackendSpec, backend_b: BackendSpec) -> None:
        if backend_a.execution_mode != "ANALYTIC_STATEVECTOR" or backend_b.execution_mode != "ANALYTIC_STATEVECTOR":
            raise ProtocolViolation("Self-Witness-0 V1 is simulator-only")
        if backend_a.target != "qpp-cpu":
            raise ProtocolViolation("Self-Witness-0 V1 reference target must be qpp-cpu")
        if backend_b.target != "nvidia":
            raise ProtocolViolation("Self-Witness-0 V1 comparison target must be nvidia; physical QPUs require V2")
        if backend_b.option_dict().get("option") != "fp64":
            raise ProtocolViolation("Self-Witness-0 V1 nvidia target must use fp64")

    def run_witness_cycle(
        self,
        self_hash: str,
        *,
        source_sha: str,
        self_hash_algorithm: str = "SHA-256",
        backend_a: BackendSpec | None = None,
        backend_b: BackendSpec | None = None,
    ) -> dict[str, Any]:
        """Execute and bind one diagnostic CPU↔GPU differential witness receipt."""
        _require_hash("source_sha", source_sha, _HEX40)
        if self_hash_algorithm not in {"SHA-256", "BLAKE3-256"}:
            raise ValueError("self_hash_algorithm must be SHA-256 or BLAKE3-256")

        a = backend_a or BackendSpec.qpp_cpu()
        b = backend_b or BackendSpec.nvidia_fp64()
        self._validate_v1_backends(a, b)

        encoding = map_hash_to_angles(self_hash)
        obs_a = _validate_observables(self._executor(a, encoding.angles_rad))
        obs_b = _validate_observables(self._executor(b, encoding.angles_rad))

        discrepancies = {
            name: abs(obs_a[name] - obs_b[name])
            for name in OBSERVABLE_NAMES
        }
        max_discrepancy = max(discrepancies.values(), default=0.0)
        differential_pass = max_discrepancy <= self.tolerance.epsilon_max_abs_diff

        kernel_spec_digest = _sha256_jcs(KERNEL_SPEC)
        mapping_spec_digest = _sha256_jcs(MAPPING_SPEC)
        observable_spec_digest = _sha256_jcs(OBSERVABLE_SPEC)

        execution_payload = {
            "source_sha": source_sha,
            "self_hash": self_hash,
            "self_hash_algorithm": self_hash_algorithm,
            "theta_words_u32": list(encoding.words_u32),
            "thetas_rad": list(encoding.angles_rad),
            "backend_a": a.payload(),
            "backend_b": b.payload(),
            "observables_a": obs_a,
            "observables_b": obs_b,
            "kernel_spec_digest": kernel_spec_digest,
            "mapping_spec_digest": mapping_spec_digest,
            "observable_spec_digest": observable_spec_digest,
        }
        execution_digest = _sha256_jcs(execution_payload)

        receipt_payload: dict[str, Any] = {
            "protocol_version": PROTOCOL_VERSION,
            "epistemic_layer": EPISTEMIC_LAYER,
            "source_sha": source_sha,
            "self_hash": self_hash,
            "self_hash_algorithm": self_hash_algorithm,
            "mapping_version": MAPPING_VERSION,
            "mapping_spec_digest": mapping_spec_digest,
            "theta_words_u32": list(encoding.words_u32),
            "thetas_rad": list(encoding.angles_rad),
            "kernel_spec_version": KERNEL_SPEC_VERSION,
            "kernel_spec_digest": kernel_spec_digest,
            "observable_set_version": OBSERVABLE_SET_VERSION,
            "observable_spec_digest": observable_spec_digest,
            "backend_a": a.target,
            "backend_a_config": a.payload(),
            "backend_b": b.target,
            "backend_b_config": b.payload(),
            "observables_a": obs_a,
            "observables_b": obs_b,
            "discrepancies": discrepancies,
            "max_discrepancy": max_discrepancy,
            "tolerance_epsilon": self.tolerance.epsilon_max_abs_diff,
            "differential_gate_status": "PASS" if differential_pass else "FAIL",
            "execution_digest": execution_digest,
            "receipt_canonicalization": "RFC8785",
            "receipt_digest_algorithm": "SHA-256",
            "authority_class": AUTHORITY_CLASS,
            "authority_effect": AUTHORITY_EFFECT,
            "quantum_physical_advantage": QUANTUM_PHYSICAL_ADVANTAGE,
            "rh_status": RH_STATUS,
        }

        receipt_digest = hashlib.sha256(_rfc8785_bytes(receipt_payload)).hexdigest()
        return {"receipt_digest": receipt_digest, "receipt": receipt_payload}
