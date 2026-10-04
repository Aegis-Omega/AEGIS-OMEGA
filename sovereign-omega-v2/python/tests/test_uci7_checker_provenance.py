from __future__ import annotations

import pytest

from harness.sdk.agi_evidence import (
    AGIEvidenceEvaluator,
    CapabilityTaskSpecV1,
    CapabilityTrialResultV1,
    ContaminationClass,
    EvidenceAxis,
    EvidenceProtocolError,
    EvaluationSuiteV1,
)


def _fabricated_suite_and_results(*, runtime_commitment: str) -> tuple[EvaluationSuiteV1, tuple[CapabilityTrialResultV1, ...]]:
    axes = tuple(EvidenceAxis)
    tasks = tuple(
        CapabilityTaskSpecV1(
            task_id=f"fabrication-{i}",
            axis=axis,
            domain=f"domain-{i}",
            hidden_case_commitment=f"{i + 1:064x}",
            checker_commitment=f"{i + 101:064x}",
            budget_commitment=f"{i + 201:064x}",
            human_reference_commitment=f"{i + 301:064x}",
            trial_count=1,
            contamination_class=ContaminationClass.HELD_OUT,
        )
        for i, axis in enumerate(axes)
    )
    suite = EvaluationSuiteV1.create(
        suite_id="fabrication-rejection-v1",
        tasks=tasks,
        axis_threshold_bps={axis: 8000 for axis in axes},
        strongest_constituent_baseline_commitment="a" * 64,
        evaluated_system_commitment="b" * 64,
    )
    fabricated = tuple(
        CapabilityTrialResultV1(
            task_spec_root=task.root,
            trial_index=0,
            checker_verdict=True,
            checker_score_bps=9000,
            predicted_correctness_bps=9000,
            output_digest="c" * 64,
            checker_commitment=task.checker_commitment,
            budget_commitment=task.budget_commitment,
            provider_runtime_commitment=runtime_commitment,
            execution_receipt_root="e" * 64,
            effect_receipt_root="f" * 64,
            admission_record_root="1" * 64,
        )
        for task in suite.tasks
    )
    return suite, fabricated


def test_publicly_constructed_checker_results_cannot_reach_threshold_met() -> None:
    suite, fabricated = _fabricated_suite_and_results(runtime_commitment="b" * 64)
    with pytest.raises(EvidenceProtocolError, match="TRIAL_RESULT_NOT_CHECKER_ISSUED"):
        AGIEvidenceEvaluator().evaluate(suite, fabricated)


def test_result_runtime_must_match_preregistered_evaluated_system() -> None:
    suite, fabricated = _fabricated_suite_and_results(runtime_commitment="9" * 64)
    with pytest.raises(EvidenceProtocolError, match="EVALUATED_SYSTEM_COMMITMENT_MISMATCH"):
        AGIEvidenceEvaluator().evaluate(suite, fabricated)
