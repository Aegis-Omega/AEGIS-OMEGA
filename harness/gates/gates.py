"""AEGIS Omega -- Zero-Discretion Type Gates v1.

Research invariants fire mechanically from declared object types. A generator
may choose a construction; it may not curate which registered falsifiers the
construction must survive.

Deliberately separate from sovereign-omega-v2/python/gate.py, which is a frozen
constitutional file governing mutation authority. This module governs
mathematical/research admission, not runtime mutation voting. The near-collision
in naming is the reason this note exists.

Three separated responsibilities, and the generator is none of them:
  REGISTRY   knows which invariants a type owes
  EXECUTOR   computes them and emits evidence
  ADMISSION  checks valid PASS receipts exist

No relevance scoring. No expected-value test. No "this property is probably
not load-bearing here". A registered type executes its registered gates.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

SCHEMA_VERSION = "AEGIS_ZERO_DISCRETION_TYPE_GATES_V1"


class GateVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


PASS, FAIL, ERROR = GateVerdict.PASS, GateVerdict.FAIL, GateVerdict.ERROR


class InvariantViolation(Exception):
    pass


class IncompleteRegistry(Exception):
    """A registered type with no gates is a defect, not a clean bill of health."""


def _canonical(value: Any) -> Any:
    """Canonical JSON-safe form. float.hex() because repr() is neither
    bit-exact nor stable across interpreters, and a digest that drifts with
    the interpreter is not an identity."""
    import numpy as np
    if isinstance(value, float):
        return {"__f64__": value.hex()}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, np.ndarray):
        return {"__ndarray__": hashlib.sha256(
            np.ascontiguousarray(value, dtype=np.float64).tobytes()).hexdigest(),
            "shape": list(value.shape)}
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return {"__repr__": repr(value)}


def digest(*parts: Any) -> str:
    """Identity of the thing that was checked. Receipts die when it changes."""
    payload = json.dumps([SCHEMA_VERSION, [_canonical(p) for p in parts]],
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class Receipt:
    object_digest: str
    type_signature: str
    gate_id: str
    inputs: dict
    result: GateVerdict
    witness: str

    @property
    def admitted(self) -> bool:
        return self.result is GateVerdict.PASS


@dataclass
class Gate:
    gate_id: str
    fn: Callable[..., tuple[bool, str]]

    def run(self, sig: str, obj_digest: str, inputs: dict, *args) -> Receipt:
        try:
            ok, witness = self.fn(*args)
            res = PASS if ok else FAIL
        except Exception as exc:                      # fail-closed on ERROR too
            res, witness = ERROR, f"{type(exc).__name__}: {exc}"
        return Receipt(obj_digest, sig, self.gate_id, inputs, res, witness)


# --------------------------------------------------------------------------
# REGISTRY.  Keyed by the constructor that produced the object, never by a
# label the author supplies -- otherwise the exploit is not "skip the gate",
# it is "declare the weaker type".
# --------------------------------------------------------------------------
_UNARY: dict[str, list[Gate]] = {}
_BINARY: dict[str, list[Gate]] = {}


def unary(sig: str):
    def deco(fn):
        _UNARY.setdefault(sig, []).append(Gate(fn.__name__, fn)); return fn
    return deco


def binary(sig: str):
    def deco(fn):
        _BINARY.setdefault(sig, []).append(Gate(fn.__name__, fn)); return fn
    return deco


def gateset(sig: str, kind: str = "unary") -> list[Gate]:
    table = _UNARY if kind == "unary" else _BINARY
    if sig not in table:
        raise IncompleteRegistry(
            f"type {sig!r} is admissible but owes no {kind} gates; "
            f"an empty gate set passes vacuously and must not admit"
        )
    return table[sig]


def admit(receipts: list[Receipt]) -> None:
    """FAIL blocks. ERROR blocks. Absence of a result blocks."""
    if not receipts:
        raise InvariantViolation("no gate receipts: nothing was checked")
    bad = [r for r in receipts if not r.admitted]
    if bad:
        raise InvariantViolation(
            "; ".join(f"{r.gate_id}={r.result} [{r.witness}]" for r in bad)
        )


# --------------------------------------------------------------------------
# UNARY GATES
# --------------------------------------------------------------------------
@unary("AntisymmetricOperator")
def quadratic_form_is_identically_zero(A) -> tuple[bool, str]:
    """A^T = -A  =>  x^T A x = 0 for every real x.  Not small. Zero.

    Any construction needing x^T A x >= K > 0 for such an A is impossible,
    not merely hard, and no amount of numerical work will find that out.
    """
    import numpy as np
    asym = np.linalg.norm(A + A.T)
    if asym > 1e-12 * max(np.linalg.norm(A), 1.0):
        return True, f"not antisymmetric (||A+A^T||={asym:.3e}); gate not applicable"
    rng = np.random.default_rng(0)
    worst = max(abs(v @ A @ v) for v in rng.standard_normal((64, A.shape[0])))
    return False, (
        f"x^T A x = 0 identically (worst of 64 probes: {worst:.3e}); "
        f"any positive lower bound on this form is unreachable"
    )


@unary("GraphLaplacian")
def annihilates_constant_mode(L) -> tuple[bool, str]:
    """L 1 = 0.  A coupling built from L cannot move a uniform fibre lift."""
    import numpy as np
    r = np.linalg.norm(L @ np.ones(L.shape[0]))
    return r > 1e-10, f"||L*1|| = {r:.3e}" + ("" if r > 1e-10 else " -> kernel contains the constant mode")


@unary("EdgeDecomposition")
def sum_is_not_the_adjacency(payload) -> tuple[bool, str]:
    """Sum of unweighted edge indicators IS the adjacency matrix, which acts
    as a scalar on any eigenvector of A -- the ground mode included."""
    import numpy as np
    S, A = payload
    d = np.linalg.norm(S - A)
    return d > 1e-10, f"||sum B_e - A|| = {d:.3e}" + ("" if d > 1e-10 else " -> decomposition is scalar on eigenmodes of A")


# --------------------------------------------------------------------------
# BINARY GATES -- the ones a unary GateSet(o) cannot express.
# Coverage needs (basis, target); commutation needs (op, op).
# --------------------------------------------------------------------------
@binary("SpectralBasis x SpectralTarget")
def basis_resolves_target(basis, target_max) -> tuple[bool, str]:
    k = basis.cutoff
    return k >= target_max, f"k_max = N_F*pi/h = {k:.3f} vs target {target_max:.3f}"


@binary("NonCommutingPair")
def operators_actually_fail_to_commute(A, B) -> tuple[bool, str]:
    """Declared as a non-commuting pair: prove it. [A_G, 3I - A_G] = 0."""
    import numpy as np
    K = A @ B - B @ A
    n = np.linalg.norm(K)
    return n > 1e-10, f"||[A,B]|| = {n:.3e}" + ("" if n > 1e-10 else " -> the term vanishes identically")


@binary("SeparableChannels")
def channels_span_different_subspaces(sig_vecs, nui_vecs) -> tuple[bool, str]:
    """If signal lies inside span(nuisance), nulling one nulls the other."""
    import numpy as np
    Q = np.linalg.qr(np.asarray(nui_vecs).T)[0]
    inside = [float(np.linalg.norm(Q.T @ (v / np.linalg.norm(v)))) for v in sig_vecs]
    worst = max(inside)
    return worst < 0.99, f"max fraction of signal inside span(nuisance) = {worst:.4f}"


# --------------------------------------------------------------------------
# Assert-by-construction.  The gate fires before any allocation.
# --------------------------------------------------------------------------
@dataclass
class SpectralBasis:
    N_F: int
    h: float
    convention: str = "sine_dirichlet"     # k_j = j*pi/h ; other conventions differ
    _receipts: list = field(default_factory=list, repr=False)

    @property
    def cutoff(self) -> float:
        import numpy as np
        if self.convention != "sine_dirichlet":
            raise IncompleteRegistry(f"no cutoff rule registered for {self.convention!r}")
        return self.N_F * np.pi / self.h

    def against(self, target_max: float) -> "SpectralBasis":
        """Pairing the basis with what it will be integrated against.

        Coverage cannot fire at construction: the target is often not known
        until later.  It fires here, at first composition, and blocks.
        """
        sig = "SpectralBasis x SpectralTarget"
        d = digest(self.N_F, self.h, self.convention, target_max)
        rs = [g.run(sig, d, {"N_F": self.N_F, "h": self.h, "target": target_max},
                    self, target_max) for g in gateset(sig, "binary")]
        admit(rs)
        self._receipts.extend(rs)
        return self
