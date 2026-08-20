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
from harness.sdk.sovereign_execution import ZERO_HASH


def _task(i: int = 0) -> CapabilityTaskSpecV1:
    return CapabilityTaskSpecV1(
        task_id=f"uci8-task-{i}",
        axis=EvidenceAxis.NOVEL_ABSTRACTION_TRANSFER,
        domain="evaluation-campaign",
        hidden_case_commitment=f"{i + 1:064x}",
        checker_commitment=f"{i + 101:064x}",
        budget_commitment=f"{i + 201:064x}",
        human_reference_commitment=f"{i + 301:064x}",
        trial_count=1,
        contamination_class=ContaminationClass.HELD_OUT,
    )


def _unit(task: CapabilityTaskSpecV1) -> CampaignTaskTrialUnitV1:
    return CampaignTaskTrialUnitV1(task_spec_root=task.root, trial_index=0)


def _track(
    task: CapabilityTaskSpecV1,
    *,
    family: BenchmarkFamily = BenchmarkFamily.ARC_AGI_2,
    privacy: SplitPrivacy = SplitPrivacy.PRIVATE,
    metric: MetricKind = MetricKind.EXACT_MATCH_ACCURACY,
    contamination: ContaminationClass = ContaminationClass.HELD_OUT,
    human_reference: str = "4" * 64,
) -> BenchmarkTrackSpecV1:
    return BenchmarkTrackSpecV1.create(
        track_id="track-1",
        benchmark_family=family,
        benchmark_version="2026.1",
        benchmark_source_commitment="1" * 64,
        split_id="private-eval",
        split_privacy=privacy,
        metric_kind=metric,
        task_trial_units=(_unit(task),),
        scorer_commitment=task.checker_commitment,
        budget_commitment=task.budget_commitment,
        human_reference_commitment=human_reference,
        contamination_class=contamination,
        repetition_count=1,
        statistical_mode=StatisticalMode.PAIRED_DESCRIPTIVE_V1,
    )


def _campaign(track: BenchmarkTrackSpecV1) -> EvaluationCampaignManifestV1:
    return EvaluationCampaignManifestV1.create(
        campaign_id="uci8-campaign-v1",
        uci7_suite_root="7" * 64,
        evaluated_system_commitment="b" * 64,
        strongest_constituent_baseline_commitment="a" * 64,
        tracks=(track,),
    )


def _result(task: CapabilityTaskSpecV1, *, runtime: str, score: int = 9000):
    adapter = DeterministicCheckerAdapterV1(
        checker_commitment=task.checker_commitment,
        provider_runtime_commitment=runtime,
        checker=lambda _output: (True, score),
    )
    return adapter.issue_result(
        task=task,
        trial_index=0,
        candidate_output=f"{runtime}:{task.task_id}".encode(),
        predicted_correctness_bps=score,
        execution_receipt_root="e" * 64,
        effect_receipt_root="f" * 64,
        admission_record_root="1" * 64,
    )


def _pair(task: CapabilityTaskSpecV1, track: BenchmarkTrackSpecV1, campaign: EvaluationCampaignManifestV1):
    return PairedBenchmarkTrialV1.create(
        campaign=campaign,
        track=track,
        system_result=_result(task, runtime=campaign.evaluated_system_commitment, score=9000),
        baseline_result=_result(task, runtime=campaign.strongest_constituent_baseline_commitment, score=7000),
    )


def test_track_root_binds_benchmark_version_and_task_trial_manifest() -> None:
    task = _task()
    track = _track(task)
    changed_version = BenchmarkTrackSpecV1.create(
        track_id=track.track_id,
        benchmark_family=track.benchmark_family,
        benchmark_version="2026.2",
        benchmark_source_commitment=track.benchmark_source_commitment,
        split_id=track.split_id,
        split_privacy=track.split_privacy,
        metric_kind=track.metric_kind,
        task_trial_units=track.task_trial_units,
        scorer_commitment=track.scorer_commitment,
        budget_commitment=track.budget_commitment,
        human_reference_commitment=track.human_reference_commitment,
        contamination_class=track.contamination_class,
        repetition_count=track.repetition_count,
        statistical_mode=track.statistical_mode,
    )
    changed_unit = BenchmarkTrackSpecV1.create(
        track_id=track.track_id,
        benchmark_family=track.benchmark_family,
        benchmark_version=track.benchmark_version,
        benchmark_source_commitment=track.benchmark_source_commitment,
        split_id=track.split_id,
        split_privacy=track.split_privacy,
        metric_kind=track.metric_kind,
        task_trial_units=(CampaignTaskTrialUnitV1(task_spec_root=_task(9).root, trial_index=0),),
        scorer_commitment=track.scorer_commitment,
        budget_commitment=track.budget_commitment,
        human_reference_commitment=track.human_reference_commitment,
        contamination_class=track.contamination_class,
        repetition_count=track.repetition_count,
        statistical_mode=track.statistical_mode,
    )
    assert changed_version.root != track.root
    assert changed_unit.root != track.root
    assert changed_unit.task_manifest_commitment != track.task_manifest_commitment


def test_public_development_split_cannot_claim_held_out_contamination() -> None:
    with pytest.raises(EvaluationCampaignError, match="PUBLIC_SPLIT_CANNOT_BE_HELD_OUT"):
        _track(_task(), privacy=SplitPrivacy.PUBLIC_DEV, contamination=ContaminationClass.HELD_OUT)


def test_inferential_statistical_mode_is_not_a_v1_surface() -> None:
    assert {mode.value for mode in StatisticalMode} == {"PAIRED_DESCRIPTIVE_V1"}
    with pytest.raises((ValueError, EvaluationCampaignError)):
        StatisticalMode("SIGNIFICANT_IMPROVEMENT")


