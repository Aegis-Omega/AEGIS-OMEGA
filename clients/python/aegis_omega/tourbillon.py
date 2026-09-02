"""
QuantumTourbillon — multi-perspective verification carousel (MPVC).

Status: ARCHITECTURAL_HYPOTHESIS.  QUANTUM_PHYSICAL_ADVANTAGE = NOT_ESTABLISHED.
RH = NOT_PROVEN.  Nothing in this module carries proof authority.

Authority taxonomy (fixed at import time, enforced on receipt construction):

    P1_COQ_KERNEL        -> ADMISSION_GATE
    P2_EXACT_HEAD        -> ADMISSION_GATE
    P3_DEPENDENCY_GRAPH  -> STRUCTURAL_GATE
    P4_ARITHMETIC_BOUND  -> BOUNDED_FALSIFICATION
    P5_WEIL_DUALITY      -> OPEN            (never PASS; recorded, never consulted)
    P_QUANTUM_GROVER     -> T1_DIAGNOSTIC   (zero admission authority)

Core invariant.  Admit(C) iff every mandatory gate (P1..P4) returns PASS.
Any FAIL on a mandatory gate -> QUARANTINED.  Any UNKNOWN or UNAVAILABLE on a
mandatory gate, or a mandatory gate absent -> UNKNOWN.  Receipts whose
authority is OPEN or T1_DIAGNOSTIC are hashed into the chain but have no vote.

Determinism.  Receipts are hashed with BLAKE3 over canonical JSON (sorted
keys, no whitespace, ASCII).  No wall-clock time enters any digest.

The Grover fault locator is a 2-qubit circuit simulated locally with the
Qiskit statevector; it demonstrates amplitude amplification onto a marked
failing perspective and nothing more.  No cloud backend is contacted.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

import blake3

__all__ = [
    "AuthorityLevel",
    "ClaimResolution",
    "ClaimState",
    "DiagnosticOracleRegistry",
    "GroverDiagnostic",
    "PERSPECTIVE_AUTHORITY",
    "Perspective",
    "PerspectiveOutcome",
    "PerspectiveReceipt",
    "QuantumPerspectiveCarousel",
    "canonical_bytes",
    "resolve_claim",
]


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

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

    @property
    def admission_bearing(self) -> bool:
        return self in _ADMISSION_BEARING


_ADMISSION_BEARING = frozenset({
    AuthorityLevel.ADMISSION_GATE,
    AuthorityLevel.STRUCTURAL_GATE,
    AuthorityLevel.BOUNDED_FALSIFICATION,
})


class Perspective(str, Enum):
    P1_COQ_KERNEL = "P1_COQ_KERNEL"
    P2_EXACT_HEAD = "P2_EXACT_HEAD"
    P3_DEPENDENCY_GRAPH = "P3_DEPENDENCY_GRAPH"
    P4_ARITHMETIC_BOUND = "P4_ARITHMETIC_BOUND"
    P5_WEIL_DUALITY = "P5_WEIL_DUALITY"
    P_QUANTUM_GROVER = "P_QUANTUM_GROVER"


PERSPECTIVE_AUTHORITY: Mapping[Perspective, AuthorityLevel] = {
    Perspective.P1_COQ_KERNEL: AuthorityLevel.ADMISSION_GATE,
    Perspective.P2_EXACT_HEAD: AuthorityLevel.ADMISSION_GATE,
    Perspective.P3_DEPENDENCY_GRAPH: AuthorityLevel.STRUCTURAL_GATE,
    Perspective.P4_ARITHMETIC_BOUND: AuthorityLevel.BOUNDED_FALSIFICATION,
    Perspective.P5_WEIL_DUALITY: AuthorityLevel.OPEN,
    Perspective.P_QUANTUM_GROVER: AuthorityLevel.T1_DIAGNOSTIC,
}

MANDATORY_GATES: tuple[Perspective, ...] = (
    Perspective.P1_COQ_KERNEL,
    Perspective.P2_EXACT_HEAD,
    Perspective.P3_DEPENDENCY_GRAPH,
    Perspective.P4_ARITHMETIC_BOUND,
)


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------

def canonical_bytes(payload: Any) -> bytes:
    """Canonical JSON: sorted keys, no whitespace, ASCII-only, UTF-8 bytes."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


@dataclass(frozen=True)
class PerspectiveReceipt:
    perspective: Perspective
    outcome: PerspectiveOutcome
    evidence: Mapping[str, Any] = field(default_factory=dict)
    authority: AuthorityLevel = field(init=False)

    def __post_init__(self) -> None:
        expected = PERSPECTIVE_AUTHORITY[self.perspective]
        object.__setattr__(self, "authority", expected)
        if (
            expected is AuthorityLevel.OPEN
            and self.outcome is PerspectiveOutcome.PASS
        ):
            raise ValueError(
                f"{self.perspective.value} is OPEN and can never report PASS"
            )
        try:
            canonical_bytes(dict(self.evidence))
        except (TypeError, ValueError) as exc:
            raise ValueError("receipt evidence must be canonical-JSON serialisable") from exc

    def payload(self) -> dict[str, Any]:
        return {
            "perspective": self.perspective.value,
            "authority": self.authority.value,
            "outcome": self.outcome.value,
            "evidence": dict(self.evidence),
        }

    def digest(self) -> str:
        return blake3.blake3(canonical_bytes(self.payload())).hexdigest()


