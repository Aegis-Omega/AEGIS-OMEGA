"""AEGIS Ω — Conservative Epistemic Semilattice V1.

For loss-bearing epistemic summaries:
    merge((a,u), (b,v)) = (min(a,b), max(u,v))

where a is authority and u is declared loss uncertainty in basis points.

This operation is conservative in both coordinates:
- authority cannot increase;
- loss uncertainty cannot decrease.

The operation is commutative, associative and idempotent.
"""
from __future__ import annotations

from dataclasses import dataclass

from epistemic_authority_conservation import AuthorityLevel


@dataclass(frozen=True)
class LossBearingEpistemicStateV1:
    authority: AuthorityLevel
    uncertainty_bps: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.uncertainty_bps, bool)
            or not isinstance(self.uncertainty_bps, int)
            or not 0 <= self.uncertainty_bps <= 10000
        ):
            raise ValueError("UNCERTAINTY_BPS_INVALID")


def conservative_merge(
    left: LossBearingEpistemicStateV1,
    right: LossBearingEpistemicStateV1,
) -> LossBearingEpistemicStateV1:
    return LossBearingEpistemicStateV1(
        authority=AuthorityLevel(min(int(left.authority), int(right.authority))),
        uncertainty_bps=max(left.uncertainty_bps, right.uncertainty_bps),
    )


def merge_all(
    states: tuple[LossBearingEpistemicStateV1, ...],
) -> LossBearingEpistemicStateV1:
    if not states:
        raise ValueError("NONEMPTY_STATES_REQUIRED")
    current = states[0]
    for state in states[1:]:
        current = conservative_merge(current, state)
    return current


def conservative_certificate(
    states: tuple[LossBearingEpistemicStateV1, ...],
) -> dict[str, object]:
    result = merge_all(states)
    return {
        "schema": "AEGIS_CONSERVATIVE_EPISTEMIC_SEMILATTICE_V1",
        "input_count": len(states),
        "authority": result.authority.name,
        "uncertainty_bps": result.uncertainty_bps,
        "authority_equals_global_min": int(result.authority)
        == min(int(state.authority) for state in states),
        "uncertainty_equals_global_max": result.uncertainty_bps
        == max(state.uncertainty_bps for state in states),
        "authority_effect": "NONE",
    }
