"""Exact fixed-point arithmetic for QuantumManifold Scheduler v0.1.

The canonical scheduler domain is integer-only. This module implements the
normative §4 arithmetic without floating-point conversion and without granting
execution or epistemic authority.
"""
from __future__ import annotations

PPM = 1_000_000
MAX_SAFE_CANONICAL_INT = 9_007_199_254_740_991


def require_canonical_metric(value: object) -> int:
    """Return a canonical non-negative integer or fail closed."""
    if type(value) is not int or value < 0:
        raise ValueError("FIXED_POINT_DOMAIN_ERROR")
    if value > MAX_SAFE_CANONICAL_INT:
        raise ValueError("SCORE_RANGE_EXCEEDED")
    return value


def require_positive_stabilizer(epsilon_ppm: object) -> int:
    """Validate the strictly positive epsilon stabilizer."""
    if type(epsilon_ppm) is not int or epsilon_ppm <= 0:
        raise ValueError("INVALID_STABILIZER")
    if epsilon_ppm > MAX_SAFE_CANONICAL_INT:
        raise ValueError("SCORE_RANGE_EXCEEDED")
    return epsilon_ppm


def mul_ppm(x: object, y: object) -> int:
    """Compute floor(x*y/PPM) using exact non-negative integer arithmetic."""
    x_int = require_canonical_metric(x)
    y_int = require_canonical_metric(y)
    return (x_int * y_int) // PPM


def ranking_score_ppm(
    *,
    alpha_ppm: object,
    information_gain_ppm: object,
    beta_ppm: object,
    closure_leverage_ppm: object,
    gamma_ppm: object,
    falsification_value_ppm: object,
    epsilon_ppm: object,
    cost_ppm: object,
) -> int:
    """Compute the normative v0.1 fixed-point ranking score exactly."""
    epsilon_int = require_positive_stabilizer(epsilon_ppm)
    cost_int = require_canonical_metric(cost_ppm)

    weighted_ig_ppm = mul_ppm(alpha_ppm, information_gain_ppm)
    weighted_l_ppm = mul_ppm(beta_ppm, closure_leverage_ppm)
    weighted_f_ppm = mul_ppm(gamma_ppm, falsification_value_ppm)

    numerator_ppm = weighted_ig_ppm + weighted_l_ppm + weighted_f_ppm
    denominator_ppm = epsilon_int + cost_int
    if denominator_ppm <= 0:
        raise ValueError("INVALID_STABILIZER")

    result = (numerator_ppm * PPM) // denominator_ppm
    return require_canonical_metric(result)
