"""
QuantumTourbillon — deterministic multi-perspective verification carousel (MPVC).

Status: ARCHITECTURAL_HYPOTHESIS. QUANTUM_PHYSICAL_ADVANTAGE = NOT_ESTABLISHED.
RH = NOT_PROVEN. The Grover path is T1_DIAGNOSTIC and has zero admission authority.

Admission invariant:
    ADMITTED iff exactly one provenance-coherent PASS receipt exists for each
    mandatory gate P1..P4 and every mandatory receipt has its fixed authority.

Any mandatory FAIL or receipt-integrity/provenance violation -> QUARANTINED.
Missing, UNKNOWN, or UNAVAILABLE mandatory evidence -> UNKNOWN.
OPEN and T1_DIAGNOSTIC receipts are retained in the receipt chain but never vote.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import blake3

__all__ = [
    "AuthorityLevel",
    "ClaimResolution",
    "ClaimState",
    "DiagnosticOracleRegistry",
    "GroverDiagnostic",
    "MANDATORY_GATES",
    "PERSPECTIVE_AUTHORITY",
    "Perspective",
    "PerspectiveOutcome",
    "PerspectiveReceipt",
    "QuantumPerspectiveCarousel",
    "RECEIPT_VERSION",
    "canonical_bytes",
    "resolve_claim",
]

RECEIPT_VERSION = "1.1.0"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PerspectiveOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


class ClaimState(str, Enum):
    ADMITTED = "ADMITTED"
    QUARANTINED = "QUARANTINED"
    UNKNOWN = "UNKNOWN"


class AuthorityLevel(str, Enum):
    ADMISSION_GATE = "ADMISSION_GATE"
    STRUCTURAL_GATE = "STRUCTURAL_GATE"
    BOUNDED_FALSIFICATION = "BOUNDED_FALSIFICATION"
    OPEN = "OPEN"
    T1_DIAGNOSTIC = "T1_DIAGNOSTIC"


class Perspective(str, Enum):
    P1_COQ_KERNEL = "P1_COQ_KERNEL"
    P2_EXACT_HEAD = "P2_EXACT_HEAD"
    P3_DEPENDENCY_GRAPH = "P3_DEPENDENCY_GRAPH"
    P4_ARITHMETIC_BOUND = "P4_ARITHMETIC_BOUND"
    P5_WEIL_DUALITY = "P5_WEIL_DUALITY"
    P_QUANTUM_GROVER = "P_QUANTUM_GROVER"


PERSPECTIVE_AUTHORITY: Mapping[Perspective, AuthorityLevel] = MappingProxyType({
    Perspective.P1_COQ_KERNEL: AuthorityLevel.ADMISSION_GATE,
    Perspective.P2_EXACT_HEAD: AuthorityLevel.ADMISSION_GATE,
    Perspective.P3_DEPENDENCY_GRAPH: AuthorityLevel.STRUCTURAL_GATE,
    Perspective.P4_ARITHMETIC_BOUND: AuthorityLevel.BOUNDED_FALSIFICATION,
    Perspective.P5_WEIL_DUALITY: AuthorityLevel.OPEN,
    Perspective.P_QUANTUM_GROVER: AuthorityLevel.T1_DIAGNOSTIC,
})

MANDATORY_GATES: tuple[Perspective, ...] = (
    Perspective.P1_COQ_KERNEL,
    Perspective.P2_EXACT_HEAD,
    Perspective.P3_DEPENDENCY_GRAPH,
    Perspective.P4_ARITHMETIC_BOUND,
)
_MANDATORY_SET = frozenset(MANDATORY_GATES)


def canonical_bytes(payload: Any) -> bytes:
    """Strict canonical JSON bytes for deterministic hashing.

    NaN/Infinity are rejected. Key order and incidental whitespace never affect
    the digest.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _require_source_sha(value: str) -> None:
    if not isinstance(value, str) or _HEX40.fullmatch(value) is None:
        raise ValueError("source_sha must be a full lowercase 40-hex Git commit SHA")


def _require_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase 64-hex digest")


@dataclass(frozen=True)
class PerspectiveReceipt:
    perspective: Perspective
    outcome: PerspectiveOutcome
    source_sha: str
    claim_digest: str
    execution_digest: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    version: str = RECEIPT_VERSION
    authority: AuthorityLevel = field(init=False)
    _canonical_evidence: bytes = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.version != RECEIPT_VERSION:
            raise ValueError(f"unsupported receipt version: {self.version!r}")
        _require_source_sha(self.source_sha)
        _require_digest("claim_digest", self.claim_digest)
        _require_digest("execution_digest", self.execution_digest)

        expected = PERSPECTIVE_AUTHORITY[self.perspective]
        object.__setattr__(self, "authority", expected)
        if expected is AuthorityLevel.OPEN and self.outcome is PerspectiveOutcome.PASS:
            raise ValueError(f"{self.perspective.value} is OPEN and can never report PASS")

        try:
            canonical = canonical_bytes(dict(self.evidence))
            normalized = json.loads(canonical)
        except (TypeError, ValueError) as exc:
            raise ValueError("receipt evidence must be strict canonical-JSON serialisable") from exc
        object.__setattr__(self, "_canonical_evidence", canonical)
        object.__setattr__(self, "evidence", _freeze_json(normalized))

    def payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source_sha": self.source_sha,
            "claim_digest": self.claim_digest,
            "execution_digest": self.execution_digest,
            "perspective": self.perspective.value,
            "authority": self.authority.value,
            "outcome": self.outcome.value,
            "evidence": _thaw_json(self.evidence),
        }

    def digest(self) -> str:
        return blake3.blake3(canonical_bytes(self.payload())).hexdigest()


