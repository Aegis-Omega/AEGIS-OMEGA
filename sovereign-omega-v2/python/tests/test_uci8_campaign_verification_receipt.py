from __future__ import annotations

from dataclasses import replace

import pytest

from harness.sdk.agi_evidence import (
    CapabilityTaskSpecV1,
    ContaminationClass,
    DeterministicCheckerAdapterV1,
    EvidenceAxis,
)
from harness.sdk.evaluation_campaign import (
    BenchmarkFamily,
    BenchmarkTrackSpecV1,
    CampaignEvidenceBundleV1,
    CampaignEvidenceStatus,
    CampaignEvidenceVerificationReceiptV1,
    CampaignTaskTrialUnitV1,
    EvaluationCampaignError,
    EvaluationCampaignManifestV1,
    MetricKind,
    PairedBenchmarkTrialV1,
    PortableCheckerHMACV1,
    SplitPrivacy,
    StatisticalMode,
)

KEY = b"uci8-campaign-verification-key-material-32bytes-minimum"
RUN_ID = "uci8-campaign-run-001"
VERIFICATION_ID = "uci8-campaign-verification-001"


def _fixture(*, portable_pair: bool = True):
    task = CapabilityTaskSpecV1(
        task_id="uci8-campaign-verification",
        axis=EvidenceAxis.NOVEL_ABSTRACTION_TRANSFER,
        domain="evaluation-campaign",
        hidden_case_commitment="1" * 64,
        checker_commitment="2" * 64,
        budget_commitment="3" * 64,
        human_reference_commitment="4" * 64,
        trial_count=1,
        contamination_class=ContaminationClass.HELD_OUT,
    )
    track = BenchmarkTrackSpecV1.create(
        track_id="campaign-verification-track",
        benchmark_family=BenchmarkFamily.ARC_AGI_2,
        benchmark_version="2026.1",
        benchmark_source_commitment="5" * 64,
        split_id="private-eval",
        split_privacy=SplitPrivacy.PRIVATE,
        metric_kind=MetricKind.EXACT_MATCH_ACCURACY,
        task_trial_units=(CampaignTaskTrialUnitV1(task_spec_root=task.root, trial_index=0),),
        scorer_commitment=task.checker_commitment,
        budget_commitment=task.budget_commitment,
        human_reference_commitment=task.human_reference_commitment,
        contamination_class=ContaminationClass.HELD_OUT,
        repetition_count=1,
        statistical_mode=StatisticalMode.PAIRED_DESCRIPTIVE_V1,
    )
    campaign = EvaluationCampaignManifestV1.create(
        campaign_id="campaign-verification-v1",
        uci7_suite_root="6" * 64,
        evaluated_system_commitment="a" * 64,
        strongest_constituent_baseline_commitment="b" * 64,
        tracks=(track,),
    )

    def issue(runtime: str, score: int):
        adapter = DeterministicCheckerAdapterV1(
            checker_commitment=task.checker_commitment,
            provider_runtime_commitment=runtime,
            checker=lambda _output: (True, score),
        )
        return adapter.issue_result(
            task=task,
            trial_index=0,
            candidate_output=f"{runtime}:{score}".encode(),
            predicted_correctness_bps=score,
            execution_receipt_root="c" * 64,
            effect_receipt_root="d" * 64,
            admission_record_root="e" * 64,
        )

    system = issue(campaign.evaluated_system_commitment, 9000)
    baseline = issue(campaign.strongest_constituent_baseline_commitment, 7000)
    mac = PortableCheckerHMACV1(key_id="campaign-key-v1", secret_key=KEY)

    if portable_pair:
        system_att = mac.issue(run_id=RUN_ID, result=system)
        baseline_att = mac.issue(run_id=RUN_ID, result=baseline)
        pair = PairedBenchmarkTrialV1.create(
            campaign=campaign,
            track=track,
            system_result=system,
            baseline_result=baseline,
            expected_run_id=RUN_ID,
            system_attestation=system_att,
            baseline_attestation=baseline_att,
            attestation_verifier=mac,
        )
        pair_receipt = mac.issue_pair_verification(
            run_id=RUN_ID,
            pair=pair,
            system_result=system,
            baseline_result=baseline,
            system_attestation=system_att,
            baseline_attestation=baseline_att,
        )
        pair_for_bundle = replace(pair)
        bundle = CampaignEvidenceBundleV1.create(
            campaign=campaign,
            pairs=(pair_for_bundle,),
            pair_verifications=(replace(pair_receipt),),
            pair_verification_verifier=mac,
            benchmark_adapter_executable_commitment="7" * 64,
            runner_environment_commitment="8" * 64,
            execution_receipt_bundle_commitment="9" * 64,
        )
    else:
        pair = PairedBenchmarkTrialV1.create(
            campaign=campaign,
            track=track,
            system_result=system,
            baseline_result=baseline,
        )
        bundle = CampaignEvidenceBundleV1.create(
            campaign=campaign,
            pairs=(pair,),
            benchmark_adapter_executable_commitment="7" * 64,
            runner_environment_commitment="8" * 64,
            execution_receipt_bundle_commitment="9" * 64,
        )
    return campaign, mac, bundle


