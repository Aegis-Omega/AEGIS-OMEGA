"""Finite-section spectral inertia diagnostics for the Weil research lane.

This module is deliberately T1-only.  It evaluates a floating-point Galerkin
model, applies the moment constraint by nullspace reduction, and solves the
symmetric generalized eigenproblem ``M c = lambda G c``.  It cannot mint proof
authority, establish global Weil positivity, or prove RH.

Key safeguards:

* ``p_cutoff`` and an optional prime-shift/support cutoff are separate knobs;
* the moment constraint is imposed by an explicit nullspace basis, never by a
  tiny regularizing eigenvalue in the removed direction;
* inertia comparisons on the same span use the Gram metric;
* Diophantine control values are labelled conservatively;
* convergence sweeps are finite diagnostics and never assert an infinite liminf;
* reference replay requires exact inertia counts plus bounded eigenvalue windows;
* every emitted receipt is numerical diagnostic evidence only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

import numpy as np
import scipy.linalg as la
import scipy.special as sp


T1_AUTHORITY = "T1_NUMERICAL_DIAGNOSTIC"
PHI_NOT_SUPPORTED = "NOT_SUPPORTED"


@dataclass(frozen=True)
class SpectralProbeConfig:
    tau: float = 2.0
    p_cutoff: int = 2000
    k_basis_dim: int = 40
    n_quad: int = 8192
    t_bound: float = 200.0
    max_prime_shift: float | None = None
    zero_tolerance: float = 1e-10
    negative_tolerance: float = 1e-8

    def __post_init__(self) -> None:
        if not math.isfinite(self.tau) or self.tau <= 0.0:
            raise ValueError("tau must be finite and positive")
        if self.p_cutoff < 2:
            raise ValueError("p_cutoff must be >= 2")
        if self.k_basis_dim < 1:
            raise ValueError("k_basis_dim must be >= 1")
        if self.n_quad < 32:
            raise ValueError("n_quad must be >= 32")
        if not math.isfinite(self.t_bound) or self.t_bound <= 0.0:
            raise ValueError("t_bound must be finite and positive")
        if self.max_prime_shift is not None:
            if not math.isfinite(self.max_prime_shift) or self.max_prime_shift <= 0.0:
                raise ValueError("max_prime_shift must be finite and positive when supplied")
        if self.zero_tolerance <= 0.0 or self.negative_tolerance <= 0.0:
            raise ValueError("eigenvalue tolerances must be positive")


@dataclass(frozen=True)
class PrimePowerTerm:
    prime: int
    exponent: int
    prime_power: int
    weight: float
    shift: float


@dataclass(frozen=True)
class ReducedGalerkinMatrices:
    M: np.ndarray
    G: np.ndarray
    constraint_basis: np.ndarray
    moment_vector: np.ndarray


@dataclass(frozen=True)
class InertiaResult:
    eigenvalues: tuple[float, ...]
    lambda_min: float
    nu_minus: int
    nu_zero: int
    nu_plus: int
    active_dimension: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sieve_primes(limit: int) -> np.ndarray:
    sieve = np.ones(limit + 1, dtype=bool)
    sieve[:2] = False
    for candidate in range(2, math.isqrt(limit) + 1):
        if sieve[candidate]:
            sieve[candidate * candidate :: candidate] = False
    return np.flatnonzero(sieve)


def _prime_power_terms(config: SpectralProbeConfig) -> tuple[PrimePowerTerm, ...]:
    terms: list[PrimePowerTerm] = []
    for p_raw in _sieve_primes(config.p_cutoff):
        p = int(p_raw)
        log_p = math.log(p)
        exponent = 1
        prime_power = p
        while prime_power <= config.p_cutoff:
            shift = exponent * log_p
            if config.max_prime_shift is None or shift < config.max_prime_shift:
                terms.append(
                    PrimePowerTerm(
                        prime=p,
                        exponent=exponent,
                        prime_power=prime_power,
                        weight=log_p / math.sqrt(prime_power),
                        shift=shift,
                    )
                )
            if prime_power > config.p_cutoff // p:
                break
            prime_power *= p
            exponent += 1
    return tuple(terms)


def generalized_inertia(
    M: np.ndarray,
    G: np.ndarray,
    *,
    zero_tolerance: float = 1e-10,
    negative_tolerance: float = 1e-8,
) -> InertiaResult:
    """Solve a symmetric generalized eigenproblem and classify its inertia.

    ``G`` must be positive definite on the supplied coordinates.  This helper
    is also the same-span congruence falsifier: replacing ``(M,G)`` by
    ``(S.T M S, S.T G S)`` for invertible ``S`` must preserve the counts.
    """

    M = np.asarray(M, dtype=float)
    G = np.asarray(G, dtype=float)
    if M.ndim != 2 or G.ndim != 2 or M.shape != G.shape or M.shape[0] != M.shape[1]:
        raise ValueError("M and G must be square matrices with identical shape")
    M = 0.5 * (M + M.T)
    G = 0.5 * (G + G.T)

    gram_eigs = la.eigvalsh(G, check_finite=True)
    if float(np.min(gram_eigs)) <= 0.0:
        raise ValueError("Gram matrix must be positive definite on the active subspace")

    eigvals = la.eigvalsh(M, G, check_finite=True)
    eigvals = np.asarray(eigvals, dtype=float)
    nu_minus = int(np.sum(eigvals < -negative_tolerance))
    nu_plus = int(np.sum(eigvals > zero_tolerance))
    nu_zero = int(eigvals.size - nu_minus - nu_plus)
    return InertiaResult(
        eigenvalues=tuple(float(x) for x in eigvals),
        lambda_min=float(np.min(eigvals)) if eigvals.size else 0.0,
        nu_minus=nu_minus,
        nu_zero=nu_zero,
        nu_plus=nu_plus,
        active_dimension=int(eigvals.size),
    )


class WeilSpectralInertiaProbe:
    def __init__(self, config: SpectralProbeConfig):
        self.config = config
        self.k_indices = np.arange(-config.k_basis_dim, config.k_basis_dim + 1, dtype=int)
        self.dim = int(self.k_indices.size)
        self.prime_power_terms = _prime_power_terms(config)

    @property
    def prime_power_count(self) -> int:
        return len(self.prime_power_terms)

    def compute_symbol(self, t_grid: np.ndarray) -> np.ndarray:
        t_grid = np.asarray(t_grid, dtype=float)
        s_vals = 0.25 + 0.5j * t_grid
        arch = np.real(sp.digamma(s_vals)) - math.log(math.pi)
        prime_symbol = np.zeros_like(t_grid, dtype=float)
        for term in self.prime_power_terms:
            prime_symbol += 2.0 * term.weight * np.cos(term.shift * t_grid)
        return arch - prime_symbol

    def assemble_raw(self, scale_factor: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if not math.isfinite(scale_factor) or scale_factor <= 0.0:
            raise ValueError("scale_factor must be finite and positive")

        cfg = self.config
        t_grid = np.linspace(-cfg.t_bound, cfg.t_bound, cfg.n_quad, dtype=float)
        dt = float(t_grid[1] - t_grid[0])
        symbol = self.compute_symbol(t_grid)
        arguments = (cfg.tau * scale_factor / math.pi) * t_grid[None, :] - self.k_indices[:, None]
        psi = np.sinc(arguments)
        w_quad = dt / (2.0 * math.pi)

        M = (psi * (symbol * w_quad)) @ psi.T
        G = (psi * w_quad) @ psi.T
        moment_vector = np.sum(psi * w_quad, axis=1)
        return 0.5 * (M + M.T), 0.5 * (G + G.T), moment_vector

    def assemble_moment_restricted(self, scale_factor: float = 1.0) -> ReducedGalerkinMatrices:
        M, G, moment_vector = self.assemble_raw(scale_factor)
        row = moment_vector.reshape(1, -1)
        constraint_basis = la.null_space(row)
        if constraint_basis.shape != (self.dim, self.dim - 1):
            raise RuntimeError("moment nullspace does not have the expected codimension one")

        M_reduced = constraint_basis.T @ M @ constraint_basis
        G_reduced = constraint_basis.T @ G @ constraint_basis
        M_reduced = 0.5 * (M_reduced + M_reduced.T)
        G_reduced = 0.5 * (G_reduced + G_reduced.T)

        gram_min = float(np.min(la.eigvalsh(G_reduced, check_finite=True)))
        if gram_min <= 0.0:
            raise ValueError("reduced Gram matrix is not positive definite")

        return ReducedGalerkinMatrices(
            M=M_reduced,
            G=G_reduced,
            constraint_basis=constraint_basis,
            moment_vector=moment_vector,
        )

    def solve_generalized_inertia(self, scale_factor: float = 1.0) -> InertiaResult:
        reduced = self.assemble_moment_restricted(scale_factor)
        return generalized_inertia(
            reduced.M,
            reduced.G,
            zero_tolerance=self.config.zero_tolerance,
            negative_tolerance=self.config.negative_tolerance,
        )

    def run_scale_probe(self, scales: Mapping[str, float]) -> dict[str, object]:
        if not scales:
            raise ValueError("at least one scale is required")
        results = {
            name: {
                "scale": float(scale),
                **self.solve_generalized_inertia(float(scale)).to_dict(),
            }
            for name, scale in scales.items()
        }
        return {
            "schema_version": "1.0.0",
            "authority": T1_AUTHORITY,
            "method": "FLOAT64_GENERALIZED_EIGENPROBLEM_WITH_NULLSPACE_MOMENT_CONSTRAINT",
            "config": asdict(self.config),
            "prime_power_count": self.prime_power_count,
            "results": results,
            "phi_nonresonant_positivity_hypothesis": PHI_NOT_SUPPORTED,
            "finite_section_negativity_status": "OBSERVED_ONLY_WHERE_NUMERICALLY_PRESENT",
            "global_weil_positivity_proven": False,
            "rh_proven": False,
            "non_claims": (
                "NO_INFINITE_DIMENSIONAL_LIMINF_THEOREM",
                "NO_DIOPHANTINE_OPTIMALITY_THEOREM_FOR_PRIME_PHASES",
                "NO_PROOF_AUTHORITY_FROM_FLOATING_POINT_SPECTRA",
            ),
        }


def truncated_liouville_control(terms: int = 4) -> dict[str, object]:
    """Return a finite approximation to Liouville's constant without mislabelling it.

    A finite floating-point truncation is rational in the machine model and is
    therefore not itself a Liouville number.  It is useful only as a numerical
    control with unusually separated decimal scales.
    """

    if terms < 1 or terms > 8:
        raise ValueError("terms must be between 1 and 8")
    value = sum(10.0 ** (-math.factorial(n)) for n in range(1, terms + 1))
    return {
        "label": "TRUNCATED_LIOUVILLE_APPROXIMATION",
        "terms": terms,
        "value": float(value),
        "is_exact_liouville_number": False,
        "authority": T1_AUTHORITY,
    }


def build_scale_controls() -> dict[str, float]:
    """Return the fixed specificity-control family used by the φ probe.

    The last entry is a *finite truncation* of Liouville's constant and carries
    no claim about the Diophantine class of its machine representation.
    """

    return {
        "uniform": 1.0,
        "phi": (1.0 + math.sqrt(5.0)) / 2.0,
        "sqrt2": math.sqrt(2.0),
        "sqrt3": math.sqrt(3.0),
        "e": math.e,
        "pi": math.pi,
        "liouville_trunc4": float(truncated_liouville_control(4)["value"]),
    }


def run_convergence_matrix(
    configs: Mapping[str, SpectralProbeConfig],
    *,
    scale_factor: float,
) -> dict[str, object]:
    """Run a finite convergence matrix without inferring an infinite limit.

    This is a diagnostic matrix over explicitly supplied finite configurations.
    Stability across these rows may motivate analysis, but never establishes a
    liminf, global positivity, or RH.
    """

    if not configs:
        raise ValueError("at least one convergence configuration is required")
    if not math.isfinite(scale_factor) or scale_factor <= 0.0:
        raise ValueError("scale_factor must be finite and positive")

    cases: dict[str, dict[str, object]] = {}
    for label, config in configs.items():
        if not isinstance(label, str) or not label:
            raise ValueError("convergence labels must be non-empty strings")
        if not isinstance(config, SpectralProbeConfig):
            raise TypeError("each convergence case must use SpectralProbeConfig")
        result = WeilSpectralInertiaProbe(config).solve_generalized_inertia(scale_factor)
        cases[label] = {
            "config": asdict(config),
            "scale": float(scale_factor),
            **result.to_dict(),
            "authority": T1_AUTHORITY,
            "global_weil_positivity_proven": False,
            "rh_proven": False,
        }

    return {
        "schema_version": "1.0.0",
        "authority": T1_AUTHORITY,
        "scale": float(scale_factor),
        "cases": cases,
        "liminf_proven": False,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "interpretation": "FINITE_CONVERGENCE_DIAGNOSTIC_ONLY",
    }


def verify_reference_fixture(
    observed: Mapping[str, Any],
    fixture: Mapping[str, Any],
) -> dict[str, object]:
    """Verify a bounded T1 replay fixture without converting it into proof authority.

    Inertia counts are discrete and must match exactly.  ``lambda_min`` is a
    floating-point quantity and is therefore checked against a committed closed
    interval rather than by byte/hash equality.
    """

    errors: list[str] = []
    if observed.get("authority") != T1_AUTHORITY:
        errors.append("OBSERVED_AUTHORITY_MISMATCH")
    if fixture.get("authority") != T1_AUTHORITY:
        errors.append("FIXTURE_AUTHORITY_MISMATCH")
    if observed.get("global_weil_positivity_proven") is not False:
        errors.append("OBSERVED_GLOBAL_POSITIVITY_MUST_BE_FALSE")
    if observed.get("rh_proven") is not False:
        errors.append("OBSERVED_RH_PROVEN_MUST_BE_FALSE")

    observed_results = observed.get("results")
    expected = fixture.get("expected")
    if not isinstance(observed_results, Mapping):
        errors.append("OBSERVED_RESULTS_INVALID")
        observed_results = {}
    if not isinstance(expected, Mapping) or not expected:
        errors.append("FIXTURE_EXPECTED_INVALID")
        expected = {}

    for label, requirement in expected.items():
        if label not in observed_results:
            errors.append(f"{label}:MISSING_OBSERVED_RESULT")
            continue
        if not isinstance(requirement, Mapping):
            errors.append(f"{label}:FIXTURE_REQUIREMENT_INVALID")
            continue
        actual = observed_results[label]
        if not isinstance(actual, Mapping):
            errors.append(f"{label}:OBSERVED_RESULT_INVALID")
            continue

        expected_nu = requirement.get("nu_minus")
        actual_nu = actual.get("nu_minus")
        if isinstance(expected_nu, bool) or not isinstance(expected_nu, int):
            errors.append(f"{label}:NU_MINUS_FIXTURE_INVALID")
        elif actual_nu != expected_nu:
            errors.append(f"{label}:NU_MINUS_MISMATCH")

        interval = requirement.get("lambda_min_interval")
        if (
            not isinstance(interval, (list, tuple))
            or len(interval) != 2
            or isinstance(interval[0], bool)
            or isinstance(interval[1], bool)
        ):
            errors.append(f"{label}:LAMBDA_INTERVAL_INVALID")
            continue
        try:
            lower = float(interval[0])
            upper = float(interval[1])
            value = float(actual.get("lambda_min"))
        except (TypeError, ValueError):
            errors.append(f"{label}:LAMBDA_VALUE_INVALID")
            continue
        if not all(math.isfinite(x) for x in (lower, upper, value)) or lower > upper:
            errors.append(f"{label}:LAMBDA_INTERVAL_INVALID")
        elif not lower <= value <= upper:
            errors.append(f"{label}:LAMBDA_MIN_OUTSIDE_INTERVAL")

    return {
        "schema_version": "1.0.0",
        "authority": T1_AUTHORITY,
        "reproduced": not errors,
        "errors": tuple(sorted(set(errors))),
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "proof_authority": False,
    }