@dataclass(frozen=True)
class ClaimResolution:
    state: ClaimState
    source_sha: str
    claim_digest: str
    consulted: tuple[str, ...]
    ignored: tuple[str, ...]
    receipt_digests: tuple[str, ...]
    chain_digest: str
    violations: tuple[str, ...]


def resolve_claim(
    receipts: Sequence[PerspectiveReceipt],
    *,
    expected_source_sha: str,
    expected_claim_digest: str,
) -> ClaimResolution:
    """Resolve one claim under exact-head and claim-digest provenance binding."""
    _require_source_sha(expected_source_sha)
    _require_digest("expected_claim_digest", expected_claim_digest)

    receipts = tuple(receipts)
    by_perspective: dict[Perspective, PerspectiveReceipt] = {}
    violations: list[str] = []

    for receipt in receipts:
        if receipt.perspective in by_perspective:
            violations.append(f"DUPLICATE_PERSPECTIVE:{receipt.perspective.value}")
        else:
            by_perspective[receipt.perspective] = receipt

        expected_authority = PERSPECTIVE_AUTHORITY[receipt.perspective]
        if receipt.authority is not expected_authority:
            violations.append(f"AUTHORITY_MISMATCH:{receipt.perspective.value}")
        if receipt.source_sha != expected_source_sha:
            violations.append(f"SOURCE_SHA_MISMATCH:{receipt.perspective.value}")
        if receipt.claim_digest != expected_claim_digest:
            violations.append(f"CLAIM_DIGEST_MISMATCH:{receipt.perspective.value}")

    consulted = tuple(
        receipt.perspective.value for receipt in receipts
        if receipt.perspective in _MANDATORY_SET
    )
    ignored = tuple(
        receipt.perspective.value for receipt in receipts
        if receipt.perspective not in _MANDATORY_SET
    )

    mandatory = [by_perspective.get(gate) for gate in MANDATORY_GATES]
    if violations:
        state = ClaimState.QUARANTINED
    elif any(
        receipt is not None and receipt.outcome is PerspectiveOutcome.FAIL
        for receipt in mandatory
    ):
        state = ClaimState.QUARANTINED
    elif any(
        receipt is None
        or receipt.outcome in (PerspectiveOutcome.UNKNOWN, PerspectiveOutcome.UNAVAILABLE)
        for receipt in mandatory
    ):
        state = ClaimState.UNKNOWN
    elif all(
        receipt is not None and receipt.outcome is PerspectiveOutcome.PASS
        for receipt in mandatory
    ):
        state = ClaimState.ADMITTED
    else:
        state = ClaimState.UNKNOWN

    receipt_digests = tuple(receipt.digest() for receipt in receipts)
    chain_digest = blake3.blake3(canonical_bytes({
        "version": RECEIPT_VERSION,
        "source_sha": expected_source_sha,
        "claim_digest": expected_claim_digest,
        "receipts": list(receipt_digests),
        "state": state.value,
        "violations": violations,
    })).hexdigest()

    return ClaimResolution(
        state=state,
        source_sha=expected_source_sha,
        claim_digest=expected_claim_digest,
        consulted=consulted,
        ignored=ignored,
        receipt_digests=receipt_digests,
        chain_digest=chain_digest,
        violations=tuple(violations),
    )


@dataclass(frozen=True)
class GroverDiagnostic:
    marked_index: int | None
    located_index: int | None
    probability: float
    probabilities: tuple[float, ...]
    circuit_qasm_depth: int
    marked_name: str | None = None

    def as_receipt(
        self,
        *,
        source_sha: str,
        claim_digest: str,
        execution_digest: str,
    ) -> PerspectiveReceipt:
        outcome = (
            PerspectiveOutcome.PASS
            if self.located_index is not None and self.probability > 0.99
            else PerspectiveOutcome.UNKNOWN
        )
        return PerspectiveReceipt(
            perspective=Perspective.P_QUANTUM_GROVER,
            outcome=outcome,
            source_sha=source_sha,
            claim_digest=claim_digest,
            execution_digest=execution_digest,
            evidence={
                "marked_index": self.marked_index,
                "marked_name": self.marked_name,
                "located_index": self.located_index,
                "probability": round(self.probability, 12),
                "probabilities": [round(p, 12) for p in self.probabilities],
                "backend": "qiskit.quantum_info.Statevector",
                "physical_advantage": "NOT_ESTABLISHED",
                "admission_authority": "NONE",
            },
        )


