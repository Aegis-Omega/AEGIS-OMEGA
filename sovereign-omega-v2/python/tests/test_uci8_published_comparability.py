from __future__ import annotations

import pytest

from harness.sdk.agi_evidence import CapabilityTaskSpecV1, ContaminationClass, EvidenceAxis
from harness.sdk.evaluation_campaign import (
    BenchmarkFamily,
    BenchmarkTrackSpecV1,
    CampaignTaskTrialUnitV1,
    EvaluationCampaignError,
    MetricKind,
    PublishedComparability,
    SplitPrivacy,
    StatisticalMode,
)
from harness.sdk.sovereign_execution import ZERO_HASH


def _metr_track(
    *,
    comparability: PublishedComparability = PublishedComparability.NOT_COMPARABLE_TO_PUBLISHED,
    methodology_commitment: str = ZERO_HASH,
) -> BenchmarkTrackSpecV1:
    task = CapabilityTaskSpecV1(
        task_id="metr-comparability-task",
        axis=EvidenceAxis.LONG_HORIZON_RELIABILITY,
        domain="evaluation-campaign",
        hidden_case_commitment="1" * 64,
        checker_commitment="2" * 64,
        budget_commitment="3" * 64,
        human_reference_commitment="4" * 64,
        trial_count=1,
        contamination_class=ContaminationClass.HELD_OUT,
    )
    return BenchmarkTrackSpecV1.create(
        track_id="metr-comparability-track",
        benchmark_family=BenchmarkFamily.METR_TIME_HORIZON,
        benchmark_version="2026.1",
        benchmark_source_commitment="5" * 64,
        split_id="private-eval",
        split_privacy=SplitPrivacy.PRIVATE,
        metric_kind=MetricKind.HUMAN_EQUIVALENT_TASK_HORIZON,
        task_trial_units=(CampaignTaskTrialUnitV1(task_spec_root=task.root, trial_index=0),),
        scorer_commitment=task.checker_commitment,
        budget_commitment=task.budget_commitment,
        human_reference_commitment=task.human_reference_commitment,
        contamination_class=ContaminationClass.HELD_OUT,
        repetition_count=1,
        statistical_mode=StatisticalMode.PAIRED_DESCRIPTIVE_V1,
        published_comparability=comparability,
        published_methodology_commitment=methodology_commitment,
    )


def test_human_equivalent_metr_semantics_do_not_imply_published_comparability() -> None:
    track = _metr_track()
    assert track.metric_kind is MetricKind.HUMAN_EQUIVALENT_TASK_HORIZON
    assert track.published_comparability is PublishedComparability.NOT_COMPARABLE_TO_PUBLISHED
    assert track.to_dict()["published_comparability"] == "NOT_COMPARABLE_TO_PUBLISHED"


def test_claiming_published_methodology_match_requires_bound_methodology() -> None:
    with pytest.raises(EvaluationCampaignError, match="PUBLISHED_METHODOLOGY_COMMITMENT_REQUIRED"):
        _metr_track(comparability=PublishedComparability.PUBLISHED_METHODOLOGY_MATCHED)


def test_bound_methodology_can_explicitly_mark_published_comparability() -> None:
    track = _metr_track(
        comparability=PublishedComparability.PUBLISHED_METHODOLOGY_MATCHED,
        methodology_commitment="9" * 64,
    )
    assert track.published_methodology_commitment == "9" * 64
    assert track.to_dict()["published_comparability"] == "PUBLISHED_METHODOLOGY_MATCHED"
