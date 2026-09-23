"""AEGIS Ω — Conservative Consensus CRDT V1.

The existing epistemic-strength order is reversed into a safety order:

    x <=S y  iff  y <=E x

Under this safety order the No-Free conservative meet becomes a join:
claims intersect, authority takes the minimum, and declared loss uncertainty
takes the maximum.

CRDT-native local updates must be inflationary in <=S, i.e. they may only
weaken or preserve epistemic strength. Any strengthening must leave the CRDT
lane and use proof-carrying promotion.
"""
from __future__ import annotations

from no_free_epistemic_gain import (
    EpistemicStateV1,
    conservative_meet,
    epistemic_le,
)
from multi_agent_conservative_consensus import multi_agent_consensus


def safety_le(left: EpistemicStateV1, right: EpistemicStateV1) -> bool:
    """Safety-order comparison: right is at least as conservative as left."""
    return epistemic_le(right, left)


def crdt_merge(
    left: EpistemicStateV1,
    right: EpistemicStateV1,
) -> EpistemicStateV1:
    return conservative_meet(left, right)


def safe_local_update(
    old: EpistemicStateV1,
    new: EpistemicStateV1,
) -> bool:
    """State-based CRDT updates must be inflationary in the safety order."""
    return safety_le(old, new)


def reconcile_nonempty(
    delivered_states: tuple[EpistemicStateV1, ...],
) -> EpistemicStateV1:
    if not delivered_states:
        raise ValueError("NONEMPTY_DELIVERY_REQUIRED")
    return multi_agent_consensus(delivered_states)


def convergence_certificate(
    left_deliveries: tuple[EpistemicStateV1, ...],
    right_deliveries: tuple[EpistemicStateV1, ...],
) -> dict[str, object]:
    if not left_deliveries or not right_deliveries:
        raise ValueError("NONEMPTY_DELIVERY_REQUIRED")

    left = reconcile_nonempty(left_deliveries)
    right = reconcile_nonempty(right_deliveries)
    converged = left == right

    return {
        "schema": "AEGIS_CONSERVATIVE_CONSENSUS_CRDT_RECEIPT_V1",
        "left_count": len(left_deliveries),
        "right_count": len(right_deliveries),
        "converged": converged,
        "decision": "PASS" if converged else "DIVERGED",
        "network_eventual_delivery": "ASSUMED_NOT_VERIFIED",
        "authority_effect": "NONE",
    }
