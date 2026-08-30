from __future__ import annotations

from harness.sdk.universal_intelligence_evidence import (
    EpistemicAuthorityTier,
    EvaluationCampaignContract,
    EvaluationReplayProofV1,
    EvidenceObservation,
    UniversalIntelligenceEvidencePlane,
    verify_evaluation_replay,
)


def _sha(ch: str) -> str:
    return ch * 64


def _verified_replay(
    *,
    dimension: str = "transfer",
    baseline_bps: int = 5000,
    observed_bps: int = 6000,
):
    proof = EvaluationReplayProofV1(
        campaign_id="campaign-v1",
        dimension=dimension,
        baseline_score_bps=baseline_bps,
        observed_score_bps=observed_bps,
        original_result_root=_sha("1"),
        replayed_result_root=_sha("1"),
        external_replication_result_root=_sha("1"),
        preregistration_root=_sha("2"),
        hidden_checker_commitment_root=_sha("3"),
        contamination_control_root=_sha("4"),
        strongest_constituent_root=_sha("5"),
        producer_identity_root=_sha("6"),
        verifier_identity_root=_sha("7"),
        replicator_identity_root=_sha("8"),
    )
    receipt = verify_evaluation_replay(proof)
    assert receipt.replay_verified is True
    return receipt


def test_positive_score_with_arbitrary_receipt_string_remains_hypothesis() -> None:
    plane = UniversalIntelligenceEvidencePlane(EvaluationCampaignContract("campaign-v1"))
    admitted = plane.record_falsification_run(
        EvidenceObservation(
            dimension="transfer",
            baseline_score=0.5,
            observed_score=0.6,
            reproducible_receipt_sha="sha256:test",
        )
    )

    assert admitted is False
    recorded = plane.recorded_evidence[-1]
    assert recorded.tier is EpistemicAuthorityTier.T2_HYPOTHESIS
    assert "REPLAY_RECEIPT_UNVERIFIED" in recorded.verification_reason_codes


def test_bound_verified_replay_is_required_for_t1_empirical() -> None:
    plane = UniversalIntelligenceEvidencePlane(EvaluationCampaignContract("campaign-v1"))
    receipt = _verified_replay()
    admitted = plane.record_falsification_run(
        EvidenceObservation(
            dimension="transfer",
            baseline_score=0.5,
            observed_score=0.6,
            reproducible_receipt_sha=receipt.root,
            verification_receipt=receipt,
        )
    )

    assert admitted is True
    recorded = plane.recorded_evidence[-1]
    assert recorded.tier is EpistemicAuthorityTier.T1_EMPIRICAL
    assert recorded.reproducible_receipt_sha == receipt.root
    assert recorded.verification_reason_codes == (
        "REPLAY_ROOTS_CONTROLS_AND_INDEPENDENT_IDENTITIES_BOUND",
    )
    assert plane.authority_weight == 0
    assert plane.evaluate_generalization_status()["agi_proven"] is False


def test_receipt_splicing_or_score_mismatch_downgrades_to_hypothesis() -> None:
    plane = UniversalIntelligenceEvidencePlane(EvaluationCampaignContract("campaign-v1"))
    receipt = _verified_replay()
    admitted = plane.record_falsification_run(
        EvidenceObservation(
            dimension="transfer",
            baseline_score=0.5,
            observed_score=0.61,
            reproducible_receipt_sha=_sha("f"),
            verification_receipt=receipt,
        )
    )

    assert admitted is False
    recorded = plane.recorded_evidence[-1]
    assert recorded.tier is EpistemicAuthorityTier.T2_HYPOTHESIS
    assert "REPLAY_RECEIPT_ROOT_BINDING_MISMATCH" in recorded.verification_reason_codes
    assert "REPLAY_SCORE_BINDING_MISMATCH" in recorded.verification_reason_codes


def test_replay_verifier_fails_closed_on_result_or_identity_mismatch() -> None:
    receipt = verify_evaluation_replay(
        EvaluationReplayProofV1(
            campaign_id="campaign-v1",
            dimension="transfer",
            baseline_score_bps=5000,
            observed_score_bps=6000,
            original_result_root=_sha("1"),
            replayed_result_root=_sha("9"),
            external_replication_result_root=_sha("1"),
            preregistration_root=_sha("2"),
            hidden_checker_commitment_root=_sha("3"),
            contamination_control_root=_sha("4"),
            strongest_constituent_root=_sha("5"),
            producer_identity_root=_sha("6"),
            verifier_identity_root=_sha("6"),
            replicator_identity_root=_sha("8"),
        )
    )

    assert receipt.replay_verified is False
    assert "REPLAY_RESULT_MISMATCH" in receipt.reason_codes
    assert "REPLAY_VERIFIER_NOT_INDEPENDENT" in receipt.reason_codes


def test_non_improvement_remains_refuted_even_with_verified_replay() -> None:
    plane = UniversalIntelligenceEvidencePlane(EvaluationCampaignContract("campaign-v1"))
    receipt = _verified_replay(dimension="agency", baseline_bps=7000, observed_bps=7000)
    admitted = plane.record_falsification_run(
        EvidenceObservation(
            dimension="agency",
            baseline_score=0.7,
            observed_score=0.7,
            reproducible_receipt_sha=receipt.root,
            verification_receipt=receipt,
        )
    )

    assert admitted is False
    assert plane.recorded_evidence[-1].tier is EpistemicAuthorityTier.T3_REFUTED
