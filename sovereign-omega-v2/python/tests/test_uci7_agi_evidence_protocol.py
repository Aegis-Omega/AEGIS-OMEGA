from __future__ import annotations

import pytest

from harness.sdk.agi_evidence import (
    AGIEvidenceEvaluator,
    AGIEvidenceStatus,
    CapabilityTaskSpecV1,
    CapabilityTrialResultV1,
    ContaminationClass,
    DeterministicCheckerAdapterV1,
    EvidenceAxis,
    EvidenceProtocolError,
    EvaluationSuiteV1,
)


REQUIRED_AXES = (
    EvidenceAxis.NOVEL_ABSTRACTION_TRANSFER,
    EvidenceAxis.CROSS_DOMAIN_GENERALITY,
    EvidenceAxis.TOOL_AND_ENVIRONMENT_AGENCY,
    EvidenceAxis.LONG_HORIZON_RELIABILITY,
    EvidenceAxis.SAFE_ADAPTATION,
    EvidenceAxis.METACOGNITIVE_CALIBRATION,
)


def _task(axis: EvidenceAxis, i: int = 0, *, hidden: str | None = None) -> CapabilityTaskSpecV1:
    return CapabilityTaskSpecV1(
        task_id=f"{axis.value.lower()}-{i}",
        axis=axis,
        domain=f"domain-{i}",
        hidden_case_commitment=hidden or (f"{i + 1:064x}"[-64:]),
        checker_commitment=(f"{i + 101:064x}"[-64:]),
        budget_commitment=(f"{i + 201:064x}"[-64:]),
        human_reference_commitment=(f"{i + 301:064x}"[-64:]),
        trial_count=1,
        contamination_class=ContaminationClass.HELD_OUT,
    )


def _suite(*, axes=REQUIRED_AXES, threshold_bps: int = 8000) -> EvaluationSuiteV1:
    tasks = tuple(_task(axis, i) for i, axis in enumerate(axes))
    return EvaluationSuiteV1.create(
        suite_id="uci7-fixture-v1",
        tasks=tasks,
        axis_threshold_bps={axis: threshold_bps for axis in axes},
        strongest_constituent_baseline_commitment="a" * 64,
        evaluated_system_commitment="b" * 64,
    )


def _result(
    task: CapabilityTaskSpecV1,
    *,
    verdict: bool = True,
    score_bps: int = 9000,
    predicted_bps: int = 9000,
) -> CapabilityTrialResultV1:
    adapter = DeterministicCheckerAdapterV1(
        checker_commitment=task.checker_commitment,
        provider_runtime_commitment="b" * 64,
        checker=lambda _output: (verdict, score_bps),
    )
    return adapter.issue_result(
        task=task,
        trial_index=0,
        candidate_output=b"uci7-fixture-output",
        predicted_correctness_bps=predicted_bps,
        execution_receipt_root="e" * 64,
        effect_receipt_root="f" * 64,
        admission_record_root="1" * 64,
    )


def _pass_result(task: CapabilityTaskSpecV1, *, predicted_bps: int = 9000) -> CapabilityTrialResultV1:
    return _result(task, predicted_bps=predicted_bps)


def test_required_axis_failure_cannot_be_compensated_by_other_axes() -> None:
    suite = _suite()
    results = [_pass_result(t) for t in suite.tasks]
    failed = suite.tasks[0]
    results[0] = _result(failed, verdict=False, score_bps=0)
    assessment = AGIEvidenceEvaluator().evaluate(suite, results)
    assert assessment.status is not AGIEvidenceStatus.PREREGISTERED_THRESHOLD_MET
    assert assessment.axis_assessments[failed.axis].threshold_met is False


def test_missing_required_axis_fails_closed() -> None:
    suite = _suite(axes=REQUIRED_AXES[:-1])
    with pytest.raises(EvidenceProtocolError, match="REQUIRED_AXIS_MISSING"):
        AGIEvidenceEvaluator().evaluate(suite, [_pass_result(t) for t in suite.tasks])


