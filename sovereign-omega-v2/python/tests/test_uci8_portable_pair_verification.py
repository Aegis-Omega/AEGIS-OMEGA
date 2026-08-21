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
    CampaignTaskTrialUnitV1,
    EvaluationCampaignError,
    EvaluationCampaignManifestV1,
    MetricKind,
    PairVerificationAttestationV1,
    PairedBenchmarkTrialV1,
    PortableCheckerHMACV1,
    SplitPrivacy,
    StatisticalMode,
)

KEY = b"uci8-pair-verification-key-material-32bytes-minimum"
RUN_ID = "uci8-pair-verification-run-001"


def _fixture():
    task = CapabilityTaskSpecV1(
        task_id="uci8-portable-pair",
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
        track_id="portable-pair-track",
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
        campaign_id="portable-pair-campaign",
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

    mac = PortableCheckerHMACV1(key_id="pair-key-v1", secret_key=KEY)
    system = issue(campaign.evaluated_system_commitment, 9000)
    baseline = issue(campaign.strongest_constituent_baseline_commitment, 7000)
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
    return campaign, mac, pair, system, baseline, system_att, baseline_att


def _bundle(campaign, mac, pair, receipt):
    return CampaignEvidenceBundleV1.create(
        campaign=campaign,
        pairs=(pair,),
        benchmark_adapter_executable_commitment="7" * 64,
        runner_environment_commitment="8" * 64,
        execution_receipt_bundle_commitment="9" * 64,
        pair_verifications=(receipt,),
        pair_verification_verifier=mac,
    )


def test_pair_verification_receipt_survives_process_reconstruction_without_self_promotion() -> None:
    campaign, mac, pair, system, baseline, system_att, baseline_att = _fixture()
    receipt = mac.issue_pair_verification(
        run_id=RUN_ID,
        pair=pair,
        system_result=system,
        baseline_result=baseline,
        system_attestation=system_att,
        baseline_attestation=baseline_att,
    )

    replayed_pair = replace(pair)
    replayed_receipt = replace(receipt)
    bundle = _bundle(campaign, mac, replayed_pair, replayed_receipt)
    assert bundle.evidence_status is CampaignEvidenceStatus.HELD_OUT_EVIDENCE_COMPLETE
    assert bundle.pair_verification_roots == (receipt.root,)


def test_pair_verification_cannot_be_rebound_to_different_pair_root() -> None:
    campaign, mac, pair, system, baseline, system_att, baseline_att = _fixture()
    receipt = mac.issue_pair_verification(
        run_id=RUN_ID,
        pair=pair,
        system_result=system,
        baseline_result=baseline,
        system_attestation=system_att,
        baseline_attestation=baseline_att,
    )
    tampered_pair = replace(pair, system_result_root="f" * 64)
    with pytest.raises(EvaluationCampaignError, match="PAIR_VERIFICATION_PAIR_ROOT_MISMATCH"):
        _bundle(campaign, mac, tampered_pair, receipt)


def test_pair_verification_issuer_rechecks_result_attestations_and_pair_binding() -> None:
    _campaign, mac, pair, system, baseline, system_att, baseline_att = _fixture()
    bad_system_att = replace(system_att, trial_index=1)
    with pytest.raises(EvaluationCampaignError, match="ATTESTATION_TRIAL_INDEX_MISMATCH"):
        mac.issue_pair_verification(
            run_id=RUN_ID,
            pair=pair,
            system_result=system,
            baseline_result=baseline,
            system_attestation=bad_system_att,
            baseline_attestation=baseline_att,
        )


def test_pair_verification_is_nominal_hmac_attestation_not_public_signature() -> None:
    assert PairVerificationAttestationV1.__name__ == "PairVerificationAttestationV1"
