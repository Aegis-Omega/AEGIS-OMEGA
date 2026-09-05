from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from harness.sdk.authority_client import authorize_from_environment
from harness.sdk.quantummanifold_scheduler import (
    CandidateActionV1,
    DispatchProposalV1,
    OpenObligationV1,
    QuantumManifoldError,
    QuantumManifoldSchedulerV1,
    RealityThreadV1,
)

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
        ranking_score_ppm=300_000,
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
