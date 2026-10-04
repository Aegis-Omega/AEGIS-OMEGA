from __future__ import annotations

import pytest

from harness.sdk.agi_evidence import (
    AGIEvidenceEvaluator,
    AGIEvidenceStatus,
    CapabilityTaskSpecV1,
    ContaminationClass,
    DeterministicCheckerAdapterV1,
    EvidenceAxis,
    EvidenceProtocolError,
    EvaluationSuiteV1,
)


def _suite() -> EvaluationSuiteV1:
    tasks = tuple(
        CapabilityTaskSpecV1(
            task_id=f"baseline-{i}",
            axis=axis,
            domain=f"domain-{i}",
            hidden_case_commitment=f"{i + 1:064x}",
            checker_commitment=f"{i + 101:064x}",
            budget_commitment=f"{i + 201:064x}",
            human_reference_commitment=f"{i + 301:064x}",
            trial_count=1,
            contamination_class=ContaminationClass.HELD_OUT,
        )
        for i, axis in enumerate(EvidenceAxis)
    )
    return EvaluationSuiteV1.create(
        suite_id="baseline-attribution-v1",
        tasks=tasks,
        axis_threshold_bps={axis: 8000 for axis in EvidenceAxis},
        strongest_constituent_baseline_commitment="a" * 64,
        evaluated_system_commitment="b" * 64,
    )


def _results(suite: EvaluationSuiteV1, *, runtime: str, score_bps: int, equal_axis: EvidenceAxis | None = None):
    results = []
    for task in suite.tasks:
        score = 9000 if task.axis is equal_axis else score_bps
        adapter = DeterministicCheckerAdapterV1(
            checker_commitment=task.checker_commitment,
            provider_runtime_commitment=runtime,
            checker=lambda _output, score=score: (True, score),
        )
        results.append(
            adapter.issue_result(
                task=task,
                trial_index=0,
                candidate_output=f"{runtime}:{task.task_id}".encode(),
                predicted_correctness_bps=9000,
                execution_receipt_root="e" * 64,
                effect_receipt_root="f" * 64,
                admission_record_root="1" * 64,
            )
        )
    return results


def test_threshold_met_does_not_imply_collective_contribution_without_baseline_results() -> None:
    suite = _suite()
    system_results = _results(suite, runtime=suite.evaluated_system_commitment, score_bps=9000)
    assessment = AGIEvidenceEvaluator().evaluate(suite, system_results)
    assert assessment.status is AGIEvidenceStatus.PREREGISTERED_THRESHOLD_MET
    assert assessment.collective_contribution_established is False
    assert all(axis.baseline_mean_score_bps is None for axis in assessment.axis_assessments.values())
    assert all(axis.system_minus_baseline_bps is None for axis in assessment.axis_assessments.values())


def test_positive_delta_on_every_required_axis_establishes_collective_contribution() -> None:
    suite = _suite()
    system_results = _results(suite, runtime=suite.evaluated_system_commitment, score_bps=9000)
    baseline_results = _results(suite, runtime=suite.strongest_constituent_baseline_commitment, score_bps=7000)
    assessment = AGIEvidenceEvaluator().evaluate(suite, system_results, baseline_results=baseline_results)
    assert assessment.collective_contribution_established is True
    assert all(axis.baseline_mean_score_bps == 7000 for axis in assessment.axis_assessments.values())
    assert all(axis.system_minus_baseline_bps == 2000 for axis in assessment.axis_assessments.values())
    assert all(axis.collective_contribution_positive is True for axis in assessment.axis_assessments.values())


def test_nonpositive_delta_on_one_axis_blocks_collective_contribution_claim() -> None:
    suite = _suite()
    system_results = _results(suite, runtime=suite.evaluated_system_commitment, score_bps=9000)
    baseline_results = _results(
        suite,
        runtime=suite.strongest_constituent_baseline_commitment,
        score_bps=7000,
        equal_axis=EvidenceAxis.LONG_HORIZON_RELIABILITY,
    )
    assessment = AGIEvidenceEvaluator().evaluate(suite, system_results, baseline_results=baseline_results)
    assert assessment.collective_contribution_established is False
    assert assessment.axis_assessments[EvidenceAxis.LONG_HORIZON_RELIABILITY].system_minus_baseline_bps == 0
    assert assessment.axis_assessments[EvidenceAxis.LONG_HORIZON_RELIABILITY].collective_contribution_positive is False


def test_baseline_results_must_match_preregistered_constituent_identity() -> None:
    suite = _suite()
    system_results = _results(suite, runtime=suite.evaluated_system_commitment, score_bps=9000)
    wrong_baseline = _results(suite, runtime="9" * 64, score_bps=7000)
    with pytest.raises(EvidenceProtocolError, match="BASELINE_RUNTIME_COMMITMENT_MISMATCH"):
        AGIEvidenceEvaluator().evaluate(suite, system_results, baseline_results=wrong_baseline)


def test_baseline_trial_cardinality_must_match_system_manifest() -> None:
    suite = _suite()
    system_results = _results(suite, runtime=suite.evaluated_system_commitment, score_bps=9000)
    baseline_results = _results(suite, runtime=suite.strongest_constituent_baseline_commitment, score_bps=7000)
    with pytest.raises(EvidenceProtocolError, match="BASELINE_TRIAL_CARDINALITY_MISMATCH"):
        AGIEvidenceEvaluator().evaluate(suite, system_results, baseline_results=baseline_results[:-1])
