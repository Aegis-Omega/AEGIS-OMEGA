from __future__ import annotations

import pytest

from harness.sdk.agi_evidence import CapabilityTaskSpecV1, ContaminationClass, EvidenceAxis
from harness.sdk.evaluation_campaign import (
    BenchmarkFamily,
    BenchmarkTrackSpecV1,
    CampaignTaskTrialUnitV1,
    DeltaResolutionStatus,
    EvaluationCampaignError,
    MetricKind,
    SplitPrivacy,
    StatisticalMode,
)
from harness.sdk.sovereign_execution import ZERO_HASH


def _track(
    *,
    resolution_bps: int | None = None,
    basis_commitment: str = ZERO_HASH,
) -> BenchmarkTrackSpecV1:
    task = CapabilityTaskSpecV1(
        task_id="measurement-resolution-task",
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
        track_id="measurement-resolution-track",
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
        measurement_resolution_bps=resolution_bps,
        measurement_resolution_basis_commitment=basis_commitment,
    )


def test_resolution_is_not_established_without_repeated_run_evidence() -> None:
    track = _track()
    assert track.classify_delta_resolution(100) is DeltaResolutionStatus.NOT_ESTABLISHED
    assert track.measurement_resolution_bps is None


def test_declared_resolution_requires_bound_run_to_run_basis() -> None:
    with pytest.raises(EvaluationCampaignError, match="MEASUREMENT_RESOLUTION_BASIS_REQUIRED"):
        _track(resolution_bps=200)


def test_descriptive_floor_labels_deltas_without_inferential_claim() -> None:
    track = _track(resolution_bps=200, basis_commitment="9" * 64)
    assert track.classify_delta_resolution(199) is DeltaResolutionStatus.BELOW_MEASUREMENT_RESOLUTION
    assert track.classify_delta_resolution(-199) is DeltaResolutionStatus.BELOW_MEASUREMENT_RESOLUTION
    assert track.classify_delta_resolution(200) is DeltaResolutionStatus.AT_OR_ABOVE_MEASUREMENT_RESOLUTION
    assert track.classify_delta_resolution(350) is DeltaResolutionStatus.AT_OR_ABOVE_MEASUREMENT_RESOLUTION
    assert track.to_dict()["measurement_resolution_basis_commitment"] == "9" * 64


def test_bps_resolution_is_not_silently_applied_to_horizon_metric() -> None:
    arc = _track(resolution_bps=200, basis_commitment="9" * 64)
    with pytest.raises(EvaluationCampaignError, match="BPS_RESOLUTION_NOT_APPLICABLE_TO_HORIZON_METRIC"):
        BenchmarkTrackSpecV1.create(
            track_id="bad-horizon-resolution",
            benchmark_family=BenchmarkFamily.METR_TIME_HORIZON,
            benchmark_version="2026.1",
            benchmark_source_commitment="5" * 64,
            split_id="private-eval",
            split_privacy=SplitPrivacy.PRIVATE,
            metric_kind=MetricKind.HUMAN_EQUIVALENT_TASK_HORIZON,
            task_trial_units=arc.task_trial_units,
            scorer_commitment=arc.scorer_commitment,
            budget_commitment=arc.budget_commitment,
            human_reference_commitment=arc.human_reference_commitment,
            contamination_class=ContaminationClass.HELD_OUT,
            repetition_count=1,
            statistical_mode=StatisticalMode.PAIRED_DESCRIPTIVE_V1,
            measurement_resolution_bps=200,
            measurement_resolution_basis_commitment="9" * 64,
        )