def test_post_hoc_threshold_mutation_changes_suite_root_and_invalidates_results() -> None:
    suite = _suite(threshold_bps=8000)
    mutated = _suite(threshold_bps=7000)
    assert suite.root != mutated.root
    results = [_pass_result(t) for t in suite.tasks]
    with pytest.raises(EvidenceProtocolError, match="TASK_NOT_IN_SUITE"):
        AGIEvidenceEvaluator().evaluate(mutated, results)


def test_caller_declared_correctness_is_not_an_input_surface() -> None:
    task = _task(EvidenceAxis.NOVEL_ABSTRACTION_TRANSFER)
    with pytest.raises(TypeError):
        CapabilityTrialResultV1(
            task_spec_root=task.root,
            trial_index=0,
            checker_verdict=True,
            checker_score_bps=9000,
            predicted_correctness_bps=9000,
            caller_declared_correctness=True,  # type: ignore[call-arg]
            output_digest="c" * 64,
            checker_commitment=task.checker_commitment,
            budget_commitment=task.budget_commitment,
            provider_runtime_commitment="b" * 64,
            execution_receipt_root="e" * 64,
            effect_receipt_root="f" * 64,
            admission_record_root="1" * 64,
        )


def test_checker_commitment_mismatch_fails_closed() -> None:
    suite = _suite()
    result = _pass_result(suite.tasks[0])
    forged = CapabilityTrialResultV1(
        **{
            **result.to_dict(),
            "checker_commitment": "9" * 64,
        }
    )
    with pytest.raises(EvidenceProtocolError, match="CHECKER_COMMITMENT_MISMATCH"):
        AGIEvidenceEvaluator().evaluate(suite, [forged, *[_pass_result(t) for t in suite.tasks[1:]]])


def test_task_cardinality_drift_fails_closed() -> None:
    suite = _suite()
    with pytest.raises(EvidenceProtocolError, match="TRIAL_CARDINALITY_MISMATCH"):
        AGIEvidenceEvaluator().evaluate(suite, [_pass_result(t) for t in suite.tasks[:-1]])


def test_hidden_answer_exposure_rejects_entire_run() -> None:
    suite = _suite()
    results = [_pass_result(t) for t in suite.tasks]
    assessment = AGIEvidenceEvaluator().evaluate(suite, results, hidden_answer_exposure_detected=True)
    assert assessment.status is AGIEvidenceStatus.HYPOTHESIS_REJECTED


def test_safety_invariant_violation_overrides_capability_scores() -> None:
    suite = _suite()
    results = [_pass_result(t) for t in suite.tasks]
    assessment = AGIEvidenceEvaluator().evaluate(suite, results, safety_invariant_violation=True)
    assert assessment.status is AGIEvidenceStatus.HYPOTHESIS_REJECTED


def test_budget_mismatch_against_preregistered_task_fails_closed() -> None:
    suite = _suite()
    result = _pass_result(suite.tasks[0])
    forged = CapabilityTrialResultV1(
        **{
            **result.to_dict(),
            "budget_commitment": "8" * 64,
        }
    )
    with pytest.raises(EvidenceProtocolError, match="BUDGET_COMMITMENT_MISMATCH"):
        AGIEvidenceEvaluator().evaluate(suite, [forged, *[_pass_result(t) for t in suite.tasks[1:]]])


def test_metacognitive_calibration_uses_prediction_made_before_checker_revelation() -> None:
    suite = _suite()
    results = [_pass_result(t, predicted_bps=9000) for t in suite.tasks]
    calibration_task = next(t for t in suite.tasks if t.axis is EvidenceAxis.METACOGNITIVE_CALIBRATION)
    assessment = AGIEvidenceEvaluator().evaluate(suite, results)
    axis = assessment.axis_assessments[calibration_task.axis]
    assert axis.mean_calibration_error_bps == 1000


def test_unit_test_threshold_met_is_evidence_status_not_agi_proven() -> None:
    suite = _suite()
    results = [_pass_result(t) for t in suite.tasks]
    assessment = AGIEvidenceEvaluator().evaluate(suite, results)
    assert assessment.status is AGIEvidenceStatus.PREREGISTERED_THRESHOLD_MET
    assert "AGI_PROVEN" not in {status.value for status in AGIEvidenceStatus}
