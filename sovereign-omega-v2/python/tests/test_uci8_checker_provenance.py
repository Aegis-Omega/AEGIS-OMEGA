from __future__ import annotations

import hashlib

import pytest

from harness.sdk.agi_evidence import (
    CapabilityTaskSpecV1,
    CapabilityTrialResultV1,
    ContaminationClass,
    EvidenceAxis,
)
from harness.sdk.evaluation_campaign import (
    BenchmarkFamily,
    BenchmarkTrackSpecV1,
    CampaignTaskTrialUnitV1,
    EvaluationCampaignError,
    EvaluationCampaignManifestV1,
    MetricKind,
    PairedBenchmarkTrialV1,
    SplitPrivacy,
    StatisticalMode,
)


def _task() -> CapabilityTaskSpecV1:
    return CapabilityTaskSpecV1(
        task_id="uci8-checker-provenance",
        axis=EvidenceAxis.NOVEL_ABSTRACTION_TRANSFER,
        domain="evaluation-campaign",
        hidden_case_commitment="1" * 64,
        checker_commitment="2" * 64,
        budget_commitment="3" * 64,
        human_reference_commitment="4" * 64,
        trial_count=1,
        contamination_class=ContaminationClass.HELD_OUT,
    )


def _track(task: CapabilityTaskSpecV1) -> BenchmarkTrackSpecV1:
    return BenchmarkTrackSpecV1.create(
        track_id="checker-provenance-track",
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


def _campaign(track: BenchmarkTrackSpecV1) -> EvaluationCampaignManifestV1:
    return EvaluationCampaignManifestV1.create(
        campaign_id="uci8-checker-provenance-campaign",
        uci7_suite_root="6" * 64,
        evaluated_system_commitment="a" * 64,
        strongest_constituent_baseline_commitment="b" * 64,
        tracks=(track,),
    )


def _fabricated_result(
    task: CapabilityTaskSpecV1,
    *,
    runtime: str,
    payload: bytes,
) -> CapabilityTrialResultV1:
    return CapabilityTrialResultV1(
        task_spec_root=task.root,
        trial_index=0,
        checker_verdict=True,
        checker_score_bps=9000,
        predicted_correctness_bps=9000,
        output_digest=hashlib.sha256(payload).hexdigest(),
        checker_commitment=task.checker_commitment,
        budget_commitment=task.budget_commitment,
        provider_runtime_commitment=runtime,
        execution_receipt_root="c" * 64,
        effect_receipt_root="d" * 64,
        admission_record_root="e" * 64,
    )


def test_pair_rejects_structurally_valid_but_not_checker_issued_results() -> None:
    task = _task()
    track = _track(task)
    campaign = _campaign(track)

    with pytest.raises(EvaluationCampaignError, match="CHECKER_ISSUANCE_OR_PORTABLE_ATTESTATION_REQUIRED"):
        PairedBenchmarkTrialV1.create(
            campaign=campaign,
            track=track,
            system_result=_fabricated_result(
                task,
                runtime=campaign.evaluated_system_commitment,
                payload=b"fabricated-system-result",
            ),
            baseline_result=_fabricated_result(
                task,
                runtime=campaign.strongest_constituent_baseline_commitment,
                payload=b"fabricated-baseline-result",
            ),
        )
