#!/usr/bin/env python3
"""AEGIS Ω Gravity–Quantum V3 counterfactual formula simulator.

This module compares published formula forms using exact rational arithmetic. It does
not fit experimental point-level data and it does not select a physical mechanism.

Definitions:
  r = a / g
  k = m_g / m_i

QGI Eq. (3), under m_i = m_g and the paper's time convention, normalizes to
  r(r - 2) / 3.

The reply's generalized expression, after aligning the time convention, normalizes to
  r(r - 2k) / 3.

The magnetic-only expression in the comment normalizes to
  -r^2 / 3.

The reply explicitly disputes extending that magnetic-only expression away from the
levitation condition, so all off-levitation comparisons are labeled contested
counterfactual extrapolations rather than empirical model tests.
"""
from __future__ import annotations

from fractions import Fraction

QGI_SOURCE = "ARXIV_2502_14535V4"
COMMENT_SOURCE = "ARXIV_2504_15409V1"
REPLY_SOURCE = "ARXIV_2504_21626V1"


def _fraction(num: int, den: int = 1) -> Fraction:
    if isinstance(num, bool) or isinstance(den, bool):
        raise TypeError("BOOLEAN_RATIO_COMPONENT_FORBIDDEN")
    if not isinstance(num, int) or not isinstance(den, int):
        raise TypeError("RATIO_COMPONENTS_MUST_BE_INTEGERS")
    if den == 0:
        raise ValueError("ZERO_DENOMINATOR")
    return Fraction(num, den)


def _payload(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}


def qgi_eq3_mass_equal_prefactor(r_num: int, r_den: int = 1) -> dict:
    """QGI Eq. (3), normalized by m*g^2*T^3/hbar, with m_i=m_g."""
    r = _fraction(r_num, r_den)
    return _payload(r * (r - 2) / 3)


def reply_generalized_prefactor(
    r_num: int,
    r_den: int = 1,
    k_num: int = 1,
    k_den: int = 1,
) -> dict:
    """Reply Eq. (6), time-convention aligned, normalized by m_i*g^2*T^3/hbar."""
    r = _fraction(r_num, r_den)
    k = _fraction(k_num, k_den)
    return _payload(r * (r - 2 * k) / 3)


def comment_magnetic_prefactor(r_num: int, r_den: int = 1) -> dict:
    """Comment magnetic-only form, normalized by m_i*g^2*T^3/hbar."""
    r = _fraction(r_num, r_den)
    return _payload(-(r * r) / 3)


def discrimination_delta(
    r_num: int,
    r_den: int = 1,
    k_num: int = 1,
    k_den: int = 1,
) -> dict:
    """Reply-generalized minus comment-magnetic normalized prefactor."""
    r = _fraction(r_num, r_den)
    k = _fraction(k_num, k_den)
    reply = r * (r - 2 * k) / 3
    comment = -(r * r) / 3
    return _payload(reply - comment)


def published_formula_binding() -> dict:
    return {
        "schema": "AEGIS_QGI_PUBLISHED_FORMULA_BINDING_V3",
        "normalization": "m_i*g^2*T^3/hbar",
        "variables": {
            "r": "a/g",
            "k": "m_g/m_i",
        },
        "formulae": {
            "QGI_EQ3_MASS_EQUAL": {
                "source_id": QGI_SOURCE,
                "equation": 3,
                "normalized_form": "r*(r-2)/3",
                "assumptions": ["MASS_EQUALITY_MI_EQUALS_MG", "CLOSING_CONDITION"],
            },
            "REPLY_EQ6_GENERALIZED_ALIGNED": {
                "source_id": REPLY_SOURCE,
                "equation": 6,
                "normalized_form": "r*(r-2*k)/3",
                "assumptions": ["TIME_CONVENTION_ALIGNED_TO_QGI", "CLOSING_CONDITION"],
            },
            "COMMENT_EQ6_MAGNETIC_ONLY": {
                "source_id": COMMENT_SOURCE,
                "equation": 6,
                "normalized_form": "-r^2/3",
                "off_levitation_domain_status": "CONTESTED_BY_REPLY",
            },
        },
        "non_claim": "FORMULA_COMPARISON_DOES_NOT_IDENTIFY_THE_PHYSICAL_MECHANISM",
        "authority_effect": "NONE",
    }


def build_counterfactual_grid() -> dict:
    """Evaluate an exact, dimensionless mass-equal grid without empirical fitting."""
    k = Fraction(1, 1)
    ratios = [Fraction(0, 1), Fraction(1, 2), Fraction(1, 1), Fraction(3, 2), Fraction(2, 1)]
    rows = []

    for r in ratios:
        qgi = r * (r - 2) / 3
        reply = r * (r - 2 * k) / 3
        comment = -(r * r) / 3
        delta = reply - comment
        levitation = r == k
        rows.append(
            {
                "r": _payload(r),
                "k": _payload(k),
                "levitation_condition": levitation,
                "qgi_eq3_mass_equal_prefactor": _payload(qgi),
                "reply_generalized_prefactor": _payload(reply),
                "comment_magnetic_prefactor": _payload(comment),
                "reply_minus_comment": _payload(delta),
                "formula_divergence": delta != 0,
                "comment_eq6_domain_status": (
                    "LEVITATION_LINK_SATISFIED"
                    if levitation
                    else "CONTESTED_EXTRAPOLATION_OUTSIDE_LEVITATION"
                ),
            }
        )

    return {
        "schema": "AEGIS_QGI_COUNTERFACTUAL_GRID_V3",
        "scope": "ALGEBRAIC_COUNTERFACTUAL_SIMULATION_ONLY",
        "mass_ratio_k": _payload(k),
        "rows": rows,
        "empirical_model_selection": "BLOCKED",
        "point_level_data_bound": False,
        "apparatus_systematics_propagated": False,
        "authority_effect": "NONE",
    }
