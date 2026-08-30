from fractions import Fraction
from pathlib import Path

from harness.sdk.universal_intelligence_evidence import (
    EpistemicAuthorityTier,
    EvaluationCampaignContract,
    EvidenceObservation,
    UniversalIntelligenceEvidencePlane,
)
from harness.sdk.rh_obligation_gate import (
    DEFAULT_OBLIGATIONS,
    ObligationState,
    RHObligationLedger,
)
from research.rh.finite_to_global_counterexample import (
    build_refutation_receipt,
    limit_witness_q,
    tail_norm_sq,
    truncation_q,
)
from scripts.generate_provenance_census import (
    REQUIRED_OPEN_POST_BASELINE_PRS,
    RemoteHead,
    partition_census_heads,
    partition_census_prs,
)


def test_evidence_plane_cannot_mint_authority():
    plane = UniversalIntelligenceEvidencePlane(EvaluationCampaignContract("campaign-v1"))
    assert plane.authority_weight == 0
    assert plane.may_mint_execution_authority is False
    assert plane.may_mint_effect_authority is False
    assert plane.may_mint_admission_authority is False


def test_positive_observation_promotes_only_to_empirical():
    plane = UniversalIntelligenceEvidencePlane(EvaluationCampaignContract("campaign-v1"))
    accepted = plane.record_falsification_run(
        EvidenceObservation(
            dimension="transfer",
            baseline_score=0.5,
            observed_score=0.6,
            reproducible_receipt_sha="sha256:test",
        )
    )
    assert accepted is True
    assert plane.recorded_evidence[-1].tier is EpistemicAuthorityTier.T1_EMPIRICAL
    assert plane.evaluate_generalization_status()["agi_proven"] is False


def test_non_improvement_is_refuted():
    plane = UniversalIntelligenceEvidencePlane(EvaluationCampaignContract("campaign-v1"))
    accepted = plane.record_falsification_run(
        EvidenceObservation(
            dimension="agency",
            baseline_score=0.7,
            observed_score=0.7,
            reproducible_receipt_sha="sha256:test",
        )
    )
    assert accepted is False
    assert plane.recorded_evidence[-1].tier is EpistemicAuthorityTier.T3_REFUTED


def test_empirical_observation_cannot_self_assert_formal_authority():
    plane = UniversalIntelligenceEvidencePlane(EvaluationCampaignContract("campaign-v1"))
    try:
        plane.record_falsification_run(
            EvidenceObservation(
                dimension="transfer",
                baseline_score=0.1,
                observed_score=0.9,
                reproducible_receipt_sha="sha256:test",
                tier=EpistemicAuthorityTier.T0_FORMAL,
            )
        )
    except ValueError as exc:
        assert "cannot self-assert" in str(exc)
    else:
        raise AssertionError("T0 self-promotion must fail closed")


def test_default_rh_gate_is_not_proven_and_fail_closed():
    result = RHObligationLedger().verify_final_closure()
    assert result["verdict"] == "RH_NOT_PROVEN"
    assert result["gate_status"] == "FAIL_CLOSED"
    assert result["open_obligations"]


def test_final_closure_requires_every_obligation_formally_verified():
    ledger = RHObligationLedger()
    for obligation in DEFAULT_OBLIGATIONS:
        ledger = ledger.with_state(
            obligation.obligation_id,
            ObligationState.FORMALLY_VERIFIED,
            authority_note="test-only proof-kernel fixture",
        )
    result = ledger.verify_final_closure()
    assert result["verdict"] == "RH_PROVEN_FORMALLY"
    assert result["gate_status"] == "ADMITTED"


def test_dependency_violation_fails_closed():
    ledger = RHObligationLedger().with_state(
        "W10_FinalRiemannHypothesis",
        ObligationState.FORMALLY_VERIFIED,
        authority_note="adversarial fixture",
    )
    result = ledger.verify_final_closure()
    assert result["verdict"] == "RH_NOT_PROVEN"
    assert result["dependency_violations"]


def test_census_keeps_original_150_head_snapshot_separate_from_classified_post_baseline_refs():
    source_heads = [
        RemoteHead(name=f"branch-{i:03d}", sha=f"{i:040x}", protected=False)
        for i in range(150)
    ]
    integration = RemoteHead(
        name="integration/aegis-universal-intelligence-rh-v1",
        sha="f" * 40,
        protected=False,
    )
    phi_child = RemoteHead(
        name="research/phi-finite-section-congruence-v1",
        sha="e" * 40,
        protected=False,
    )

    baseline, live = partition_census_heads(source_heads + [integration, phi_child])

    assert len(baseline) == 150
    assert len(live) == 152
    assert all(head.name not in {integration.name, phi_child.name} for head in baseline)
    assert integration in live
    assert phi_child in live


def test_census_keeps_original_95_pr_snapshot_separate_from_classified_post_baseline_prs():
    baseline_fixture = [
        {"number": i + 1, "draft": i < 73}
        for i in range(95)
    ]
    integration_pr = {"number": 342, "draft": True}
    phi_child_pr = {"number": 344, "draft": True}

    baseline, live = partition_census_prs(baseline_fixture + [integration_pr, phi_child_pr])

    assert len(baseline) == 95
    assert sum(1 for pr in baseline if pr["draft"] is True) == 73
    assert sum(1 for pr in baseline if pr["draft"] is not True) == 22
    assert len(live) == 97
    assert integration_pr in live
    assert phi_child_pr in live
    assert integration_pr not in baseline
    assert phi_child_pr not in baseline


def test_closed_verified_child_is_not_required_in_live_open_pr_set():
    assert REQUIRED_OPEN_POST_BASELINE_PRS == frozenset({342})


def test_density_alone_shortcut_has_exact_counterexample():
    for n in (1, 2, 4, 8, 16):
        assert truncation_q(n) > 0
        assert tail_norm_sq(n) == Fraction(1, 3 * (4 ** n))
    assert limit_witness_q() == Fraction(-1, 1)
    assert tail_norm_sq(16) < Fraction(1, 10**9)

    receipt = build_refutation_receipt()
    assert receipt["classification"] == "REFUTED_SHORTCUT"
    assert receipt["refutes"] == "DENSITY_ALONE_FINITE_STAGE_POSITIVITY_IMPLIES_CLOSURE_POSITIVITY"
    assert receipt["does_not_refute"] == [
        "CONTINUOUS_Q_EXTENDS_POSITIVITY_FROM_DENSE_SUBSPACE",
        "LOWER_SEMICONTINUOUS_CLOSED_FORM_EXTENDS_POSITIVITY_UNDER_ITS_HYPOTHESES",
    ]


def test_machine_readable_rh_ledger_matches_fail_closed_default():
    ledger_path = Path("research/rh/proof-obligations-v1.json")
    ledger = RHObligationLedger.from_json_file(ledger_path)
    result = ledger.verify_final_closure()
    assert result["verdict"] == "RH_NOT_PROVEN"
    assert result["gate_status"] == "FAIL_CLOSED"
    assert "W8_DensityContinuityCoverage" in result["open_obligations"]
