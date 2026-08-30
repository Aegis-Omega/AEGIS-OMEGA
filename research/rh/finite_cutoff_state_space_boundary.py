"""Finite-cutoff state-space boundary for the Weil spectral research lane.

This module records a deliberately narrow obstruction.  For a finite prime-
power cutoff ``P`` the repository spectral surrogate is

    S_P(t) = Re psi(1/4 + i t/2) - log(pi)
             - sum_{p^k <= P} 2 log(p) / p^(k/2) cos(k log(p) t).

At ``t = 0`` the exact quarter-digamma identity gives

    S_P(0) = -gamma - pi/2 - 3 log(2) - log(pi)
             - 2 sum_{p^k <= P} log(p) / p^(k/2) < 0.

Because ``S_P`` is continuous, there is a neighbourhood of zero on which it is
negative.  A nonzero odd ``C_c^infinity`` spectral bump supported in that
neighbourhood has zero integral and produces a strictly negative multiplier
quadratic form on this *spectral surrogate* state space.

The load-bearing boundary is Paley--Wiener admissibility.  A nonzero compactly
supported smooth function of the spectral variable is not entire; therefore it
is not silently identified with the Paley--Wiener image of a compactly
supported classical Weil test function.  The local surrogate counterexample
therefore does NOT refute the classical Weil admissible space, an untruncated
renormalized Weil form, global Weil positivity, the Weil criterion, or RH.

The analytic receipt below is an argument ledger, not proof-assistant
attestation.  ``evaluate_odd_bump_witness`` is a T1 floating-point replay only.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np

from harness.sdk.weil_spectral_inertia_probe import (
    SpectralProbeConfig,
    WeilSpectralInertiaProbe,
)


ANALYTIC_AUTHORITY = "ANALYTIC_ARGUMENT_LEDGER_NOT_PROOF_ASSISTANT"
NUMERICAL_AUTHORITY = "T1_NUMERICAL_WITNESS"
CLASSIFICATION = "REFUTED_ON_SPECTRAL_CCINFINITY_ZERO_MOMENT_SURROGATE"
DIGAMMA_QUARTER_IDENTITY = "psi(1/4)=-gamma-pi/2-3*log(2)"


def _validate_cutoff(p_cutoff: int) -> int:
    if isinstance(p_cutoff, bool) or not isinstance(p_cutoff, int) or p_cutoff < 2:
        raise ValueError("p_cutoff must be an integer >= 2")
    return p_cutoff


def _probe_for_cutoff(p_cutoff: int) -> WeilSpectralInertiaProbe:
    p_cutoff = _validate_cutoff(p_cutoff)
    # Only the symbol and prime-power list are used here; the tiny Galerkin
    # configuration avoids coupling this boundary ledger to a large quadrature.
    return WeilSpectralInertiaProbe(
        SpectralProbeConfig(
            tau=2.0,
            p_cutoff=p_cutoff,
            k_basis_dim=1,
            n_quad=32,
            t_bound=1.0,
        )
    )


def _content_address(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_state_space_refutation_receipt(*, p_cutoff: int) -> dict[str, Any]:
    """Return the deterministic analytic boundary ledger for one finite cutoff.

    The logical route is independent of the numerical value of the witness:
    the quarter-digamma identity makes ``S_P(0)`` strictly negative, the finite
    cosine sum makes ``S_P`` continuous, and standard bump-function existence
    supplies an odd compactly supported spectral witness.  The receipt keeps
    that statement separate from Paley--Wiener/classical Weil admissibility.
    """

    probe = _probe_for_cutoff(p_cutoff)
    symbol_at_zero = float(probe.compute_symbol(np.array([0.0], dtype=float))[0])
    prime_weights_positive = all(term.weight > 0.0 for term in probe.prime_power_terms)
    if not prime_weights_positive:
        raise RuntimeError("finite prime-power weights must be strictly positive")
    if not symbol_at_zero < 0.0:
        raise RuntimeError("finite-cutoff symbol-at-zero sign disagrees with analytic identity")

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "authority": ANALYTIC_AUTHORITY,
        "classification": CLASSIFICATION,
        "p_cutoff": p_cutoff,
        "prime_power_count": probe.prime_power_count,
        "digamma_quarter_identity": DIGAMMA_QUARTER_IDENTITY,
        "symbol_at_zero_formula": (
            "-gamma-pi/2-3*log(2)-log(pi)"
            "-2*sum_{p^k<=P}(log(p)/p^(k/2))"
        ),
        "symbol_at_zero_numeric_diagnostic": symbol_at_zero,
        "all_prime_power_weights_strictly_positive": True,
        "symbol_at_zero_strictly_negative": True,
        "symbol_continuous_for_finite_cutoff": True,
        "negative_neighbourhood_of_zero_exists": True,
        "odd_ccinfinity_witness_exists": True,
        "zero_moment_by_odd_symmetry": True,
        "finite_cutoff_surrogate_q_negative": True,
        "spectral_witness_compact_support": True,
        "spectral_witness_entire": False,
        "paley_wiener_image_membership": False,
        "classical_weil_admissible_space_refuted": False,
        "untruncated_renormalized_weil_form_refuted": False,
        "global_weil_positivity_proven": False,
        "weil_criterion_proven": False,
        "rh_proven": False,
        "proof_assistant_verified": False,
        "load_bearing_open_bridge": (
            "PALey_WIENER_ADMISSIBLE_TEST_SPACE_TO_CONCRETE_WEIL_OPERATOR_SEMANTICS"
        ),
        "non_claims": (
            "COMPACT_SPECTRAL_BUMP_IS_NOT_PROMOTED_TO_A_PALEY_WIENER_IMAGE",
            "NO_CLASSICAL_WEIL_ADMISSIBLE_SPACE_REFUTATION",
            "NO_UNTRUNCATED_OR_RENORMALIZED_GLOBAL_OPERATOR_REFUTATION",
            "NO_GLOBAL_WEIL_POSITIVITY_WEIL_CRITERION_OR_RH_AUTHORITY",
        ),
    }
    return {**payload, "receipt_sha256": _content_address(payload)}


def evaluate_odd_bump_witness(
    *,
    p_cutoff: int,
    epsilon: float,
    n_grid: int,
) -> dict[str, Any]:
    """Numerically replay one odd compact spectral bump witness.

    ``b(t) = (t/epsilon) exp(-1/(1-(t/epsilon)^2))`` for ``|t|<epsilon``
    and zero outside is a nonzero odd ``C_c^infinity`` function.  The routine
    checks whether the requested support is contained in a numerically observed
    negative region of ``S_P`` and evaluates the corresponding multiplier form.
    This floating-point replay carries no proof authority.
    """

    probe = _probe_for_cutoff(p_cutoff)
    epsilon = float(epsilon)
    if not math.isfinite(epsilon) or epsilon <= 0.0:
        raise ValueError("epsilon must be finite and positive")
    if isinstance(n_grid, bool) or not isinstance(n_grid, int) or n_grid < 513:
        raise ValueError("n_grid must be an odd integer >= 513")
    if n_grid % 2 == 0:
        raise ValueError("n_grid must be odd so the replay grid is exactly symmetric")

    t_grid = np.linspace(-epsilon, epsilon, n_grid, dtype=float)
    x = t_grid / epsilon
    bump = np.zeros_like(t_grid)
    inside = np.abs(x) < 1.0
    denom = 1.0 - x[inside] * x[inside]
    bump[inside] = x[inside] * np.exp(-1.0 / denom)

    symbol = probe.compute_symbol(t_grid)
    active = np.abs(bump) > 0.0
    if not np.any(active):
        raise RuntimeError("odd bump construction unexpectedly produced the zero function")

    support_symbol_max = float(np.max(symbol[active]))
    support_inside_negative = support_symbol_max < 0.0
    discrete_moment = float(np.trapezoid(bump, t_grid))
    norm_sq = float(np.trapezoid(bump * bump, t_grid) / (2.0 * math.pi))
    quadratic_form = float(
        np.trapezoid(symbol * bump * bump, t_grid) / (2.0 * math.pi)
    )

    return {
        "schema_version": "1.0.0",
        "authority": NUMERICAL_AUTHORITY,
        "p_cutoff": p_cutoff,
        "epsilon": epsilon,
        "n_grid": n_grid,
        "symbol_at_zero": float(symbol[n_grid // 2]),
        "support_symbol_max": support_symbol_max,
        "support_inside_negative_symbol_region": bool(support_inside_negative),
        "discrete_moment": discrete_moment,
        "witness_norm_sq": norm_sq,
        "quadratic_form": quadratic_form,
        "spectral_witness_compact_support": True,
        "spectral_witness_entire": False,
        "paley_wiener_image_membership": False,
        "classical_weil_admissible_space_refuted": False,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "proof_authority": False,
    }
