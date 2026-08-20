from __future__ import annotations

import pytest

from harness.sdk.agi_evidence import CapabilityTaskSpecV1, ContaminationClass, EvidenceAxis
from harness.sdk.evaluation_campaign import (
    BaselineSelectionMode,
    BenchmarkFamily,
    BenchmarkTrackSpecV1,
    CampaignTaskTrialUnitV1,
    EvaluationCampaignError,
    EvaluationCampaignManifestV1,
    MetricKind,
    SplitPrivacy,
    StatisticalMode,
)


def _track() -> BenchmarkTrackSpecV1:
    task = CapabilityTaskSpecV1(
        task_id="baseline-selection-task",
        axis=EvidenceAxis.NOVEL_ABSTRACTION_TRANSFER,
        domain="evaluation-campaign",
        hidden_case_commitment="1" * 64,
        checker_commitment="2" * 64,
        budget_commitment="3" * 64,
        human_reference_commitment="4" * 64,
        trial_count=1,
        contamination_class=ContaminationClass.HELD_OUT,
    )
    return BenchmarkTrackSpecV1.create(
        track_id="baseline-selection-track",
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


def _campaign(mode: BaselineSelectionMode) -> EvaluationCampaignManifestV1:
    return EvaluationCampaignManifestV1.create(
        campaign_id="baseline-selection-campaign",
        uci7_suite_root="6" * 64,
        evaluated_system_commitment="a" * 64,
        strongest_constituent_baseline_commitment="b" * 64,
        tracks=(_track(),),
        baseline_selection_mode=mode,
    )


def test_fixed_apriori_campaign_baseline_is_explicitly_serialized() -> None:
    campaign = _campaign(BaselineSelectionMode.FIXED_A_PRIORI_CAMPAIGN)
    assert campaign.baseline_selection_mode is BaselineSelectionMode.FIXED_A_PRIORI_CAMPAIGN
    assert campaign.to_dict()["baseline_selection_mode"] == "FIXED_A_PRIORI_CAMPAIGN"


def test_same_comparison_data_per_task_baseline_is_rejected() -> None:
    with pytest.raises(EvaluationCampaignError, match="BASELINE_SELECTION_USES_COMPARISON_DATA"):
        _campaign(BaselineSelectionMode.SAME_COMPARISON_DATA_PER_TASK)


def test_separate_per_task_selection_is_not_silently_claimed_in_v1() -> None:
    with pytest.raises(EvaluationCampaignError, match="PER_TASK_BASELINE_SELECTION_NOT_IMPLEMENTED_V1"):
        _campaign(BaselineSelectionMode.SEPARATE_SELECTION_SPLIT_PER_TASK)
