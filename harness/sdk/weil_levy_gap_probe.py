"""Finite-cutoff Lévy--Khintchine decomposition for the Weil spectral probe.

For the finite prime-power cutoff used by :mod:`weil_spectral_inertia_probe`,
write

    S_P(t) = Re psi(1/4 + i t/2) - log(pi)
             - sum_{p^k <= P} 2 log(p) / p^(k/2) cos(k log(p) t).

After normalization at t=0,

    eta_P(t) := S_P(t) - S_P(0)

is a real conditionally-negative-definite function of Lévy--Khintchine form:

    eta_P(t)
      = integral_R (1 - cos(t x)) nu_infty(dx)
        + sum_{p^k <= P} 2 w_{p,k} (1 - cos(a_{p,k} t)),

where

    nu_infty(dx) = exp(-|x|/2) / (1 - exp(-2|x|)) dx,
    w_{p,k} = log(p) / p^(k/2),
    a_{p,k} = k log(p).

Thus the *normalized finite-cutoff* symbol is the exponent of a symmetric
Lévy process.  The original S_P is not itself a standard Lévy exponent when
S_P(0) != 0; in the observed Weil finite sections S_P(0) < 0, so the operator
is a positive Lévy Dirichlet form plus an adverse negative scalar shift.

The undeformed P -> infinity prime jump measure is deliberately NOT promoted
to a standard Lévy measure: its mass outside the unit ball contains
2 sum_p log(p)/sqrt(p), which diverges (already by comparison with Euler's
divergent sum over reciprocal primes).  Any infinite-process interpretation
therefore requires an additional renormalization/tempering theorem.

All outputs here are T1 diagnostics.  They do not establish the concrete
infinite Weil operator, global Weil positivity, the Weil criterion, or RH.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import scipy.linalg as la
import scipy.special as sp

from harness.sdk.weil_spectral_inertia_probe import (
    T1_AUTHORITY,
    WeilSpectralInertiaProbe,
)


ARCHIMEDEAN_LEVY_DENSITY = "exp(-abs(x)/2)/(1-exp(-2*abs(x)))"
INFINITE_PRIME_LIMIT_REASON = "PRIME_JUMP_MASS_OUTSIDE_UNIT_BALL_DIVERGES"
METHOD = "FINITE_CUTOFF_LEVY_KHINTCHINE_PLUS_SCALAR_SPECTRAL_OFFSET"


def _normalized_components(
    probe: WeilSpectralInertiaProbe,
    t_grid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Return (eta, arch_delta, prime_jump, S(0), normalization_error)."""

    t_grid = np.asarray(t_grid, dtype=float)
    arch_zero = float(np.real(sp.digamma(0.25)))
    arch_delta = np.real(sp.digamma(0.25 + 0.5j * t_grid)) - arch_zero

    prime_jump = np.zeros_like(t_grid, dtype=float)
    for term in probe.prime_power_terms:
        prime_jump += 2.0 * term.weight * (1.0 - np.cos(term.shift * t_grid))

    eta = arch_delta + prime_jump
    symbol_zero = float(probe.compute_symbol(np.array([0.0], dtype=float))[0])
    normalized_from_original = probe.compute_symbol(t_grid) - symbol_zero
    normalization_error = float(np.max(np.abs(eta - normalized_from_original))) if eta.size else 0.0
    return eta, arch_delta, prime_jump, symbol_zero, normalization_error