class QuantumPerspectiveCarousel:
    """2-qubit local fault locator over the four mandatory gates.

    The quantum receipt is always T1_DIAGNOSTIC. Classical resolution remains
    the sole source of claim state.
    """

    REGISTER: tuple[Perspective, ...] = MANDATORY_GATES

    def __init__(
        self,
        receipts: Sequence[PerspectiveReceipt],
        *,
        source_sha: str,
        claim_digest: str,
        diagnostic_execution_digest: str,
    ) -> None:
        _require_source_sha(source_sha)
        _require_digest("claim_digest", claim_digest)
        _require_digest("diagnostic_execution_digest", diagnostic_execution_digest)
        self.receipts = tuple(receipts)
        self.source_sha = source_sha
        self.claim_digest = claim_digest
        self.diagnostic_execution_digest = diagnostic_execution_digest

    def failing_index(self) -> int | None:
        for index, perspective in enumerate(self.REGISTER):
            matches = [r for r in self.receipts if r.perspective is perspective]
            if len(matches) != 1:
                return index
            receipt = matches[0]
            if (
                receipt.authority is not PERSPECTIVE_AUTHORITY[perspective]
                or receipt.source_sha != self.source_sha
                or receipt.claim_digest != self.claim_digest
                or receipt.outcome is not PerspectiveOutcome.PASS
            ):
                return index
        return None

    @staticmethod
    def build_fault_locator(marked_index: int):
        """Exact N=4 Grover circuit; one iteration gives p=1 for one mark."""
        if not 0 <= marked_index < 4:
            raise ValueError("marked_index must be in 0..3")
        from qiskit import QuantumCircuit

        qc = QuantumCircuit(2, name=f"grover_fault_{marked_index}")
        qc.h([0, 1])
        zeros = [q for q in (0, 1) if not (marked_index >> q) & 1]
        if zeros:
            qc.x(zeros)
        qc.cz(0, 1)
        if zeros:
            qc.x(zeros)
        qc.h([0, 1])
        qc.x([0, 1])
        qc.cz(0, 1)
        qc.x([0, 1])
        qc.h([0, 1])
        return qc

    @classmethod
    def amplify(cls, marked_index: int) -> GroverDiagnostic:
        from qiskit.quantum_info import Statevector

        qc = cls.build_fault_locator(marked_index)
        probabilities = tuple(
            float(p) for p in Statevector.from_instruction(qc).probabilities()
        )
        located = max(range(4), key=probabilities.__getitem__)
        return GroverDiagnostic(
            marked_index=marked_index,
            located_index=located,
            probability=probabilities[located],
            probabilities=probabilities,
            circuit_qasm_depth=qc.depth(),
        )

    def locate_fault(self) -> GroverDiagnostic:
        marked = self.failing_index()
        if marked is None:
            return GroverDiagnostic(
                marked_index=None,
                located_index=None,
                probability=0.0,
                probabilities=(0.25, 0.25, 0.25, 0.25),
                circuit_qasm_depth=0,
            )
        return self.amplify(marked)

    def resolve(self) -> ClaimResolution:
        diagnostic = self.locate_fault().as_receipt(
            source_sha=self.source_sha,
            claim_digest=self.claim_digest,
            execution_digest=self.diagnostic_execution_digest,
        )
        return resolve_claim(
            [*self.receipts, diagnostic],
            expected_source_sha=self.source_sha,
            expected_claim_digest=self.claim_digest,
        )


class DiagnosticOracleRegistry:
    """T1_DIAGNOSTIC registry for up to four local invariants."""

    CAPACITY = 4

    def __init__(self) -> None:
        self._invariants: list[tuple[str, Any]] = []

    def register(self, name: str, check) -> None:
        if len(self._invariants) >= self.CAPACITY:
            raise ValueError(
                f"the 2-qubit fault locator addresses at most {self.CAPACITY} invariants"
            )
        if any(existing == name for existing, _ in self._invariants):
            raise ValueError(f"duplicate invariant {name!r}")
        self._invariants.append((name, check))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self._invariants)

    def first_failing_index(self) -> int | None:
        for index, (_, check) in enumerate(self._invariants):
            try:
                if not bool(check()):
                    return index
            except Exception:
                return index
        return None

    def locate_fault(self) -> GroverDiagnostic:
        marked = self.first_failing_index()
        if marked is None:
            return GroverDiagnostic(
                marked_index=None,
                located_index=None,
                probability=0.0,
                probabilities=(0.25, 0.25, 0.25, 0.25),
                circuit_qasm_depth=0,
            )
        diagnostic = QuantumPerspectiveCarousel.amplify(marked)
        return GroverDiagnostic(
            marked_index=diagnostic.marked_index,
            located_index=diagnostic.located_index,
            probability=diagnostic.probability,
            probabilities=diagnostic.probabilities,
            circuit_qasm_depth=diagnostic.circuit_qasm_depth,
            marked_name=self.names[marked],
        )
