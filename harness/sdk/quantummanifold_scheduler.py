"""QuantumManifold Scheduler v0.1 Phase-1 authority-zero kernel.

The scheduler consumes content-addressed provenance inputs, performs exact
integer fixed-point optimization, and emits recommendations only. Content
digests are identities/bindings; they are never converted into numeric utility.
Positive execution authority remains outside this module.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Mapping, Protocol

from harness.sdk.sovereign_execution import canonical_hash

PPM = 1_000_000
MAX_SAFE_CANONICAL_INT = 9_007_199_254_740_991

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_ROLES = frozenset({"BUILDER", "FALSIFIER", "REVIEWER"})


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


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise QuantumManifoldError("CANONICAL_SERIALIZATION_INVALID") from exc


def _canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _exact_non_negative_int(value: object, *, upper: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QuantumManifoldError("FIXED_POINT_DOMAIN_ERROR")
    if upper is not None and value > upper:
        raise QuantumManifoldError("FIXED_POINT_DOMAIN_ERROR")
    return value


def _exact_positive_int(value: object, *, upper: int | None = None) -> int:
    result = _exact_non_negative_int(value, upper=upper)
    if result <= 0:
        raise QuantumManifoldError("FIXED_POINT_DOMAIN_ERROR")
    return result


def _validate_git_sha(value: str) -> str:
    if not isinstance(value, str) or _GIT_SHA_RE.fullmatch(value) is None:
        raise QuantumManifoldError("SOURCE_HEAD_INVALID")
    return value


def _validate_digest(value: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise QuantumManifoldError("DIGEST_BINDING_INVALID")
    return value


def mul_ppm(x: int, y: int) -> int:
    """Canonical non-negative fixed-point multiplication with floor semantics."""

    x = _exact_non_negative_int(x)
    y = _exact_non_negative_int(y)
    return (x * y) // PPM


def canonical_proposal_bytes(proposal: DispatchProposalV1) -> bytes:
    """Return the canonical byte representation of an authority-zero proposal."""

    if not isinstance(proposal, DispatchProposalV1):
        raise QuantumManifoldError("PROPOSAL_TYPE_INVALID")
    if proposal.authority_effect != "NONE":
        raise QuantumManifoldError("AUTHORITY_TUNNELING_ATTEMPT")
    if proposal.can_admit_claim or proposal.can_advance_authority:
        raise QuantumManifoldError("AUTHORITY_TUNNELING_ATTEMPT")
    return _canonical_json_bytes(asdict(proposal))


def canonical_proposal_digest(proposal: DispatchProposalV1) -> str:
    return hashlib.sha256(canonical_proposal_bytes(proposal)).hexdigest()


def _lineage_class(thread: RealityThreadV1) -> str:
    if not isinstance(thread, RealityThreadV1):
        raise QuantumManifoldError("LINEAGE_TYPE_INVALID")
    _validate_git_sha(thread.source_head_sha)
    _validate_digest(thread.claim_digest)
    _validate_digest(thread.semantic_fingerprint)
    _validate_digest(thread.verified_lineage_root)
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


def _canonical_action_bytes(action: CandidateActionV1) -> bytes:
    if not isinstance(action, CandidateActionV1):
        raise QuantumManifoldError("CANDIDATE_ACTION_TYPE_INVALID")
    return _canonical_json_bytes(asdict(action))


class QuantumManifoldSchedulerV1:
    """Deterministic authority-zero Phase-1 scheduler."""

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

        self._ppm = _exact_positive_int(self._policy.get("ppm"))
        self._max_safe_canonical_int = _exact_positive_int(
            self._policy.get("max_safe_canonical_int")
        )
        if self._ppm != PPM or self._max_safe_canonical_int != MAX_SAFE_CANONICAL_INT:
            raise QuantumManifoldError("FIXED_POINT_POLICY_MISMATCH")

        self._alpha_ppm = _exact_non_negative_int(
            self._policy.get("alpha_ppm"), upper=self._max_safe_canonical_int
        )
        self._beta_ppm = _exact_non_negative_int(
            self._policy.get("beta_ppm"), upper=self._max_safe_canonical_int
        )
        self._gamma_ppm = _exact_non_negative_int(
            self._policy.get("gamma_ppm"), upper=self._max_safe_canonical_int
        )
        self._mu_ppm = _exact_non_negative_int(
            self._policy.get("mu_ppm"), upper=self._max_safe_canonical_int
        )
        self._eta_ppm = _exact_non_negative_int(
            self._policy.get("eta_ppm"), upper=self._max_safe_canonical_int
        )
        self._epsilon_ppm = _exact_positive_int(
            self._policy.get("epsilon_ppm"), upper=self._max_safe_canonical_int
        )
        self._policy_digest = _canonical_json_sha256(self._policy)

    def centrality_ppm(
        self,
        obligation: OpenObligationV1,
        active_terminal_threads: tuple[RealityThreadV1, ...],
    ) -> int:
        if not isinstance(obligation, OpenObligationV1):
            raise QuantumManifoldError("OBLIGATION_TYPE_INVALID")
        _validate_git_sha(obligation.source_head_sha)
        _validate_digest(obligation.obligation_digest)

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
        if not isinstance(action, CandidateActionV1):
            raise QuantumManifoldError("CANDIDATE_ACTION_TYPE_INVALID")
        if action.closure_prior_root is None or self._closure_prior_store is None:
            raise QuantumManifoldError("UNVERIFIED_CLOSURE_PRIOR")
        _validate_digest(action.closure_prior_root)
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
        leverage = mul_ppm(p_close_ppm, centrality)
        return _exact_non_negative_int(leverage, upper=self._max_safe_canonical_int)

    def cost_ppm(self, action: CandidateActionV1) -> int:
        if not isinstance(action, CandidateActionV1):
            raise QuantumManifoldError("CANDIDATE_ACTION_TYPE_INVALID")
        compute = _exact_non_negative_int(
            action.compute_cost_ppm, upper=self._max_safe_canonical_int
        )
        evidence = _exact_non_negative_int(
            action.evidence_cost_ppm, upper=self._max_safe_canonical_int
        )
        latency = _exact_non_negative_int(
            action.latency_cost_ppm, upper=self._max_safe_canonical_int
        )
        total = (
            compute
            + mul_ppm(self._mu_ppm, evidence)
            + mul_ppm(self._eta_ppm, latency)
        )
        return _exact_non_negative_int(total, upper=self._max_safe_canonical_int)

    def ranking_score_ppm(
        self,
        *,
        information_gain_ppm: int,
        closure_leverage_ppm: int,
        falsification_value_ppm: int,
        cost_ppm: int,
    ) -> int:
        information_gain_ppm = _exact_non_negative_int(
            information_gain_ppm, upper=self._max_safe_canonical_int
        )
        closure_leverage_ppm = _exact_non_negative_int(
            closure_leverage_ppm, upper=self._max_safe_canonical_int
        )
        falsification_value_ppm = _exact_non_negative_int(
            falsification_value_ppm, upper=self._max_safe_canonical_int
        )
        cost_ppm = _exact_non_negative_int(
            cost_ppm, upper=self._max_safe_canonical_int
        )

        weighted_ig = mul_ppm(self._alpha_ppm, information_gain_ppm)
        weighted_l = mul_ppm(self._beta_ppm, closure_leverage_ppm)
        weighted_f = mul_ppm(self._gamma_ppm, falsification_value_ppm)
        numerator = weighted_ig + weighted_l + weighted_f
        denominator = self._epsilon_ppm + cost_ppm
        if denominator <= 0:
            raise QuantumManifoldError("FIXED_POINT_DOMAIN_ERROR")
        score = (numerator * self._ppm) // denominator
        return _exact_non_negative_int(score, upper=self._max_safe_canonical_int)

    def rank_candidates(
        self,
        candidates: tuple[CandidateActionV1, ...],
        *,
        obligations_by_digest: Mapping[str, OpenObligationV1],
        active_terminal_threads: tuple[RealityThreadV1, ...],
    ) -> tuple[CandidateActionV1, ...]:
        unique: dict[str, CandidateActionV1] = {}
        canonical_by_digest: dict[str, bytes] = {}

        for action in candidates:
            if not isinstance(action, CandidateActionV1):
                raise QuantumManifoldError("CANDIDATE_ACTION_TYPE_INVALID")
            _validate_digest(action.candidate_action_digest)
            _validate_git_sha(action.source_head_sha)
            _validate_digest(action.obligation_digest)
            if action.recommended_role not in _ROLES:
                raise QuantumManifoldError("ROLE_ISOLATION_VIOLATION")

            canonical = _canonical_action_bytes(action)
            previous = canonical_by_digest.get(action.candidate_action_digest)
            if previous is not None:
                if previous != canonical:
                    raise QuantumManifoldError("CANDIDATE_DIGEST_COLLISION")
                continue
            canonical_by_digest[action.candidate_action_digest] = canonical
            unique[action.candidate_action_digest] = action

        scored: list[tuple[tuple[int, int, int, int, str], CandidateActionV1]] = []
        for action in unique.values():
            obligation = obligations_by_digest.get(action.obligation_digest)
            if obligation is None:
                raise QuantumManifoldError("OBLIGATION_BINDING_MISSING")
            if not isinstance(obligation, OpenObligationV1):
                raise QuantumManifoldError("OBLIGATION_TYPE_INVALID")
            if obligation.obligation_digest != action.obligation_digest:
                raise QuantumManifoldError("OBLIGATION_BINDING_MISMATCH")

            ig = _exact_non_negative_int(
                action.information_gain_ppm, upper=self._max_safe_canonical_int
            )
            falsification = _exact_non_negative_int(
                action.falsification_value_ppm, upper=self._max_safe_canonical_int
            )
            closure = self.closure_leverage_ppm(
                action, obligation, active_terminal_threads
            )
            cost = self.cost_ppm(action)
            score = self.ranking_score_ppm(
                information_gain_ppm=ig,
                closure_leverage_ppm=closure,
                falsification_value_ppm=falsification,
                cost_ppm=cost,
            )
            key = (
                -score,
                -closure,
                -falsification,
                cost,
                action.candidate_action_digest,
            )
            scored.append((key, action))

        scored.sort(key=lambda item: item[0])
        return tuple(action for _, action in scored)

    def assert_current_head(self, bound_head_sha: str, current_head_sha: str) -> None:
        bound = _validate_git_sha(bound_head_sha)
        current = _validate_git_sha(current_head_sha)
        if bound != current:
            raise QuantumManifoldError("STALE_RESULT_REQUIRES_REBASE")

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
        self.assert_current_head(source_head_sha, current_head_sha)
        _validate_digest(baseline_digest)
        _validate_digest(reality_snapshot_digest)
        _validate_digest(obligation_set_digest)
        _validate_digest(candidate_set_digest)
        _validate_digest(scheduler_policy_digest)
        _validate_digest(selected_action_digest)
        if scheduler_policy_digest != self._policy_digest:
            raise QuantumManifoldError("SCHEDULER_POLICY_MISMATCH")
        if recommended_role not in _ROLES:
            raise QuantumManifoldError("ROLE_ISOLATION_VIOLATION")

        information_gain_ppm = _exact_non_negative_int(
            information_gain_ppm, upper=self._max_safe_canonical_int
        )
        closure_leverage_ppm = _exact_non_negative_int(
            closure_leverage_ppm, upper=self._max_safe_canonical_int
        )
        falsification_value_ppm = _exact_non_negative_int(
            falsification_value_ppm, upper=self._max_safe_canonical_int
        )
        cost_ppm = _exact_non_negative_int(
            cost_ppm, upper=self._max_safe_canonical_int
        )
        ranking_score_ppm = _exact_non_negative_int(
            ranking_score_ppm, upper=self._max_safe_canonical_int
        )
        expected_score = self.ranking_score_ppm(
            information_gain_ppm=information_gain_ppm,
            closure_leverage_ppm=closure_leverage_ppm,
            falsification_value_ppm=falsification_value_ppm,
            cost_ppm=cost_ppm,
        )
        if ranking_score_ppm != expected_score:
            raise QuantumManifoldError("RANKING_SCORE_MISMATCH")

        return DispatchProposalV1(
            receipt_kind="AEGIS_QUANTUMMANIFOLD_SCHEDULING_RECEIPT_V1",
            baseline_digest=baseline_digest,
            source_head_sha=source_head_sha,
            reality_snapshot_digest=reality_snapshot_digest,
            obligation_set_digest=obligation_set_digest,
            candidate_set_digest=candidate_set_digest,
            scheduler_policy_digest=scheduler_policy_digest,
            selected_action_digest=selected_action_digest,
            information_gain_ppm=information_gain_ppm,
            closure_leverage_ppm=closure_leverage_ppm,
            falsification_value_ppm=falsification_value_ppm,
            cost_ppm=cost_ppm,
            ranking_score_ppm=ranking_score_ppm,
            recommended_role=recommended_role,
        )
