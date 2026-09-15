from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from harness.sdk.authority_client import authorize_from_environment
from harness.sdk.quantummanifold_scheduler import (
    CandidateActionV1,
    ClosurePriorV1,
    DispatchProposalV1,
    OpenObligationV1,
    QuantumManifoldError,
    QuantumManifoldSchedulerV1,
    RealityThreadV1,
)
from harness.sdk.sovereign_execution import canonical_hash

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "harness" / "policies" / "quantummanifold-scheduler.v1.json"
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

HEAD_A = "a" * 40
HEAD_B = "b" * 40
DIGEST_0 = "0" * 64
DIGEST_1 = "1" * 64
DIGEST_2 = "2" * 64
DIGEST_3 = "3" * 64
DIGEST_4 = "4" * 64
DIGEST_5 = "5" * 64
DIGEST_6 = "6" * 64
DIGEST_7 = "7" * 64
DIGEST_8 = "8" * 64
DIGEST_9 = "9" * 64
DIGEST_C = "c" * 64
DIGEST_D = "d" * 64
DIGEST_E = "e" * 64
DIGEST_F = "f" * 64


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


POLICY_DIGEST = _canonical_sha(POLICY)


class RejectingClosurePriorStore:
    def fetch_verified(self, prior_root: str):
        raise KeyError(prior_root)


class MappingClosurePriorStore:
    def __init__(self, priors: tuple[ClosurePriorV1, ...]) -> None:
        self._priors = {prior.prior_root: prior for prior in priors}

    def fetch_verified(self, prior_root: str) -> ClosurePriorV1:
        return self._priors[prior_root]


def _scheduler(*, prior_store=None) -> QuantumManifoldSchedulerV1:
    return QuantumManifoldSchedulerV1(
        policy=POLICY,
        closure_prior_store=prior_store,
    )


def _lineage_a(thread_id: str = "thread-a") -> RealityThreadV1:
    return RealityThreadV1(
        thread_id=thread_id,
        source_head_sha=HEAD_A,
        claim_digest=DIGEST_1,
        semantic_fingerprint=DIGEST_2,
        verified_lineage_root=DIGEST_3,
    )


def _lineage_b() -> RealityThreadV1:
    return RealityThreadV1(
        thread_id="thread-b",
        source_head_sha=HEAD_A,
        claim_digest=DIGEST_4,
        semantic_fingerprint=DIGEST_5,
        verified_lineage_root=DIGEST_6,
    )


def _obligation(*threads: RealityThreadV1) -> OpenObligationV1:
    return OpenObligationV1(
        obligation_id="obl-1",
        obligation_digest=DIGEST_7,
        source_head_sha=HEAD_A,
        downstream_threads=tuple(threads),
    )


def _action(*, closure_prior_root: str | None = None) -> CandidateActionV1:
    return CandidateActionV1(
        action_id="action-1",
        candidate_action_digest=DIGEST_8,
        source_head_sha=HEAD_A,
        obligation_digest=DIGEST_7,
        closure_prior_root=closure_prior_root,
        information_gain_ppm=100_000,
        falsification_value_ppm=200_000,
        compute_cost_ppm=10_000,
        evidence_cost_ppm=20_000,
        latency_cost_ppm=30_000,
        recommended_role="BUILDER",
    )


def _prior_for(action: CandidateActionV1, *, p_close_ppm: int) -> ClosurePriorV1:
    payload = {
        "obligation_digest": action.obligation_digest,
        "candidate_action_digest": action.candidate_action_digest,
        "p_close_ppm": p_close_ppm,
        "estimator_kind": "TEST_FIXTURE_V1",
        "estimator_root": DIGEST_E,
        "policy_digest": POLICY_DIGEST,
        "source_head_sha": action.source_head_sha,
        "verification_receipt_root": DIGEST_F,
    }
    root = canonical_hash("qm-closure-prior-v1", payload)
    return ClosurePriorV1(prior_root=root, **payload)


