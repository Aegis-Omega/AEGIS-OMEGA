from __future__ import annotations

import pytest

from harness.sdk.closed_loop_epistemic_actuation import (
    CAPABILITY_BOOST_ONLY,
    EVIDENCE_ONLY,
    INFORMATION_GAIN_UNESTABLISHED,
    LEARNING_EFFECT_ESTABLISHED,
    VERIFIED_INFORMATION_GAIN,
    LearningInterventionV1,
    ObservationEvidenceV1,
    ObservationTransformV1,
    evaluate_learning_effect,
    verify_observation_effect,
)
from harness.sdk.resident_runtime import AnalysisPacketV1, ZERO_HASH


def _sha(ch: str) -> str:
    return ch * 64


def test_action_conditioned_observation_requires_transform_binding() -> None:
    plan = ObservationTransformV1(
        action_id="inspect:file:1",
        action_kind="REPOSITORY_FILE_READ",
        target_scope="src/core.py",
        predicted_transform="BYTE_EXACT_FILE_CONTENT",
        budget_units=1,
    )
    evidence = ObservationEvidenceV1(
        action_id="inspect:file:other",
        observed_transform="BYTE_EXACT_FILE_CONTENT",
        observation_root=_sha("a"),
        prior_entropy_bits=5.0,
        posterior_entropy_bits=2.0,
        calibration_before_bps=8000,
        calibration_after_bps=8500,
        missed_critical_feature=False,
    )

    with pytest.raises(ValueError, match="OBSERVATION_ACTION_BINDING_MISMATCH"):
        verify_observation_effect(plan, evidence)


def test_information_gain_is_verified_only_with_bound_calibrated_observation() -> None:
    plan = ObservationTransformV1(
        action_id="inspect:symbol:1",
        action_kind="SYMBOL_INSPECTION",
        target_scope="harness.sdk.resident_runtime",
        predicted_transform="SYMBOL_LEVEL_VIEW",
        budget_units=2,
    )
    evidence = ObservationEvidenceV1(
        action_id=plan.action_id,
        observed_transform=plan.predicted_transform,
        observation_root=_sha("b"),
        prior_entropy_bits=7.5,
        posterior_entropy_bits=3.0,
        calibration_before_bps=7000,
        calibration_after_bps=8200,
        missed_critical_feature=False,
    )

    receipt = verify_observation_effect(plan, evidence)

    assert receipt.status == VERIFIED_INFORMATION_GAIN
    assert receipt.information_gain_bits == pytest.approx(4.5)
    assert receipt.information_gain_established is True
    assert receipt.authority == EVIDENCE_ONLY
    assert receipt.may_mint_execution_authority is False
    assert receipt.may_mint_learning_authority is False
    assert len(receipt.root) == 64


def test_entropy_reduction_without_calibration_does_not_establish_information_gain() -> None:
    plan = ObservationTransformV1(
        action_id="inspect:trace:1",
        action_kind="EXECUTION_TRACE",
        target_scope="run-1",
        predicted_transform="TEMPORAL_TRACE_VIEW",
        budget_units=3,
    )
    evidence = ObservationEvidenceV1(
        action_id=plan.action_id,
        observed_transform=plan.predicted_transform,
        observation_root=_sha("c"),
        prior_entropy_bits=8.0,
        posterior_entropy_bits=1.0,
        calibration_before_bps=9000,
        calibration_after_bps=6000,
        missed_critical_feature=False,
    )

    receipt = verify_observation_effect(plan, evidence)

    assert receipt.status == INFORMATION_GAIN_UNESTABLISHED
    assert receipt.information_gain_bits == pytest.approx(7.0)
    assert receipt.information_gain_established is False
    assert "CALIBRATION_WORSENED" in receipt.reason_codes


def test_compute_only_boost_cannot_mint_learning_even_when_immediate_score_rises() -> None:
    intervention = LearningInterventionV1(
        intervention_id="compute-boost-1",
        mechanism_class="COMPUTE_ONLY",
        mechanism="extra_test_time_compute",
        matched_control_id="sham-compute-1",
        pre_performance_bps=5000,
        immediate_performance_bps=7800,
        delayed_performance_bps=5200,
        control_pre_performance_bps=5000,
        control_delayed_performance_bps=5100,
        pre_transfer_bps=4000,
        post_transfer_bps=4100,
        control_pre_transfer_bps=4000,
        control_post_transfer_bps=4050,
        durable_state_before=_sha("d"),
        durable_state_after=_sha("d"),
        independent_replay_receipt_sha=_sha("e"),
    )

    receipt = evaluate_learning_effect(intervention, minimum_effect_bps=100)

    assert receipt.status == CAPABILITY_BOOST_ONLY
    assert receipt.learning_established is False
    assert receipt.immediate_gain_bps == 2800
    assert receipt.authority == EVIDENCE_ONLY
    assert receipt.may_mint_execution_authority is False


def test_learning_requires_retention_transfer_control_and_durable_state_change() -> None:
    intervention = LearningInterventionV1(
        intervention_id="adapt-1",
        mechanism_class="STATE_ADAPTATION",
        mechanism="verified_memory_update",
        matched_control_id="sham-adapt-1",
        pre_performance_bps=5000,
        immediate_performance_bps=7000,
        delayed_performance_bps=6800,
        control_pre_performance_bps=5000,
        control_delayed_performance_bps=5200,
        pre_transfer_bps=4000,
        post_transfer_bps=5900,
        control_pre_transfer_bps=4000,
        control_post_transfer_bps=4200,
        durable_state_before=_sha("1"),
        durable_state_after=_sha("2"),
        independent_replay_receipt_sha=_sha("3"),
    )

    receipt = evaluate_learning_effect(intervention, minimum_effect_bps=500)

    assert receipt.status == LEARNING_EFFECT_ESTABLISHED
    assert receipt.learning_established is True
    assert receipt.retention_gain_vs_control_bps == 1600
    assert receipt.transfer_gain_vs_control_bps == 1700
    assert receipt.authority == EVIDENCE_ONLY
    assert receipt.may_mint_execution_authority is False
    assert receipt.may_mint_admission_authority is False
    assert len(receipt.root) == 64


def test_resident_analysis_packet_no_longer_defaults_verified_decision_to_information_gain() -> None:
    packet = AnalysisPacketV1(
        run_id="run-1",
        task_id="task-1",
        repository_head="a" * 40,
        changed_path="README.md",
        question="inspect",
        observed_content_sha256=_sha("4"),
        observation_root=_sha("5"),
        expected_information_gain_bps=5000,
        budget_microunits=10,
    )

    assert packet.observation_transform_root == ZERO_HASH
    assert packet.observation_receipt_root == ZERO_HASH
    assert packet.observed_information_gain_bps is None
