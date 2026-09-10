#!/usr/bin/env python3
"""Scaled-integer QGI measurement binding and fail-closed model discrimination.

Numerical values in this module are bound to arXiv:2502.14535v4, not inferred to be
byte-identical to the later journal version. No float is admitted into hashed-state
candidate payloads.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

ARXIV_V4_SOURCE = "ARXIV_2502_14535V4"
COMMENT_SOURCE = "ARXIV_2504_15409V1"
REPLY_SOURCE = "ARXIV_2504_21626V1"


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_float(v) for v in value)
    return False


def validate_scaled_measurement(receipt: dict) -> None:
    """Reject non-integer numeric state so evidence can be deterministically hashed."""
    if _contains_float(receipt):
        raise ValueError("FLOAT_IN_HASHED_MEASUREMENT_STATE")

    for section in ("measurements", "apparatus", "acquisition"):
        values = receipt.get(section)
        if not isinstance(values, dict):
            raise ValueError(f"MISSING_SECTION:{section}")
        for key, value in values.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                continue
            if isinstance(value, str):
                continue
            raise ValueError(f"UNSCALED_VALUE:{section}.{key}")


def build_measurement_receipt() -> dict:
    receipt = {
        "schema": "AEGIS_QGI_SCALED_MEASUREMENT_V2",
        "source": {
            "source_id": ARXIV_V4_SOURCE,
            "arxiv_id": "2502.14535",
            "version": 4,
            "version_date": "2025-12-07",
            "scope_note": "NUMERIC_BINDING_TO_ARXIV_V4_NOT_JOURNAL_BYTE_IDENTITY",
        },
        "measurements": {
            "oscillation_count_approx": 13,
            "phase_span_millirad": 80000,
            "blind_residual_basis_points": 250,
            "relative_phase_noise_basis_points": 130,
            "visibility_start_basis_points": 8000,
            "visibility_end_basis_points": 2000,
            "free_fall_duration_max_us": 2000,
        },
        "apparatus": {
            "atom_species": "RB87",
            "atom_chip_distance_um": 113,
            "kick_duration_us": 80,
            "effective_delay_us": 77,
            "effective_g_micrometre_per_s2": 9910000,
            "maximum_separation_nm": 7500,
            "kick_current_uncertainty_ppm": 5000,
            "second_order_zeeman_accel_micrometre_per_s2": 100000,
        },
        "acquisition": {
            "experimental_cycles": 633,
            "cycle_duration_s": 30,
            "reported_acquisition_minutes": 318,
        },
        "epistemic_boundary": {
            "direct_point_level_dataset_bound": False,
            "journal_numeric_identity_verified": False,
            "mechanism_uniquely_identified": False,
        },
    }
    validate_scaled_measurement(receipt)
    return receipt


def _fraction_payload(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}


def cubic_prefactor_identity() -> dict:
    """Show the published-model degeneracy under levitation + mass equivalence."""
    qgi = Fraction(-1, 3)
    comment_under_link = Fraction(-1, 3)
    return {
        "normalization": "m*g^2*T^3/hbar",
        "assumptions": ["LEVITATION_F_MAG_EQUALS_MG_G", "MASS_EQUIVALENCE_MI_EQUALS_MG"],
        "qgi_normalized_prefactor": _fraction_payload(qgi),
        "comment_normalized_prefactor": _fraction_payload(comment_under_link),
        "degenerate_under_levitation_and_mass_equivalence": qgi == comment_under_link,
        "authority_effect": "NONE",
    }


def discriminate_published_models(receipt: dict) -> dict:
    validate_scaled_measurement(receipt)
    point_level = receipt["epistemic_boundary"]["direct_point_level_dataset_bound"]
    degenerate = cubic_prefactor_identity()["degenerate_under_levitation_and_mass_equivalence"]

    reasons = []
    if not point_level:
        reasons.append("NO_POINT_LEVEL_PHASE_DATA")
    if degenerate:
        reasons.append("PUBLISHED_MODEL_DEGENERACY")
    reasons.append("APPARATUS_SYSTEMATICS_MATERIAL")

    return {
        "schema": "AEGIS_QGI_MODEL_DISCRIMINATION_V2",
        "decision": "NO_UNIQUE_MODEL_SELECTION",
        "authority_effect": "NONE",
        "reason_codes": reasons,
        "models": {
            "QGI_GRAVITY_EP": {
                "source_id": ARXIV_V4_SOURCE,
                "status": "REQUIRES_POINT_LEVEL_REPLAY",
                "observable": "PHASE_VS_TIME_AND_CONTROL_PARAMETERS",
            },
            "MAGNETIC_RECOIL": {
                "source_id": COMMENT_SOURCE,
                "status": "REQUIRES_POINT_LEVEL_REPLAY",
                "observable": "PHASE_VS_MAGNETIC_GRADIENT_AND_INERTIAL_MASS",
            },
            "QGI_REPLY_GENERALIZED": {
                "source_id": REPLY_SOURCE,
                "status": "REQUIRES_COUNTERFACTUAL_REPLAY",
                "observable": "PHASE_WITH_LEVITATION_BROKEN_BUT_CLOSING_PRESERVED",
            },
            "APPARATUS_SYSTEMATICS": {
                "source_id": ARXIV_V4_SOURCE,
                "status": "REQUIRES_NUISANCE_PROPAGATION",
                "observable": "CURVATURE_ROTATION_INTERACTION_CURRENT_AND_FIELD_SENSITIVITY",
            },
        },
        "identifiability": cubic_prefactor_identity(),
        "next_falsifiers": [
            "BREAK_LEVITATION_DEGENERACY",
            "INDEPENDENTLY_BIND_MAGNETIC_GRADIENT",
            "REPLAY_RAW_PHASE_VS_TIME",
            "PROPAGATE_APPARATUS_SYSTEMATICS",
        ],
        "promotion_boundary": {
            "mechanistic_winner": "NOT_ESTABLISHED",
            "equivalence_principle_status": "CONSISTENT_IN_REPORTED_REGIME_NOT_UNIQUELY_CAUSAL",
            "quantum_gravity_status": "NOT_TESTED",
        },
    }
