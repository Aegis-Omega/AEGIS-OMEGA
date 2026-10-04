from __future__ import annotations

import pytest

from harness.sdk.agi_evidence import ContaminationClass
from harness.sdk.evaluation_campaign import (
    BenchmarkFamily,
    BenchmarkTrackSpecV1,
    CampaignTaskTrialUnitV1,
    EvaluationCampaignError,
    MetricKind,
    SplitPrivacy,
    StatisticalMode,
)


def _track(*, repetition_count: int, trial_indices: tuple[int, ...]) -> BenchmarkTrackSpecV1:
    task_root = "1" * 64
    return BenchmarkTrackSpecV1.create(
        track_id="repetition-integrity-v1",
        benchmark_family=BenchmarkFamily.ARC_AGI_2,
        benchmark_version="2026.1",
        benchmark_source_commitment="2" * 64,
        split_id="private-eval",
        split_privacy=SplitPrivacy.PRIVATE,
        metric_kind=MetricKind.EXACT_MATCH_ACCURACY,
        task_trial_units=tuple(
            CampaignTaskTrialUnitV1(task_spec_root=task_root, trial_index=index)
            for index in trial_indices
        ),
        scorer_commitment="3" * 64,
        budget_commitment="4" * 64,
        human_reference_commitment="5" * 64,
        contamination_class=ContaminationClass.HELD_OUT,
        repetition_count=repetition_count,
        statistical_mode=StatisticalMode.PAIRED_DESCRIPTIVE_V1,
    )


def test_declared_repetition_count_must_equal_exact_trial_index_manifest() -> None:
    with pytest.raises(EvaluationCampaignError, match="REPETITION_MANIFEST_MISMATCH"):
        _track(repetition_count=2, trial_indices=(0,))


def test_complete_zero_based_repetition_manifest_is_accepted() -> None:
    track = _track(repetition_count=2, trial_indices=(0, 1))
    assert track.repetition_count == 2
    assert tuple(unit.trial_index for unit in track.task_trial_units) == (0, 1)
