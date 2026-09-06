"""Finite-dimensional, time-independent GKSL validation in explicit units.

This is a numerical checker, not a tomography algorithm, calibration authority,
clinical admission service, continuous-time certificate, or CV tail bound.
H is an angular-frequency Hamiltonian (H_physical / hbar), in s^-1.
Jump operators include sqrt(rate), in s^-1/2. Time is in seconds.
"""

from dataclasses import asdict, dataclass
from numbers import Real

import numpy as np
from scipy.linalg import expm


@dataclass(frozen=True)
class PhysicsPolicy:
    # Synthetic demonstration policy; freeze instrument-specific bounds before use.
    eigenvalue_tolerance: float = 1e-10
    hermiticity_tolerance: float = 1e-10
    trace_tolerance: float = 1e-9
    midpoint_residual_per_second: float = 1e-3
    transition_residual: float = 1e-5
    probability_residual: float = 1e-3
    identifiability_rtol: float = 1e-9
    max_dimension: int = 16

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key == "max_dimension":
                if type(value) is not int or not 2 <= value <= 32:
                    raise ValueError("max_dimension must be an integer in [2, 32]")
            elif (not isinstance(value, Real) or isinstance(value, (bool, np.bool_))
                  or not np.isfinite(value) or value <= 0):
                raise ValueError(f"{key} must be finite and positive")
        if self.identifiability_rtol >= 1:
            raise ValueError("identifiability_rtol must be below one")


def _numeric(value, *, real=False):
    a = np.asarray(value)
    if a.dtype.kind not in "iufc" or (real and np.iscomplexobj(a)):
        raise ValueError("NON_NUMERIC_OR_WRONG_DTYPE")
    a = np.asarray(a, dtype=np.float64 if real else np.complex128)
    if not np.all(np.isfinite(a)):
        raise ValueError("NONFINITE_INPUT")
    return a


def gksl_rhs(rho, hamiltonian, jumps):
    """Algebraic RHS; public callers must validate generator/state inputs first."""
    h = hamiltonian
    value = -1j * (h @ rho - rho @ h)
    for jump in jumps:
        adj = jump.conj().T
        product = adj @ jump
        value += jump @ rho @ adj - 0.5 * (product @ rho + rho @ product)
    return value


def _superoperator(h, jumps):
    # Column-vectorization convention, constructed by action on matrix units.
    d = h.shape[0]
    columns = []
    for j in range(d):
        for i in range(d):
            e = np.zeros((d, d), dtype=complex)
            e[i, j] = 1.0
            columns.append(gksl_rhs(e, h, jumps).reshape(-1, order="F"))
    return np.column_stack(columns)


def _traceless_basis(d):
    basis = []
    for i in range(d):
        for j in range(i + 1, d):
            symmetric = np.zeros((d, d), dtype=complex)
            symmetric[i, j] = symmetric[j, i] = 1 / np.sqrt(2)
            antisymmetric = np.zeros((d, d), dtype=complex)
            antisymmetric[i, j] = -1j / np.sqrt(2)
            antisymmetric[j, i] = 1j / np.sqrt(2)
            basis.extend([symmetric, antisymmetric])
    for k in range(1, d):
        diagonal = np.zeros(d)
        diagonal[:k] = 1.0
        diagonal[k] = -k
        basis.append(np.diag(diagonal / np.sqrt(k * (k + 1))))
    return np.asarray(basis)


def wigner_origin(rho):
    """One-mode Fock-basis parity diagnostic: W(0)=2/pi sum_n (-1)^n rho_nn.

    Convention alpha=(q+ip)/sqrt(2); finite Fock support is caller-declared.
    No uncertainty interval or omitted-tail bound is inferred. A negative value
    is not an invalid state and is never used as an IFG rejection criterion.
    """
    r = _numeric(rho)
    if r.ndim != 2 or r.shape[0] != r.shape[1] or r.shape[0] == 0:
        raise ValueError("INVALID_STATE_SHAPE")
    if np.linalg.norm(r - r.conj().T) > 1e-10:
        raise ValueError("NON_HERMITIAN_STATE")
    if abs(np.trace(r) - 1) > 1e-9 or np.linalg.eigvalsh(r).min() < -1e-10:
        raise ValueError("INVALID_DENSITY_MATRIX")
    parity = (-1.0) ** np.arange(r.shape[0])
    return {
        "value": float((2 / np.pi) * np.dot(parity, np.diag(r).real)),
        "convention": "one_mode_alpha_Fock_parity_2_over_pi",
        "scope": "FINITE_FOCK_NUMERICAL_DIAGNOSTIC_NO_TAIL_OR_CONFIDENCE_BOUND",
    }


