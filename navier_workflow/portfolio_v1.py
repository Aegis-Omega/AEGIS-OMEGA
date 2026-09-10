"""Deterministic bounded portfolio routing for AEGIS Navier workflow V1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lane:
    lane_id: str
    problem_class: str
    progress_signal: int
    transfer_utility: int
    verification_density: int
    open_obligation_penalty: int
    correlated_failure_penalty: int
    status: str


def priority_score(lane: Lane) -> int:
    """Routing score only. It never changes the lane's epistemic status."""
    return max(
        0,
        lane.progress_signal
        + lane.transfer_utility
        + lane.verification_density
        - lane.open_obligation_penalty
        - lane.correlated_failure_penalty,
    )


def allocate_budget(
    lanes: list[Lane], total_budget: int, diversity_floor: int
) -> dict[str, int]:
    if total_budget < 0 or diversity_floor < 0:
        raise ValueError("budget values must be non-negative integers")

    active = [lane for lane in lanes if lane.status != "FALSIFIED"]
    if total_budget < diversity_floor * len(active):
        raise ValueError("budget below diversity floor")

    result = {lane.lane_id: 0 for lane in lanes}
    for lane in active:
        result[lane.lane_id] = diversity_floor

    remaining = total_budget - diversity_floor * len(active)
    ranked = sorted(active, key=lambda lane: (-priority_score(lane), lane.lane_id))

    if ranked:
        for index in range(remaining):
            result[ranked[index % len(ranked)].lane_id] += 1

    return result
