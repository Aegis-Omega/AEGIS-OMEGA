"""QuantumManifold Scheduler v0.1 Phase-1 contract surface.

This module is an authority-zero scheduling surface.  The first contract commit
intentionally exposes typed immutable records while leaving the four focused
scheduler operations unimplemented so the preregistered semantic RED tests can
be observed before any ranking behavior is added.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol


@dataclass(frozen=True)
class RealityThreadV1:
    thread_id: str
    source_head_sha: str
    claim_digest: str
    semantic_fingerprint: str
    verified_lineage_root: str
    active: bool = True


@dataclass(frozen=True)
class OpenObligationV1:
    obligation_id: str
    obligation_digest: str
    source_head_sha: str
    downstream_threads: tuple[RealityThreadV1, ...]


@dataclass(frozen=True)
class CandidateActionV1:
    action_id: str
    candidate_action_digest: str
    source_head_sha: str
    obligation_digest: str
    closure_prior_root: str | None
    information_gain_ppm: int
    falsification_value_ppm: int
    compute_cost_ppm: int
    evidence_cost_ppm: int
    latency_cost_ppm: int
    recommended_role: str


@dataclass(frozen=True)
class ClosurePriorV1:
    prior_root: str
    obligation_digest: str
    candidate_action_digest: str
    p_close_ppm: int
    estimator_kind: str
    estimator_root: str
    policy_digest: str
    source_head_sha: str
    verification_receipt_root: str


class TrustedClosurePriorStore(Protocol):
    def fetch_verified(self, prior_root: str) -> ClosurePriorV1: ...


@dataclass(frozen=True)
class DispatchProposalV1:
    receipt_kind: str
    baseline_digest: str
    source_head_sha: str
    reality_snapshot_digest: str
    obligation_set_digest: str
    candidate_set_digest: str
    scheduler_policy_digest: str
    selected_action_digest: str
    information_gain_ppm: int
    closure_leverage_ppm: int
    falsification_value_ppm: int
    cost_ppm: int
    ranking_score_ppm: int
    recommended_role: str
    authority_effect: str = field(default="NONE", init=False)
    can_admit_claim: bool = field(default=False, init=False)
    can_advance_authority: bool = field(default=False, init=False)


class QuantumManifoldError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class QuantumManifoldSchedulerV1:
    """Authority-zero Phase-1 scheduler contract.

    Behavior is intentionally absent in this commit.  Each operation is added
    only after its preregistered test has been observed RED at an exact head.
    """

    def __init__(
        self,
        *,
        policy: Mapping[str, object],
        closure_prior_store: TrustedClosurePriorStore | None = None,
    ) -> None:
        self._policy = dict(policy)
        self._closure_prior_store = closure_prior_store

    def centrality_ppm(
        self,
        obligation: OpenObligationV1,
        active_terminal_threads: tuple[RealityThreadV1, ...],
    ) -> int:
        raise NotImplementedError

    def closure_leverage_ppm(
        self,
        action: CandidateActionV1,
        obligation: OpenObligationV1,
        active_terminal_threads: tuple[RealityThreadV1, ...],
    ) -> int:
        raise NotImplementedError

    def assert_current_head(self, bound_head_sha: str, current_head_sha: str) -> None:
        raise NotImplementedError

    def build_proposal(
        self,
        *,
        baseline_digest: str,
        source_head_sha: str,
        current_head_sha: str,
        reality_snapshot_digest: str,
        obligation_set_digest: str,
        candidate_set_digest: str,
        scheduler_policy_digest: str,
        selected_action_digest: str,
        information_gain_ppm: int,
        closure_leverage_ppm: int,
        falsification_value_ppm: int,
        cost_ppm: int,
        ranking_score_ppm: int,
        recommended_role: str,
    ) -> DispatchProposalV1:
        raise NotImplementedError