class IndependentFalsificationGate:
    """Evaluate an observed state trajectory and calibrated measurement model.

    Independence is an external data/split/governance requirement, not a property
    certified by the class name. All samples are checked; no averaging away of
    invalid states. Missing/ill-formed input produces DENY.
    """

    def __init__(self, policy=None):
        self.policy = PhysicsPolicy() if policy is None else policy
        if not isinstance(self.policy, PhysicsPolicy):
            raise TypeError("policy must be PhysicsPolicy")

    def evaluate(self, rho, times_seconds, hamiltonian, jumps, *, povm, probabilities):
        metrics = {}
        reasons = []
        try:
            # Overflow and invalid floating-point operations must not turn into PASS.
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                self._evaluate(rho, times_seconds, hamiltonian, jumps,
                               povm, probabilities, metrics, reasons)
        except (ValueError, TypeError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
            reasons.append(str(exc) if isinstance(exc, ValueError) else "NUMERICAL_OR_INPUT_FAILURE")
        if any(not np.isfinite(v) for v in metrics.values() if isinstance(v, (int, float))):
            reasons.append("NONFINITE_METRIC")
            metrics = {k: v if not isinstance(v, float) or np.isfinite(v) else None
                       for k, v in metrics.items()}
        return {
            "status": "DENY" if reasons else "PASS_RESEARCH_ONLY",
            "reasons": list(dict.fromkeys(reasons)),
            "metrics": metrics,
            "policy": asdict(self.policy),
            "scope": "FINITE_SAMPLED_MODEL_CONSISTENCY_ONLY",
            "calibration_authority": "NOT_VERIFIED_BY_THIS_MODULE",
            "clinical_admission": False,
            "quantum_nonclassicality": "NOT_TESTED_BY_PHYSICAL_GATE",
        }

    def _evaluate(self, rho, times, h, jumps, povm, probabilities, metrics, reasons):
        p = self.policy
        r, t, h = _numeric(rho), _numeric(times, real=True), _numeric(h)
        if r.ndim != 3 or r.shape[1] != r.shape[2] or not 2 <= r.shape[1] <= p.max_dimension:
            raise ValueError("INVALID_STATE_SHAPE")
        n, d, _ = r.shape
        if t.shape != (n,) or n < 3 or np.any(np.diff(t) <= 0):
            raise ValueError("INVALID_TIME_GRID")
        if h.shape != (d, d):
            raise ValueError("INVALID_HAMILTONIAN_SHAPE")
        js = _numeric(jumps)
        if js.size == 0 and js.shape == (0,):
            js = js.reshape(0, d, d)
        if js.ndim != 3 or js.shape[1:] != (d, d):
            raise ValueError("INVALID_JUMP_SHAPE")
        h_error = float(np.linalg.norm(h - h.conj().T, ord="fro"))
        metrics["hamiltonian_hermiticity_error_per_second"] = h_error
        if h_error > p.hermiticity_tolerance:
            raise ValueError("NON_HERMITIAN_HAMILTONIAN")
        # Never silently repair a materially non-Hermitian state before checking.
        herm = np.linalg.norm(r - r.conj().transpose(0, 2, 1), axis=(1, 2))
        traces = np.abs(np.trace(r, axis1=1, axis2=2) - 1)
        metrics["max_hermiticity_error"] = float(herm.max())
        metrics["max_trace_error"] = float(traces.max())
        if herm.max() > p.hermiticity_tolerance:
            reasons.append("NON_HERMITIAN_STATE")
        if traces.max() > p.trace_tolerance:
            reasons.append("TRACE_VIOLATION")
        hermitian = (r + r.conj().transpose(0, 2, 1)) / 2
        minimum = float(np.linalg.eigvalsh(hermitian).min())
        metrics["minimum_eigenvalue"] = minimum
        if minimum < -p.eigenvalue_tolerance:
            reasons.append("PSD_VIOLATION")
        if reasons:
            return
        # POVM completeness plus injectivity on trace-one Hermitian matrices.
        m, obs = _numeric(povm), _numeric(probabilities, real=True)
        if m.ndim != 3 or m.shape[1:] != (d, d) or m.shape[0] == 0:
            raise ValueError("INVALID_POVM_SHAPE")
        if obs.shape != (n, len(m)):
            raise ValueError("INVALID_PROBABILITY_SHAPE")
        if (np.max(np.linalg.norm(m - m.conj().transpose(0, 2, 1), axis=(1, 2))) > p.hermiticity_tolerance
                or np.linalg.eigvalsh(m).min() < -p.eigenvalue_tolerance
                or np.linalg.norm(m.sum(axis=0) - np.eye(d)) > p.trace_tolerance):
            raise ValueError("INVALID_POVM")
        design = np.einsum("mij,kji->mk", m, _traceless_basis(d)).real
        singular = np.linalg.svd(design, compute_uv=False)
        rank = int(np.count_nonzero(singular > p.identifiability_rtol * singular[0]))
        metrics["measurement_rank"] = rank
        metrics["required_measurement_rank"] = d * d - 1
        if rank != d * d - 1:
            reasons.append("NOT_IDENTIFIABLE")
        if np.any(obs < 0) or np.any(obs > 1) or np.max(np.abs(obs.sum(axis=1) - 1)) > p.trace_tolerance:
            raise ValueError("INVALID_PROBABILITIES")
        predicted = np.einsum("mij,tji->tm", m, r)
        probability_error = float(np.max(np.abs(predicted - obs)))
        metrics["max_probability_residual"] = probability_error
        if probability_error > p.probability_residual:
            reasons.append("MEASUREMENT_MISMATCH")
        # Midpoint discretization is approximate, O(dt^2), with explicit units.
        dt = np.diff(t)
        observed_derivative = (r[1:] - r[:-1]) / dt[:, None, None]
        rhs = np.asarray([gksl_rhs(x, h, js) for x in (r[1:] + r[:-1]) / 2])
        residual = float(np.linalg.norm(observed_derivative - rhs, axis=(1, 2)).max())
        metrics["max_midpoint_residual_per_second"] = residual
        if residual > p.midpoint_residual_per_second:
            reasons.append("LINDBLAD_RESIDUAL")
        # Independent interval propagator avoids a derivative copied from the RHS.
        generator = _superoperator(h, js)
        transitions = []
        for i, interval in enumerate(dt):
            predicted_state = (expm(generator * interval) @ r[i].reshape(-1, order="F")).reshape(d, d, order="F")
            transitions.append(np.linalg.norm(predicted_state - r[i + 1], ord="fro"))
        transition = float(max(transitions))
        metrics["max_transition_residual"] = transition
        if transition > p.transition_residual:
            reasons.append("TRANSITION_MISMATCH")