def _rankable_action(
    *,
    action_id: str,
    digest: str,
    p_close_ppm: int,
    information_gain_ppm: int,
    falsification_value_ppm: int,
    compute_cost_ppm: int = 20_000,
    evidence_cost_ppm: int = 20_000,
    latency_cost_ppm: int = 20_000,
) -> tuple[CandidateActionV1, ClosurePriorV1]:
    provisional = CandidateActionV1(
        action_id=action_id,
        candidate_action_digest=digest,
        source_head_sha=HEAD_A,
        obligation_digest=DIGEST_7,
        closure_prior_root=None,
        information_gain_ppm=information_gain_ppm,
        falsification_value_ppm=falsification_value_ppm,
        compute_cost_ppm=compute_cost_ppm,
        evidence_cost_ppm=evidence_cost_ppm,
        latency_cost_ppm=latency_cost_ppm,
        recommended_role="BUILDER",
    )
    prior = _prior_for(provisional, p_close_ppm=p_close_ppm)
    action = CandidateActionV1(
        action_id=provisional.action_id,
        candidate_action_digest=provisional.candidate_action_digest,
        source_head_sha=provisional.source_head_sha,
        obligation_digest=provisional.obligation_digest,
        closure_prior_root=prior.prior_root,
        information_gain_ppm=provisional.information_gain_ppm,
        falsification_value_ppm=provisional.falsification_value_ppm,
        compute_cost_ppm=provisional.compute_cost_ppm,
        evidence_cost_ppm=provisional.evidence_cost_ppm,
        latency_cost_ppm=provisional.latency_cost_ppm,
        recommended_role=provisional.recommended_role,
    )
    return action, prior


def test_centrality_inflation_rejected() -> None:
    scheduler = _scheduler()
    a = _lineage_a()
    b = _lineage_b()

    unsplit = _obligation(a)
    unsplit_universe = (a, b)

    aliases = tuple(_lineage_a(f"thread-a-alias-{idx:03d}") for idx in range(100))
    split = _obligation(*aliases)
    split_universe = aliases + (b,)

    baseline = scheduler.centrality_ppm(unsplit, unsplit_universe)
    attacked = scheduler.centrality_ppm(split, split_universe)

    assert baseline == 500_000
    assert attacked == baseline


def test_fake_closure_leverage_rejected() -> None:
    scheduler = _scheduler(prior_store=RejectingClosurePriorStore())
    a = _lineage_a()
    b = _lineage_b()
    action = _action(closure_prior_root=None)

    with pytest.raises(QuantumManifoldError) as exc:
        scheduler.closure_leverage_ppm(action, _obligation(a), (a, b))

    assert exc.value.reason_code == "UNVERIFIED_CLOSURE_PRIOR"


def test_stale_exact_head_rejected() -> None:
    scheduler = _scheduler()

    with pytest.raises(QuantumManifoldError) as exc:
        scheduler.assert_current_head(HEAD_A, HEAD_B)

    assert exc.value.reason_code == "STALE_RESULT_REQUIRES_REBASE"


def test_authority_tunneling_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = _scheduler()
    proposal = scheduler.build_proposal(
        baseline_digest=DIGEST_0,
        source_head_sha=HEAD_A,
        current_head_sha=HEAD_A,
        reality_snapshot_digest=DIGEST_1,
        obligation_set_digest=DIGEST_2,
        candidate_set_digest=DIGEST_3,
        scheduler_policy_digest=POLICY_DIGEST,
        selected_action_digest=DIGEST_8,
        information_gain_ppm=100_000,
        closure_leverage_ppm=500_000,
        falsification_value_ppm=200_000,
        cost_ppm=60_000,
        ranking_score_ppm=13_333_111,
        recommended_role="BUILDER",
    )

    assert isinstance(proposal, DispatchProposalV1)
    assert proposal.authority_effect == "NONE"
    assert proposal.can_admit_claim is False
    assert proposal.can_advance_authority is False
    assert not hasattr(scheduler, "authorize")

    scheduler_receipt_digest = _canonical_sha(asdict(proposal))
    monkeypatch.delenv("AEGIS_EXECUTION_IDENTITY_JSON", raising=False)
    monkeypatch.delenv("AEGIS_APPROVAL_JSON", raising=False)

    decision = authorize_from_environment(
        action_class="D1",
        authority_domain="agent:dispatch",
        requested_capability="coordinator.dispatch",
        tool="harness.sdk.quantummanifold_scheduler:dispatch",
        target="BUILDER",
        action={
            "operation": "agent-dispatch",
            "scheduler_receipt_digest": scheduler_receipt_digest,
        },
    )

    assert decision["outcome"] == "DENIED"
    assert decision["authority_score"] == "0.000000"
    assert decision["denial_codes"] == ["IDENTITY_UNAVAILABLE"]


