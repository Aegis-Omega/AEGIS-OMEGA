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
