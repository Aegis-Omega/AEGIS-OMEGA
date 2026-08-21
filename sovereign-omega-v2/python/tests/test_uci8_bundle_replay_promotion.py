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
    PairedBenchmarkTrialV1,
    SplitPrivacy,
    StatisticalMode,
)


def _fixture():
    task = CapabilityTaskSpecV1(
        task_id="uci8-bundle-replay",
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
        track_id="bundle-replay-track",
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
        campaign_id="bundle-replay-campaign",
        uci7_suite_root="6" * 64,
        evaluated_system_commitment="a" * 64,
        strongest_constituent_baseline_commitment="b" * 64,
        tracks=(track,),
    )

    def issued(runtime: str, score: int):
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

    pair = PairedBenchmarkTrialV1.create(
        campaign=campaign,
        track=track,
        system_result=issued(campaign.evaluated_system_commitment, 9000),
        baseline_result=issued(campaign.strongest_constituent_baseline_commitment, 7000),
    )
    return campaign, pair


def _bundle(campaign, pair):
    return CampaignEvidenceBundleV1.create(
        campaign=campaign,
        pairs=(pair,),
        benchmark_adapter_executable_commitment="7" * 64,
        runner_environment_commitment="8" * 64,
        execution_receipt_bundle_commitment="9" * 64,
    )


def test_process_local_pair_is_not_portable_collective_evidence() -> None:
    campaign, pair = _fixture()
    bundle = _bundle(campaign, pair)
    assert bundle.evidence_status is CampaignEvidenceStatus.HELD_OUT_EVIDENCE_COMPLETE


def test_reconstructed_pair_cannot_replay_into_bundle_without_portable_verification() -> None:
    campaign, pair = _fixture()
    replayed_pair = replace(pair)
    with pytest.raises(EvaluationCampaignError, match="PAIR_REPLAY_VERIFICATION_REQUIRED"):
        _bundle(campaign, replayed_pair)