def test_fixed_point_numeric_domain_and_flooring() -> None:
    qm = importlib.import_module("harness.sdk.quantummanifold_scheduler")
    mul_ppm = getattr(qm, "mul_ppm")

    assert mul_ppm(1, 999_999) == 0
    assert mul_ppm(1_000_001, 1_000_001) == 1_000_002

    for bad in (-1, 1.5, True, DIGEST_1):
        with pytest.raises(QuantumManifoldError) as exc:
            mul_ppm(bad, 1)
        assert exc.value.reason_code == "FIXED_POINT_DOMAIN_ERROR"

    scheduler = _scheduler()
    with pytest.raises(QuantumManifoldError) as exc:
        scheduler.ranking_score_ppm(
            information_gain_ppm=POLICY["max_safe_canonical_int"] + 1,
            closure_leverage_ppm=0,
            falsification_value_ppm=0,
            cost_ppm=0,
        )
    assert exc.value.reason_code == "FIXED_POINT_DOMAIN_ERROR"

    with pytest.raises(QuantumManifoldError) as exc:
        scheduler.ranking_score_ppm(
            information_gain_ppm=DIGEST_1,
            closure_leverage_ppm=0,
            falsification_value_ppm=0,
            cost_ppm=0,
        )
    assert exc.value.reason_code == "FIXED_POINT_DOMAIN_ERROR"


def test_fixed_point_cost_and_ranking_score_exact() -> None:
    scheduler = _scheduler()
    action = _action()

    assert scheduler.cost_ppm(action) == 60_000
    assert (
        scheduler.ranking_score_ppm(
            information_gain_ppm=100_000,
            closure_leverage_ppm=500_000,
            falsification_value_ppm=200_000,
            cost_ppm=60_000,
        )
        == 13_333_111
    )

    with pytest.raises(QuantumManifoldError) as exc:
        scheduler.build_proposal(
            baseline_digest=DIGEST_0,
            source_head_sha=HEAD_A,
            current_head_sha=HEAD_A,
            reality_snapshot_digest=DIGEST_1,
            obligation_set_digest=DIGEST_2,
            candidate_set_digest=DIGEST_3,
            scheduler_policy_digest=POLICY_DIGEST,
            selected_action_digest=DIGEST_8,
            information_gain_ppm=100_000,
            closure_leverage_ppm=500_000,
            falsification_value_ppm=200_000,
            cost_ppm=60_000,
            ranking_score_ppm=13_333_110,
            recommended_role="BUILDER",
        )
    assert exc.value.reason_code == "RANKING_SCORE_MISMATCH"

    overflow = CandidateActionV1(
        action_id="overflow",
        candidate_action_digest=DIGEST_9,
        source_head_sha=HEAD_A,
        obligation_digest=DIGEST_7,
        closure_prior_root=None,
        information_gain_ppm=0,
        falsification_value_ppm=0,
        compute_cost_ppm=POLICY["max_safe_canonical_int"],
        evidence_cost_ppm=POLICY["max_safe_canonical_int"],
        latency_cost_ppm=POLICY["max_safe_canonical_int"],
        recommended_role="BUILDER",
    )
    with pytest.raises(QuantumManifoldError) as exc:
        scheduler.cost_ppm(overflow)
    assert exc.value.reason_code == "FIXED_POINT_DOMAIN_ERROR"