def _reduce_with_moment_constraint(
    matrix: np.ndarray,
    gram: np.ndarray,
    moment_vector: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    basis = la.null_space(np.asarray(moment_vector, dtype=float).reshape(1, -1))
    expected_shape = (matrix.shape[0], matrix.shape[0] - 1)
    if basis.shape != expected_shape:
        raise RuntimeError("moment nullspace does not have expected codimension one")

    reduced_matrix = basis.T @ matrix @ basis
    reduced_gram = basis.T @ gram @ basis
    reduced_matrix = 0.5 * (reduced_matrix + reduced_matrix.T)
    reduced_gram = 0.5 * (reduced_gram + reduced_gram.T)
    if float(np.min(la.eigvalsh(reduced_gram, check_finite=True))) <= 0.0:
        raise ValueError("reduced Gram matrix is not positive definite")
    return reduced_matrix, reduced_gram, basis


def run_levy_gap_probe(
    probe: WeilSpectralInertiaProbe,
    *,
    scale_factor: float = 1.0,
) -> dict[str, Any]:
    """Diagnose the finite Lévy Dirichlet gap without minting proof authority."""

    if not isinstance(probe, WeilSpectralInertiaProbe):
        raise TypeError("probe must be WeilSpectralInertiaProbe")
    if not math.isfinite(scale_factor) or scale_factor <= 0.0:
        raise ValueError("scale_factor must be finite and positive")

    cfg = probe.config
    t_grid = np.linspace(-cfg.t_bound, cfg.t_bound, cfg.n_quad, dtype=float)
    dt = float(t_grid[1] - t_grid[0])
    eta, arch_delta, prime_jump, spectral_offset, normalization_error = _normalized_components(
        probe, t_grid
    )
    eta_zero, _, _, _, eta_zero_error = _normalized_components(
        probe, np.array([0.0], dtype=float)
    )

    arguments = (cfg.tau * scale_factor / math.pi) * t_grid[None, :] - probe.k_indices[:, None]
    psi = np.sinc(arguments)
    w_quad = dt / (2.0 * math.pi)

    original_symbol = probe.compute_symbol(t_grid)
    matrix_weil = (psi * (original_symbol * w_quad)) @ psi.T
    matrix_eta = (psi * (eta * w_quad)) @ psi.T
    gram = (psi * w_quad) @ psi.T
    moment_vector = np.sum(psi * w_quad, axis=1)

    matrix_weil = 0.5 * (matrix_weil + matrix_weil.T)
    matrix_eta = 0.5 * (matrix_eta + matrix_eta.T)
    gram = 0.5 * (gram + gram.T)

    reduced_weil, reduced_gram, basis = _reduce_with_moment_constraint(
        matrix_weil, gram, moment_vector
    )
    reduced_eta = basis.T @ matrix_eta @ basis
    reduced_eta = 0.5 * (reduced_eta + reduced_eta.T)

    reconstructed_weil = reduced_eta + spectral_offset * reduced_gram
    matrix_error = float(np.max(np.abs(reduced_weil - reconstructed_weil)))

    weil_eigs = np.asarray(la.eigvalsh(reduced_weil, reduced_gram, check_finite=True), dtype=float)
    eta_eigs = np.asarray(la.eigvalsh(reduced_eta, reduced_gram, check_finite=True), dtype=float)
    weil_lambda_min = float(np.min(weil_eigs)) if weil_eigs.size else 0.0
    levy_gap_lambda_min = float(np.min(eta_eigs)) if eta_eigs.size else 0.0
    lambda_shift_error = abs(weil_lambda_min - (levy_gap_lambda_min + spectral_offset))

    adverse_shift = max(0.0, -spectral_offset)
    gap_margin = levy_gap_lambda_min - adverse_shift
    finite_section_gap_closed = gap_margin >= -cfg.negative_tolerance

    prime_jump_total_mass = 2.0 * sum(term.weight for term in probe.prime_power_terms)
    prime_jump_mass_outside_unit = 2.0 * sum(
        term.weight for term in probe.prime_power_terms if abs(term.shift) > 1.0
    )

    return {
        "schema_version": "1.0.0",
        "authority": T1_AUTHORITY,
        "method": METHOD,
        "scale_factor": float(scale_factor),
        "config": {
            "tau": cfg.tau,
            "p_cutoff": cfg.p_cutoff,
            "k_basis_dim": cfg.k_basis_dim,
            "n_quad": cfg.n_quad,
            "t_bound": cfg.t_bound,
            "max_prime_shift": cfg.max_prime_shift,
            "zero_tolerance": cfg.zero_tolerance,
            "negative_tolerance": cfg.negative_tolerance,
        },
        "prime_power_count": probe.prime_power_count,
        "archimedean_levy_density": ARCHIMEDEAN_LEVY_DENSITY,
        "finite_cutoff_standard_levy_measure": True,
        "full_symbol_is_standard_levy_exponent": abs(spectral_offset) <= 1e-12,
        "infinite_prime_measure_standard_levy_limit": False,
        "infinite_prime_limit_reason": INFINITE_PRIME_LIMIT_REASON,
        "prime_jump_total_mass": float(prime_jump_total_mass),
        "prime_jump_mass_outside_unit": float(prime_jump_mass_outside_unit),
        "normalized_exponent_at_zero": float(eta_zero[0]),
        "normalized_exponent_zero_identity_error": float(eta_zero_error),
        "normalized_exponent_grid_min": float(np.min(eta)),
        "normalized_exponent_grid_max": float(np.max(eta)),
        "archimedean_increment_grid_min": float(np.min(arch_delta)),
        "prime_jump_increment_grid_min": float(np.min(prime_jump)),
        "symbol_normalization_max_abs_error": normalization_error,
        "spectral_offset": spectral_offset,
        "adverse_shift_magnitude": adverse_shift,
        "levy_gap_lambda_min": levy_gap_lambda_min,
        "weil_lambda_min": weil_lambda_min,
        "gap_margin": float(gap_margin),
        "finite_section_gap_closed": bool(finite_section_gap_closed),
        "uniform_gap_closed": bool(finite_section_gap_closed) if math.isclose(scale_factor, 1.0) else False,
        "matrix_decomposition_max_abs_error": matrix_error,
        "lambda_shift_identity_abs_error": float(lambda_shift_error),
        "conditional_negative_definiteness_proven_infinite_limit": False,
        "uniform_poincare_gap_proven": False,
        "concrete_infinite_weil_operator_bound": False,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "non_claims": (
            "FINITE_CUTOFF_LEVY_DECOMPOSITION_DOES_NOT_DEFINE_THE_UNTRUNCATED_PRIME_PROCESS",
            "NEGATIVE_SCALAR_OFFSET_IS_NOT_MARKOV_KILLING",
            "NO_UNIFORM_POINCARE_OR_SPECTRAL_GAP_THEOREM",
            "NO_GLOBAL_WEIL_POSITIVITY_OR_RH_AUTHORITY",
        ),
    }
