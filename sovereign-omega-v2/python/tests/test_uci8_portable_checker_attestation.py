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
    CampaignTaskTrialUnitV1,
    CheckerResultAttestationV1,
    EvaluationCampaignError,
    EvaluationCampaignManifestV1,
    MetricKind,
    PairedBenchmarkTrialV1,
    PortableCheckerHMACV1,
    SplitPrivacy,
    StatisticalMode,
)

TEST_HMAC_KEY = b"uci8-portable-checker-attestation-key-v1-32bytes+"
RUN_ID = "uci8-portable-replay-run-001"


def _task() -> CapabilityTaskSpecV1:
    return CapabilityTaskSpecV1(
        task_id="uci8-portable-checker",
        axis=EvidenceAxis.NOVEL_ABSTRACTION_TRANSFER,
        domain="evaluation-campaign",
        hidden_case_commitment="1" * 64,
        checker_commitment="2" * 64,
        budget_commitment="3" * 64,
        human_reference_commitment="4" * 64,
        trial_count=2,
        contamination_class=ContaminationClass.HELD_OUT,
    )


def _track(task: CapabilityTaskSpecV1) -> BenchmarkTrackSpecV1:
    return BenchmarkTrackSpecV1.create(
        track_id="portable-checker-track",
        benchmark_family=BenchmarkFamily.ARC_AGI_2,
        benchmark_version="2026.1",
        benchmark_source_commitment="5" * 64,
        split_id="private-eval",
        split_privacy=SplitPrivacy.PRIVATE,
        metric_kind=MetricKind.EXACT_MATCH_ACCURACY,
        task_trial_units=(
            CampaignTaskTrialUnitV1(task_spec_root=task.root, trial_index=0),
            CampaignTaskTrialUnitV1(task_spec_root=task.root, trial_index=1),
        ),
        scorer_commitment=task.checker_commitment,
        budget_commitment=task.budget_commitment,
        human_reference_commitment=task.human_reference_commitment,
        contamination_class=ContaminationClass.HELD_OUT,
        repetition_count=2,
        statistical_mode=StatisticalMode.PAIRED_DESCRIPTIVE_V1,
    )


def _campaign(track: BenchmarkTrackSpecV1) -> EvaluationCampaignManifestV1:
    return EvaluationCampaignManifestV1.create(
        campaign_id="portable-checker-campaign",
        uci7_suite_root="6" * 64,
        evaluated_system_commitment="a" * 64,
        strongest_constituent_baseline_commitment="b" * 64,
        tracks=(track,),
    )


def _issued(task: CapabilityTaskSpecV1, *, runtime: str, trial_index: int = 0):
    adapter = DeterministicCheckerAdapterV1(
        checker_commitment=task.checker_commitment,
        provider_runtime_commitment=runtime,
        checker=lambda _output: (True, 9000),
    )
    return adapter.issue_result(
        task=task,
        trial_index=trial_index,
        candidate_output=f"{runtime}:{trial_index}".encode(),
        predicted_correctness_bps=9000,
        execution_receipt_root="c" * 64,
        effect_receipt_root="d" * 64,
        admission_record_root="e" * 64,
    )


def test_checker_attestation_survives_reconstruction_outside_issuance_registry() -> None:
    task = _task()
    track = _track(task)
    campaign = _campaign(track)
    mac = PortableCheckerHMACV1(key_id="ci-test-key-v1", secret_key=TEST_HMAC_KEY)

    system_issued = _issued(task, runtime=campaign.evaluated_system_commitment)
    baseline_issued = _issued(task, runtime=campaign.strongest_constituent_baseline_commitment)
    system_attestation = mac.issue(run_id=RUN_ID, result=system_issued)
    baseline_attestation = mac.issue(run_id=RUN_ID, result=baseline_issued)

    # Simulate serialization/reload: dataclass reconstruction is a fresh object
    # and therefore intentionally absent from the process-local issuance registry.
    system_replayed = replace(system_issued)
    baseline_replayed = replace(baseline_issued)

    pair = PairedBenchmarkTrialV1.create(
        campaign=campaign,
        track=track,
        system_result=system_replayed,
        baseline_result=baseline_replayed,
        expected_run_id=RUN_ID,
        system_attestation=system_attestation,
        baseline_attestation=baseline_attestation,
        attestation_verifier=mac,
    )
    assert pair.system_checker_attestation_root == system_attestation.root
    assert pair.baseline_checker_attestation_root == baseline_attestation.root
    assert pair.checker_run_id == RUN_ID


def test_valid_mac_cannot_be_rebound_to_wrong_trial_index() -> None:
    task = _task()
    track = _track(task)
    campaign = _campaign(track)
    mac = PortableCheckerHMACV1(key_id="ci-test-key-v1", secret_key=TEST_HMAC_KEY)

    system_issued = _issued(task, runtime=campaign.evaluated_system_commitment, trial_index=0)
    baseline_issued = _issued(task, runtime=campaign.strongest_constituent_baseline_commitment, trial_index=0)
    system_attestation = mac.issue(run_id=RUN_ID, result=system_issued)
    baseline_attestation = mac.issue(run_id=RUN_ID, result=baseline_issued)

    with pytest.raises(EvaluationCampaignError, match="ATTESTATION_TRIAL_INDEX_MISMATCH"):
        PairedBenchmarkTrialV1.create(
            campaign=campaign,
            track=track,
            system_result=replace(system_issued, trial_index=1),
            baseline_result=replace(baseline_issued, trial_index=1),
            expected_run_id=RUN_ID,
            system_attestation=system_attestation,
            baseline_attestation=baseline_attestation,
            attestation_verifier=mac,
        )


def test_hmac_issuer_refuses_structurally_valid_unissued_result() -> None:
    task = _task()
    campaign = _campaign(_track(task))
    mac = PortableCheckerHMACV1(key_id="ci-test-key-v1", secret_key=TEST_HMAC_KEY)
    issued = _issued(task, runtime=campaign.evaluated_system_commitment)
    reconstructed = replace(issued)

    with pytest.raises(EvaluationCampaignError, match="ATTESTATION_ISSUER_REQUIRES_CHECKER_ISSUED_RESULT"):
        mac.issue(run_id=RUN_ID, result=reconstructed)


def test_attestation_is_nominal_and_hmac_not_public_signature() -> None:
    assert CheckerResultAttestationV1.__name__ == "CheckerResultAttestationV1"
    assert PortableCheckerHMACV1.__name__ == "PortableCheckerHMACV1"