def test_deterministic_tie_break_order() -> None:
    active = (_lineage_a(),)
    obligation = _obligation(*active)

    closure_a, prior_a = _rankable_action(
        action_id="closure-a",
        digest=DIGEST_C,
        p_close_ppm=500_000,
        information_gain_ppm=100_000,
        falsification_value_ppm=100_000,
    )
    closure_b, prior_b = _rankable_action(
        action_id="closure-b",
        digest=DIGEST_D,
        p_close_ppm=400_000,
        information_gain_ppm=200_000,
        falsification_value_ppm=100_000,
    )
    scheduler = _scheduler(prior_store=MappingClosurePriorStore((prior_a, prior_b)))
    ranked = scheduler.rank_candidates(
        (closure_b, closure_a),
        obligations_by_digest={DIGEST_7: obligation},
        active_terminal_threads=active,
    )
    assert ranked[0].candidate_action_digest == DIGEST_C

    falsify_a, prior_c = _rankable_action(
        action_id="falsify-a",
        digest=DIGEST_C,
        p_close_ppm=500_000,
        information_gain_ppm=0,
        falsification_value_ppm=200_000,
    )
    falsify_b, prior_d = _rankable_action(
        action_id="falsify-b",
        digest=DIGEST_D,
        p_close_ppm=500_000,
        information_gain_ppm=100_000,
        falsification_value_ppm=100_000,
    )
    scheduler = _scheduler(prior_store=MappingClosurePriorStore((prior_c, prior_d)))
    ranked = scheduler.rank_candidates(
        (falsify_b, falsify_a),
        obligations_by_digest={DIGEST_7: obligation},
        active_terminal_threads=active,
    )
    assert ranked[0].candidate_action_digest == DIGEST_C

    cheap, prior_e = _rankable_action(
        action_id="cheap",
        digest=DIGEST_C,
        p_close_ppm=0,
        information_gain_ppm=0,
        falsification_value_ppm=0,
        compute_cost_ppm=10,
        evidence_cost_ppm=0,
        latency_cost_ppm=0,
    )
    expensive, prior_f = _rankable_action(
        action_id="expensive",
        digest=DIGEST_D,
        p_close_ppm=0,
        information_gain_ppm=0,
        falsification_value_ppm=0,
        compute_cost_ppm=20,
        evidence_cost_ppm=0,
        latency_cost_ppm=0,
    )
    scheduler = _scheduler(prior_store=MappingClosurePriorStore((prior_e, prior_f)))
    ranked = scheduler.rank_candidates(
        (expensive, cheap),
        obligations_by_digest={DIGEST_7: obligation},
        active_terminal_threads=active,
    )
    assert ranked[0].candidate_action_digest == DIGEST_C

    lexical_a, prior_g = _rankable_action(
        action_id="lexical-a",
        digest=DIGEST_0,
        p_close_ppm=0,
        information_gain_ppm=0,
        falsification_value_ppm=0,
        compute_cost_ppm=10,
        evidence_cost_ppm=0,
        latency_cost_ppm=0,
    )
    lexical_b, prior_h = _rankable_action(
        action_id="lexical-b",
        digest=DIGEST_1,
        p_close_ppm=0,
        information_gain_ppm=0,
        falsification_value_ppm=0,
        compute_cost_ppm=10,
        evidence_cost_ppm=0,
        latency_cost_ppm=0,
    )
    scheduler = _scheduler(prior_store=MappingClosurePriorStore((prior_g, prior_h)))
    ranked = scheduler.rank_candidates(
        (lexical_b, lexical_a),
        obligations_by_digest={DIGEST_7: obligation},
        active_terminal_threads=active,
    )
    assert ranked[0].candidate_action_digest == DIGEST_0


def test_candidate_digest_collision_rejected() -> None:
    active = (_lineage_a(),)
    obligation = _obligation(*active)
    action_a, prior = _rankable_action(
        action_id="collision-a",
        digest=DIGEST_C,
        p_close_ppm=0,
        information_gain_ppm=1,
        falsification_value_ppm=0,
    )
    action_b = CandidateActionV1(
        action_id="collision-b",
        candidate_action_digest=action_a.candidate_action_digest,
        source_head_sha=action_a.source_head_sha,
        obligation_digest=action_a.obligation_digest,
        closure_prior_root=action_a.closure_prior_root,
        information_gain_ppm=2,
        falsification_value_ppm=action_a.falsification_value_ppm,
        compute_cost_ppm=action_a.compute_cost_ppm,
        evidence_cost_ppm=action_a.evidence_cost_ppm,
        latency_cost_ppm=action_a.latency_cost_ppm,
        recommended_role=action_a.recommended_role,
    )
    scheduler = _scheduler(prior_store=MappingClosurePriorStore((prior,)))

    with pytest.raises(QuantumManifoldError) as exc:
        scheduler.rank_candidates(
            (action_a, action_b),
            obligations_by_digest={DIGEST_7: obligation},
            active_terminal_threads=active,
        )
    assert exc.value.reason_code == "CANDIDATE_DIGEST_COLLISION"


def test_proposal_serialization_byte_identical() -> None:
    qm = importlib.import_module("harness.sdk.quantummanifold_scheduler")
    canonical_proposal_bytes = getattr(qm, "canonical_proposal_bytes")
    canonical_proposal_digest = getattr(qm, "canonical_proposal_digest")

    proposal = _scheduler().build_proposal(
        baseline_digest=DIGEST_0,
        source_head_sha=HEAD_A,
        current_head_sha=HEAD_A,
        reality_snapshot_digest=DIGEST_1,
        obligation_set_digest=DIGEST_2,
        candidate_set_digest=DIGEST_3,
        scheduler_policy_digest=POLICY_DIGEST,
        selected_action_digest=DIGEST_8,
        information_gain_ppm=100_000,
        closure_leverage_ppm=500_000,
        falsification_value_ppm=200_000,
        cost_ppm=60_000,
        ranking_score_ppm=13_333_111,
        recommended_role="BUILDER",
    )

    rendered = tuple(canonical_proposal_bytes(proposal) for _ in range(3))
    assert rendered[0] == rendered[1] == rendered[2]
    assert canonical_proposal_digest(proposal) == hashlib.sha256(rendered[0]).hexdigest()
