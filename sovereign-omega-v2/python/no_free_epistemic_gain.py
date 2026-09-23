"""AEGIS Ω — No-Free Epistemic Gain / Conservative Consensus V1.

A state is:
    (claims, authority, loss_uncertainty_bps)

The conservative order says x <=E y when x is no epistemically stronger than y:
- claims(x) is a subset of claims(y);
- authority(x) <= authority(y);
- uncertainty(x) >= uncertainty(y).

The canonical conservative meet is:
    (claims intersection, min authority, max uncertainty).

This module does not prove claim truth and grants no authority.
"""
from __future__ import annotations

from dataclasses import dataclass

from epistemic_authority_conservation import AuthorityLevel


@dataclass(frozen=True)
class EpistemicStateV1:
    claims: frozenset[str]
    authority: AuthorityLevel
    uncertainty_bps: int

    def __post_init__(self) -> None:
        if not isinstance(self.claims, frozenset):
            raise ValueError("CLAIMS_MUST_BE_FROZENSET")
        if not all(isinstance(item, str) and item for item in self.claims):
            raise ValueError("CLAIM_ID_INVALID")
        if (
            isinstance(self.uncertainty_bps, bool)
            or not isinstance(self.uncertainty_bps, int)
            or not 0 <= self.uncertainty_bps <= 10000
        ):
            raise ValueError("UNCERTAINTY_BPS_INVALID")


def epistemic_le(left: EpistemicStateV1, right: EpistemicStateV1) -> bool:
    """Return whether left is no stronger than right."""
    return (
        left.claims <= right.claims
        and left.authority <= right.authority
        and left.uncertainty_bps >= right.uncertainty_bps
    )


def conservative_meet(
    left: EpistemicStateV1,
    right: EpistemicStateV1,
) -> EpistemicStateV1:
    return EpistemicStateV1(
        claims=left.claims & right.claims,
        authority=AuthorityLevel(
            min(int(left.authority), int(right.authority))
        ),
        uncertainty_bps=max(
            left.uncertainty_bps,
            right.uncertainty_bps,
        ),
    )


def canonical_consensus(
    states: tuple[EpistemicStateV1, ...],
) -> EpistemicStateV1:
    if not states:
        raise ValueError("NONEMPTY_STATES_REQUIRED")
    current = states[0]
    for state in states[1:]:
        current = conservative_meet(current, state)
    return current


def no_free_gain_certificate(
    left: EpistemicStateV1,
    right: EpistemicStateV1,
    candidate: EpistemicStateV1,
) -> dict[str, object]:
    meet = conservative_meet(left, right)
    candidate_is_common_lower_bound = (
        epistemic_le(candidate, left)
        and epistemic_le(candidate, right)
    )
    candidate_below_meet = epistemic_le(candidate, meet)

    return {
        "schema": "AEGIS_NO_FREE_EPISTEMIC_GAIN_CERTIFICATE_V1",
        "candidate_is_common_lower_bound": candidate_is_common_lower_bound,
        "candidate_below_canonical_meet": candidate_below_meet,
        "canonical_meet_claims": sorted(meet.claims),
        "canonical_meet_authority": meet.authority.name,
        "canonical_meet_uncertainty_bps": meet.uncertainty_bps,
        "decision": (
            "PASS"
            if candidate_is_common_lower_bound and candidate_below_meet
            else "DENY"
        ),
        "authority_effect": "NONE",
    }


def verify_canonical_consensus(
    states: tuple[EpistemicStateV1, ...],
    candidate: EpistemicStateV1,
) -> dict[str, object]:
    expected = canonical_consensus(states)
    exact = candidate == expected
    return {
        "schema": "AEGIS_CANONICAL_CONSERVATIVE_CONSENSUS_V1",
        "input_count": len(states),
        "exact_meet": exact,
        "decision": "PASS" if exact else "DENY",
        "authority_effect": "NONE",
    }