@dataclass(frozen=True)
class ClaimResolution:
    state: ClaimState
    consulted: tuple[str, ...]
    ignored: tuple[str, ...]
    receipt_digests: tuple[str, ...]
    chain_digest: str


def resolve_claim(receipts: Sequence[PerspectiveReceipt]) -> ClaimResolution:
    """Apply the core invariant.  Only admission-bearing receipts have a vote."""
    by_perspective: dict[Perspective, PerspectiveReceipt] = {}
    for receipt in receipts:
        if receipt.perspective in by_perspective:
            raise ValueError(f"duplicate receipt for {receipt.perspective.value}")
        by_perspective[receipt.perspective] = receipt

    consulted = [r for r in receipts if r.authority.admission_bearing]
    ignored = [r for r in receipts if not r.authority.admission_bearing]

    outcomes = [r.outcome for r in consulted]
    missing = [g for g in MANDATORY_GATES if g not in by_perspective]

    if PerspectiveOutcome.FAIL in outcomes:
        state = ClaimState.QUARANTINED
    elif (
        missing
        or PerspectiveOutcome.UNKNOWN in outcomes
        or PerspectiveOutcome.UNAVAILABLE in outcomes
    ):
        state = ClaimState.UNKNOWN
    else:
        state = ClaimState.ADMITTED

    digests = tuple(r.digest() for r in receipts)
    chain_digest = blake3.blake3(
        canonical_bytes({"receipts": list(digests), "state": state.value})
    ).hexdigest()
    return ClaimResolution(
        state=state,
        consulted=tuple(r.perspective.value for r in consulted),
        ignored=tuple(r.perspective.value for r in ignored),
        receipt_digests=digests,
        chain_digest=chain_digest,
    )


# ---------------------------------------------------------------------------
# Grover fault locator (2 qubits, exact, local statevector)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GroverDiagnostic:
    marked_index: int | None
    located_index: int | None
    probability: float
    probabilities: tuple[float, ...]
    circuit_qasm_depth: int
    marked_name: str | None = None

    def as_receipt(self) -> PerspectiveReceipt:
        outcome = (
            PerspectiveOutcome.PASS
            if self.located_index is not None and self.probability > 0.99
            else PerspectiveOutcome.UNKNOWN
        )
        return PerspectiveReceipt(
            perspective=Perspective.P_QUANTUM_GROVER,
            outcome=outcome,
            evidence={
                "marked_index": self.marked_index,
                "marked_name": self.marked_name,
                "located_index": self.located_index,
                "probability": round(self.probability, 12),
                "probabilities": [round(p, 12) for p in self.probabilities],
                "backend": "qiskit.quantum_info.Statevector",
                "physical_advantage": "NOT_ESTABLISHED",
            },
        )


class QuantumPerspectiveCarousel:
    """Indexes the four mandatory gates on a 2-qubit register and runs one
    exact Grover iteration against the first non-PASS gate."""

    REGISTER: tuple[Perspective, ...] = MANDATORY_GATES  # index 0..3

    def __init__(self, receipts: Sequence[PerspectiveReceipt]) -> None:
        self.receipts = tuple(receipts)
        self._by_perspective = {r.perspective: r for r in self.receipts}

    def failing_index(self) -> int | None:
        for index, perspective in enumerate(self.REGISTER):
            receipt = self._by_perspective.get(perspective)
            if receipt is None or receipt.outcome is not PerspectiveOutcome.PASS:
                return index
        return None

    @staticmethod
    def build_fault_locator(marked_index: int):
        """Exact 2-qubit Grover: H⊗H, phase oracle on |marked⟩, diffuser.
        For N = 4 with one marked item a single iteration is exact (p = 1)."""
        if not 0 <= marked_index < 4:
            raise ValueError("marked_index must be in 0..3")
        from qiskit import QuantumCircuit

        qc = QuantumCircuit(2, name=f"grover_fault_{marked_index}")
        qc.h([0, 1])
        # oracle: flip the phase of |marked⟩ (qubit 0 is the least-significant bit)
        zeros = [q for q in (0, 1) if not (marked_index >> q) & 1]
        if zeros:
            qc.x(zeros)
        qc.cz(0, 1)
        if zeros:
            qc.x(zeros)
        # diffuser: 2|s><s| - I
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
        probabilities = tuple(float(p) for p in Statevector.from_instruction(qc).probabilities())
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
        """Resolve the claim with the Grover receipt appended.  The appended
        receipt is T1_DIAGNOSTIC and therefore never consulted."""
        return resolve_claim([*self.receipts, self.locate_fault().as_receipt()])


# ---------------------------------------------------------------------------
# Diagnostic oracle registry (integration seam for external invariants)
# ---------------------------------------------------------------------------

class DiagnosticOracleRegistry:
    """Registers named invariants and turns the first one that fails into the
    marked state of the 2-qubit fault locator.

    The register holds at most four invariants because the single-iteration
    Grover circuit is exact only for N = 4 with one marked item; a larger
    search space needs round(pi/4 * sqrt(N)) iterations and is no longer
    exact, which is a different diagnostic and is not implemented here.
    An invariant that raises counts as failing.  T1_DIAGNOSTIC only.
    """

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
