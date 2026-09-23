"""AEGIS Ω — Multi-Agent Conservative Consensus V1.

For a non-empty tuple of exact epistemic states, consensus is the fold of the
No-Free Epistemic Gain conservative meet.

Because the binary meet uses exact claim intersection, minimum authority and
maximum loss uncertainty, the result is the strongest common state obtainable
without a separate proof-carrying promotion transition.
"""
from __future__ import annotations

from no_free_epistemic_gain import (
    EpistemicStateV1,
    canonical_consensus,
    epistemic_le,
)


def multi_agent_consensus(
    states: tuple[EpistemicStateV1, ...],
) -> EpistemicStateV1:
    return canonical_consensus(states)


def is_common_lower_bound(
    candidate: EpistemicStateV1,
    states: tuple[EpistemicStateV1, ...],
) -> bool:
    if not states:
        raise ValueError("NONEMPTY_STATES_REQUIRED")
    return all(epistemic_le(candidate, state) for state in states)


def consensus_certificate(
    states: tuple[EpistemicStateV1, ...],
    candidate: EpistemicStateV1,
) -> dict[str, object]:
    if not states:
        raise ValueError("NONEMPTY_STATES_REQUIRED")

    expected = multi_agent_consensus(states)
    expected_is_common_lower_bound = is_common_lower_bound(
        expected, states
    )
    candidate_is_common_lower_bound = is_common_lower_bound(
        candidate, states
    )
    candidate_below_consensus = (
        epistemic_le(candidate, expected)
        if candidate_is_common_lower_bound
        else False
    )

    return {
        "schema": "AEGIS_MULTI_AGENT_CONSERVATIVE_CONSENSUS_RECEIPT_V1",
        "input_count": len(states),
        "candidate_exact_consensus": candidate == expected,
        "expected_is_common_lower_bound": expected_is_common_lower_bound,
        "candidate_is_common_lower_bound": candidate_is_common_lower_bound,
        "candidate_below_consensus": candidate_below_consensus,
        "decision": (
            "PASS_CANONICAL_CONSENSUS"
            if candidate == expected
            and expected_is_common_lower_bound
            else "PASS_COMMON_LOWER_BOUND"
            if candidate_is_common_lower_bound
            and candidate_below_consensus
            else "DENY"
        ),
        "authority_effect": "NONE",
    }
