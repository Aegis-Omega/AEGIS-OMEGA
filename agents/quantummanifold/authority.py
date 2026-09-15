"""Negative authority and epistemic-transition guards for QuantumManifold v0.1.

This module cannot grant execution or epistemic authority. It only rejects
forbidden transitions that would bypass the existing Automaton-3/admission
boundary or inflate falsifier outcomes into proof claims.
"""
from __future__ import annotations

from typing import Any


def validate_role_result_transition(
    *,
    role: str,
    source_plane: str,
    destination_plane: str,
    admission_receipt: Any,
) -> None:
    """Reject any direct M4 -> M2 role-result promotion.

    An admission receipt cannot legalize this direct edge; an allowed promotion
    must travel through the separately governed admission transition instead.
    """
    _ = role, admission_receipt
    if source_plane == "M4" and destination_plane == "M2":
        raise ValueError("DIRECT_M4_TO_M2_PROMOTION_FORBIDDEN")


def validate_epistemic_transition(
    *,
    falsifier_outcome: str,
    proposed_status: str,
) -> None:
    """Reject the canonical falsifier-survival-to-proof inflation."""
    if (
        falsifier_outcome == "SURVIVED_CURRENT_FALSIFIER"
        and proposed_status == "PROVEN"
    ):
        raise ValueError("EPISTEMIC_INFLATION_FORBIDDEN")
