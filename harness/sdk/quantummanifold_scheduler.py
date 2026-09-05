"""QuantumManifold Scheduler v0.1 Phase-1 contract surface.

This module is an authority-zero scheduling surface.  Behavior is added only
against preregistered RED contracts.  Content digests are identities/bindings;
they are never converted into numeric scheduler utility.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from harness.sdk.sovereign_execution import canonical_hash


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


def _canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _exact_non_negative_int(value: object, *, upper: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QuantumManifoldError("FIXED_POINT_DOMAIN_ERROR")
    if upper is not None and value > upper:
        raise QuantumManifoldError("FIXED_POINT_DOMAIN_ERROR")
    return value


def _lineage_class(thread: RealityThreadV1) -> str:
    if not thread.verified_lineage_root:
        raise QuantumManifoldError("UNVERIFIED_LINEAGE_ROOT")
    return canonical_hash(
        "qm-lineage-class-v1",
        {
            "claim_digest": thread.claim_digest,
            "semantic_fingerprint": thread.semantic_fingerprint,
            "verified_lineage_root": thread.verified_lineage_root,
        },
    )


def _closure_prior_root(prior: ClosurePriorV1) -> str:
    return canonical_hash(
        "qm-closure-prior-v1",
        {
            "obligation_digest": prior.obligation_digest,
            "candidate_action_digest": prior.candidate_action_digest,
            "p_close_ppm": prior.p_close_ppm,
            "estimator_kind": prior.estimator_kind,
            "estimator_root": prior.estimator_root,
            "policy_digest": prior.policy_digest,
            "source_head_sha": prior.source_head_sha,
            "verification_receipt_root": prior.verification_receipt_root,
        },
    )


class QuantumManifoldSchedulerV1:
    """Authority-zero Phase-1 scheduler.

    The currently implemented surface closes only the preregistered centrality
    anti-Sybil and closure-prior provenance contracts.  Stale-head and proposal
    construction remain deliberately RED until their own GREEN step.
    """

    def __init__(
        self,
        *,
        policy: Mapping[str, object],
        closure_prior_store: TrustedClosurePriorStore | None = None,
    ) -> None:
        self._policy = dict(policy)
        self._closure_prior_store = closure_prior_store
        if self._policy.get("authority_effect") != "NONE":
            raise QuantumManifoldError("AUTHORITY_TUNNELING_ATTEMPT")
        self._ppm = _exact_non_negative_int(self._policy.get("ppm"))
        if self._ppm <= 0:
            raise QuantumManifoldError("FIXED_POINT_DOMAIN_ERROR")
        self._policy_digest = _canonical_json_sha256(self._policy)

    def centrality_ppm(
        self,
        obligation: OpenObligationV1,
        active_terminal_threads: tuple[RealityThreadV1, ...],
    ) -> int:
        universe = {
            _lineage_class(thread)
            for thread in active_terminal_threads
            if thread.active
        }
        if not universe:
            return 0

        downstream = {
            _lineage_class(thread)
            for thread in obligation.downstream_threads
            if thread.active
        }
        if not downstream.issubset(universe):
            raise QuantumManifoldError("DOWNSTREAM_LINEAGE_OUTSIDE_ACTIVE_UNIVERSE")
        return (len(downstream) * self._ppm) // len(universe)

    def closure_leverage_ppm(
        self,
        action: CandidateActionV1,
        obligation: OpenObligationV1,
        active_terminal_threads: tuple[RealityThreadV1, ...],
    ) -> int:
        if action.closure_prior_root is None or self._closure_prior_store is None:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        try:
            prior = self._closure_prior_store.fetch_verified(action.closure_prior_root)
        except Exception as exc:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR") from exc

        if not isinstance(prior, ClosurePriorV1):
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        if _closure_prior_root(prior) != prior.prior_root:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        if prior.prior_root != action.closure_prior_root:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        if prior.obligation_digest != obligation.obligation_digest:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        if prior.candidate_action_digest != action.candidate_action_digest:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        if prior.policy_digest != self._policy_digest:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        if prior.source_head_sha != action.source_head_sha:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        if obligation.source_head_sha != action.source_head_sha:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")

        p_close_ppm = _exact_non_negative_int(prior.p_close_ppm, upper=self._ppm)
        centrality = self.centrality_ppm(obligation, active_terminal_threads)
        return (p_close_ppm * centrality) // self._ppm

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