def test_benchmark_family_metric_semantics_fail_closed() -> None:
    task = _task()
    with pytest.raises(EvaluationCampaignError, match="ARC_AGI_2_METRIC_MISMATCH"):
        _track(task, family=BenchmarkFamily.ARC_AGI_2, metric=MetricKind.TOOL_ASSISTED_QA_ACCURACY)
    with pytest.raises(EvaluationCampaignError, match="GAIA_METRIC_MISMATCH"):
        _track(task, family=BenchmarkFamily.GAIA, metric=MetricKind.EXACT_MATCH_ACCURACY)
    with pytest.raises(EvaluationCampaignError, match="METR_TIME_HORIZON_METRIC_MISMATCH"):
        _track(task, family=BenchmarkFamily.METR_TIME_HORIZON, metric=MetricKind.EXACT_MATCH_ACCURACY)


def test_metr_track_requires_nonzero_human_reference() -> None:
    with pytest.raises(EvaluationCampaignError, match="METR_HUMAN_REFERENCE_REQUIRED"):
        _track(
            _task(),
            family=BenchmarkFamily.METR_TIME_HORIZON,
            metric=MetricKind.HUMAN_EQUIVALENT_TASK_HORIZON,
            human_reference=ZERO_HASH,
        )


def test_pair_rejects_system_and_baseline_task_trial_splicing() -> None:
    task = _task()
    other = _task(1)
    track = _track(task)
    campaign = _campaign(track)
    with pytest.raises(EvaluationCampaignError, match="PAIRED_TASK_TRIAL_MISMATCH"):
        PairedBenchmarkTrialV1.create(
            campaign=campaign,
            track=track,
            system_result=_result(task, runtime=campaign.evaluated_system_commitment),
            baseline_result=_result(other, runtime=campaign.strongest_constituent_baseline_commitment),
        )


def test_pair_rejects_runtime_budget_and_scorer_rebinding() -> None:
    task = _task()
    track = _track(task)
    campaign = _campaign(track)
    system_result = _result(task, runtime=campaign.evaluated_system_commitment)
    baseline_result = _result(task, runtime=campaign.strongest_constituent_baseline_commitment)

    with pytest.raises(EvaluationCampaignError, match="SYSTEM_RUNTIME_COMMITMENT_MISMATCH"):
        PairedBenchmarkTrialV1.create(
            campaign=campaign,
            track=track,
            system_result=replace(system_result, provider_runtime_commitment="9" * 64),
            baseline_result=baseline_result,
        )

    with pytest.raises(EvaluationCampaignError, match="BUDGET_COMMITMENT_MISMATCH"):
        PairedBenchmarkTrialV1.create(
            campaign=campaign,
            track=track,
            system_result=replace(system_result, budget_commitment="8" * 64),
            baseline_result=baseline_result,
        )

    with pytest.raises(EvaluationCampaignError, match="SCORER_COMMITMENT_MISMATCH"):
        PairedBenchmarkTrialV1.create(
            campaign=campaign,
            track=track,
            system_result=replace(system_result, checker_commitment="9" * 64),
            baseline_result=baseline_result,
        )


def test_bundle_requires_exact_preregistered_pair_cardinality() -> None:
    task = _task()
    track = _track(task)
    campaign = _campaign(track)
    with pytest.raises(EvaluationCampaignError, match="PAIR_CARDINALITY_MISMATCH"):
        CampaignEvidenceBundleV1.create(
            campaign=campaign,
            pairs=(),
            benchmark_adapter_executable_commitment="5" * 64,
            runner_environment_commitment="6" * 64,
            execution_receipt_bundle_commitment="7" * 64,
        )


def test_public_or_contaminated_tracks_cannot_be_promoted_to_held_out_evidence() -> None:
    task = _task()
    public_track = _track(
        task,
        privacy=SplitPrivacy.PUBLIC_DEV,
        contamination=ContaminationClass.PUBLIC,
    )
    public_campaign = _campaign(public_track)
    public_bundle = CampaignEvidenceBundleV1.create(
        campaign=public_campaign,
        pairs=(_pair(task, public_track, public_campaign),),
        benchmark_adapter_executable_commitment="5" * 64,
        runner_environment_commitment="6" * 64,
        execution_receipt_bundle_commitment="7" * 64,
    )
    assert public_bundle.evidence_status is CampaignEvidenceStatus.DEVELOPMENT_EVIDENCE_ONLY

    suspect_track = _track(task, contamination=ContaminationClass.SUSPECTED)
    suspect_campaign = _campaign(suspect_track)
    suspect_bundle = CampaignEvidenceBundleV1.create(
        campaign=suspect_campaign,
        pairs=(_pair(task, suspect_track, suspect_campaign),),
        benchmark_adapter_executable_commitment="5" * 64,
        runner_environment_commitment="6" * 64,
        execution_receipt_bundle_commitment="7" * 64,
    )
    assert suspect_bundle.evidence_status is CampaignEvidenceStatus.INVALIDATED_CONTAMINATION


def test_clean_held_out_complete_pairing_is_only_collective_contribution_evaluable() -> None:
    task = _task()
    track = _track(task)
    campaign = _campaign(track)
    bundle = CampaignEvidenceBundleV1.create(
        campaign=campaign,
        pairs=(_pair(task, track, campaign),),
        benchmark_adapter_executable_commitment="5" * 64,
        runner_environment_commitment="6" * 64,
        execution_receipt_bundle_commitment="7" * 64,
    )
    assert bundle.evidence_status is CampaignEvidenceStatus.COLLECTIVE_CONTRIBUTION_EVALUABLE
    assert "AGI_PROVEN" not in {status.value for status in CampaignEvidenceStatus}