def test_bundle_payload_never_carries_collective_promotion_status() -> None:
    _campaign, _mac, bundle = _fixture(portable_pair=True)
    assert bundle.evidence_status is CampaignEvidenceStatus.HELD_OUT_EVIDENCE_COMPLETE


def test_direct_collective_bundle_status_is_rejected_structurally() -> None:
    _campaign, _mac, bundle = _fixture(portable_pair=True)
    forged = replace(bundle, evidence_status=CampaignEvidenceStatus.COLLECTIVE_CONTRIBUTION_EVALUABLE)
    with pytest.raises(EvaluationCampaignError, match="COLLECTIVE_STATUS_REQUIRES_VERIFICATION_RECEIPT"):
        forged.validate()


def test_campaign_verification_receipt_survives_process_reconstruction() -> None:
    _campaign, mac, bundle = _fixture(portable_pair=True)
    receipt = mac.issue_campaign_verification(verification_id=VERIFICATION_ID, bundle=bundle)
    replayed_bundle = replace(bundle)
    replayed_receipt = replace(receipt)
    mac.verify_campaign_verification(bundle=replayed_bundle, receipt=replayed_receipt)
    assert receipt.verification_status is CampaignEvidenceStatus.COLLECTIVE_CONTRIBUTION_EVALUABLE
    assert receipt.bundle_root == bundle.root


def test_campaign_verification_receipt_binds_runner_environment_and_execution_bundle() -> None:
    _campaign, mac, bundle = _fixture(portable_pair=True)
    receipt = mac.issue_campaign_verification(verification_id=VERIFICATION_ID, bundle=bundle)
    with pytest.raises(EvaluationCampaignError, match="CAMPAIGN_VERIFICATION_BUNDLE_ROOT_MISMATCH"):
        mac.verify_campaign_verification(
            bundle=replace(bundle, runner_environment_commitment="f" * 64),
            receipt=receipt,
        )
    with pytest.raises(EvaluationCampaignError, match="CAMPAIGN_VERIFICATION_BUNDLE_ROOT_MISMATCH"):
        mac.verify_campaign_verification(
            bundle=replace(bundle, execution_receipt_bundle_commitment="f" * 64),
            receipt=receipt,
        )


def test_campaign_verification_issuer_requires_portable_pair_verification_roots() -> None:
    _campaign, mac, local_only_bundle = _fixture(portable_pair=False)
    with pytest.raises(EvaluationCampaignError, match="CAMPAIGN_VERIFICATION_REQUIRES_PORTABLE_PAIR_VERIFICATIONS"):
        mac.issue_campaign_verification(verification_id=VERIFICATION_ID, bundle=local_only_bundle)


def test_campaign_verification_receipt_is_nominal_hmac_receipt_not_public_signature() -> None:
    assert CampaignEvidenceVerificationReceiptV1.__name__ == "CampaignEvidenceVerificationReceiptV1"
