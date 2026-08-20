"""UCI-7 preregistered AGI evidence protocol reference evaluator.

This module evaluates evidence *about* general capability. It does not create an
AGI authority state and intentionally contains no ``AGI_PROVEN`` status.

The evaluator is standard-library only and deterministic at every hashed
boundary. Model/provider outputs are inputs to deterministic checkers elsewhere;
caller-declared correctness is not an accepted field here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, Mapping

from harness.sdk.sovereign_execution import ZERO_HASH, canonical_hash

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")

CAPABILITY_TASK_SPEC_KIND = "CAPABILITY_TASK_SPEC_V1"
CAPABILITY_TRIAL_RESULT_KIND = "CAPABILITY_TRIAL_RESULT_V1"
EVALUATION_SUITE_KIND = "EVALUATION_SUITE_V1"
CAPABILITY_AXIS_ASSESSMENT_KIND = "CAPABILITY_AXIS_ASSESSMENT_V1"
AGI_EVIDENCE_ASSESSMENT_KIND = "AGI_EVIDENCE_ASSESSMENT_V1"


class EvidenceProtocolError(ValueError):
    """Fail-closed UCI-7 protocol error with stable machine-readable messages."""


class EvidenceAxis(str, Enum):
    NOVEL_ABSTRACTION_TRANSFER = "NOVEL_ABSTRACTION_TRANSFER"
    CROSS_DOMAIN_GENERALITY = "CROSS_DOMAIN_GENERALITY"
    TOOL_AND_ENVIRONMENT_AGENCY = "TOOL_AND_ENVIRONMENT_AGENCY"
    LONG_HORIZON_RELIABILITY = "LONG_HORIZON_RELIABILITY"
    SAFE_ADAPTATION = "SAFE_ADAPTATION"
    METACOGNITIVE_CALIBRATION = "METACOGNITIVE_CALIBRATION"


REQUIRED_EVIDENCE_AXES = (
    EvidenceAxis.NOVEL_ABSTRACTION_TRANSFER,
    EvidenceAxis.CROSS_DOMAIN_GENERALITY,
    EvidenceAxis.TOOL_AND_ENVIRONMENT_AGENCY,
    EvidenceAxis.LONG_HORIZON_RELIABILITY,
    EvidenceAxis.SAFE_ADAPTATION,
    EvidenceAxis.METACOGNITIVE_CALIBRATION,
)


class ContaminationClass(str, Enum):
    HELD_OUT = "HELD_OUT"
    PUBLIC = "PUBLIC"
    SUSPECTED = "SUSPECTED"
    EXPOSED = "EXPOSED"


class AGIEvidenceStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PARTIAL_EVIDENCE = "PARTIAL_EVIDENCE"
    PREREGISTERED_THRESHOLD_MET = "PREREGISTERED_THRESHOLD_MET"
    HYPOTHESIS_REJECTED = "HYPOTHESIS_REJECTED"


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EvidenceProtocolError(f"{name}:INVALID_SHA256")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise EvidenceProtocolError(f"{name}:INVALID_ID")


def _require_bps(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= 10_000):
        raise EvidenceProtocolError(f"{name}:INVALID_BPS")


@dataclass(frozen=True)
class CapabilityTaskSpecV1:
    task_id: str
    axis: EvidenceAxis
    domain: str
    hidden_case_commitment: str
    checker_commitment: str
    budget_commitment: str
    human_reference_commitment: str
    trial_count: int
    contamination_class: ContaminationClass
    suite_policy_commitment: str = ZERO_HASH
    task_kind: str = CAPABILITY_TASK_SPEC_KIND

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.task_kind != CAPABILITY_TASK_SPEC_KIND:
            raise EvidenceProtocolError("CAPABILITY_TASK_SPEC_KIND_MISMATCH")
        _require_id("task_id", self.task_id)
        _require_id("domain", self.domain)
        if not isinstance(self.axis, EvidenceAxis):
            raise EvidenceProtocolError("EVIDENCE_AXIS_INVALID")
        if not isinstance(self.contamination_class, ContaminationClass):
            raise EvidenceProtocolError("CONTAMINATION_CLASS_INVALID")
        for name in (
            "hidden_case_commitment",
            "checker_commitment",
            "budget_commitment",
            "human_reference_commitment",
            "suite_policy_commitment",
        ):
            _require_hash(name, getattr(self, name))
        if not isinstance(self.trial_count, int) or isinstance(self.trial_count, bool) or self.trial_count < 1:
            raise EvidenceProtocolError("TRIAL_COUNT_INVALID")

    def to_dict(self) -> dict[str, object]:
        return {
            "task_kind": self.task_kind,
            "task_id": self.task_id,
            "axis": self.axis.value,
            "domain": self.domain,
            "hidden_case_commitment": self.hidden_case_commitment,
            "checker_commitment": self.checker_commitment,
            "budget_commitment": self.budget_commitment,
            "human_reference_commitment": self.human_reference_commitment,
            "trial_count": self.trial_count,
            "contamination_class": self.contamination_class.value,
            "suite_policy_commitment": self.suite_policy_commitment,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI7_CAPABILITY_TASK_SPEC_V1", self.to_dict())


@dataclass(frozen=True)
class CapabilityTrialResultV1:
    task_spec_root: str
    trial_index: int
    checker_verdict: bool
    checker_score_bps: int
    predicted_correctness_bps: int
    output_digest: str
    checker_commitment: str
    budget_commitment: str
    provider_runtime_commitment: str
    execution_receipt_root: str
    effect_receipt_root: str
    admission_record_root: str
    result_kind: str = CAPABILITY_TRIAL_RESULT_KIND

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.result_kind != CAPABILITY_TRIAL_RESULT_KIND:
            raise EvidenceProtocolError("CAPABILITY_TRIAL_RESULT_KIND_MISMATCH")
        for name in (
            "task_spec_root",
            "output_digest",
            "checker_commitment",
            "budget_commitment",
            "provider_runtime_commitment",
            "execution_receipt_root",
            "effect_receipt_root",
            "admission_record_root",
        ):
            _require_hash(name, getattr(self, name))
        if not isinstance(self.trial_index, int) or isinstance(self.trial_index, bool) or self.trial_index < 0:
            raise EvidenceProtocolError("TRIAL_INDEX_INVALID")
        if not isinstance(self.checker_verdict, bool):
            raise EvidenceProtocolError("CHECKER_VERDICT_INVALID")
        _require_bps("checker_score_bps", self.checker_score_bps)
        _require_bps("predicted_correctness_bps", self.predicted_correctness_bps)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_spec_root": self.task_spec_root,
            "trial_index": self.trial_index,
            "checker_verdict": self.checker_verdict,
            "checker_score_bps": self.checker_score_bps,
            "predicted_correctness_bps": self.predicted_correctness_bps,
            "output_digest": self.output_digest,
            "checker_commitment": self.checker_commitment,
            "budget_commitment": self.budget_commitment,
            "provider_runtime_commitment": self.provider_runtime_commitment,
            "execution_receipt_root": self.execution_receipt_root,
            "effect_receipt_root": self.effect_receipt_root,
            "admission_record_root": self.admission_record_root,
            "result_kind": self.result_kind,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI7_CAPABILITY_TRIAL_RESULT_V1", self.to_dict())


@dataclass(frozen=True)
class EvaluationSuiteV1:
    suite_id: str
    tasks: tuple[CapabilityTaskSpecV1, ...]
    axis_threshold_bps: Mapping[EvidenceAxis, int]
    strongest_constituent_baseline_commitment: str
    evaluated_system_commitment: str
    suite_policy_commitment: str
    suite_kind: str = EVALUATION_SUITE_KIND

    @classmethod
    def create(
        cls,
        *,
        suite_id: str,
        tasks: Iterable[CapabilityTaskSpecV1],
        axis_threshold_bps: Mapping[EvidenceAxis, int],
        strongest_constituent_baseline_commitment: str,
        evaluated_system_commitment: str,
    ) -> "EvaluationSuiteV1":
        _require_id("suite_id", suite_id)
        _require_hash("strongest_constituent_baseline_commitment", strongest_constituent_baseline_commitment)
        _require_hash("evaluated_system_commitment", evaluated_system_commitment)
        task_tuple = tuple(tasks)
        if not task_tuple:
            raise EvidenceProtocolError("SUITE_TASKS_EMPTY")
        normalized_thresholds: dict[EvidenceAxis, int] = {}
        for axis, threshold in axis_threshold_bps.items():
            if not isinstance(axis, EvidenceAxis):
                raise EvidenceProtocolError("EVIDENCE_AXIS_INVALID")
            _require_bps("axis_threshold_bps", threshold)
            normalized_thresholds[axis] = threshold
        policy_payload = {
            "suite_id": suite_id,
            "axis_threshold_bps": {axis.value: normalized_thresholds[axis] for axis in sorted(normalized_thresholds, key=lambda a: a.value)},
            "strongest_constituent_baseline_commitment": strongest_constituent_baseline_commitment,
            "evaluated_system_commitment": evaluated_system_commitment,
        }
        policy_commitment = canonical_hash("AEGIS_UCI7_SUITE_POLICY_V1", policy_payload)
        bound_tasks = tuple(replace(task, suite_policy_commitment=policy_commitment) for task in task_tuple)
        suite = cls(
            suite_id=suite_id,
            tasks=bound_tasks,
            axis_threshold_bps=normalized_thresholds,
            strongest_constituent_baseline_commitment=strongest_constituent_baseline_commitment,
            evaluated_system_commitment=evaluated_system_commitment,
            suite_policy_commitment=policy_commitment,
        )
        suite.validate()
        return suite

    def validate(self) -> None:
        if self.suite_kind != EVALUATION_SUITE_KIND:
            raise EvidenceProtocolError("EVALUATION_SUITE_KIND_MISMATCH")
        _require_id("suite_id", self.suite_id)
        for name in (
            "strongest_constituent_baseline_commitment",
            "evaluated_system_commitment",
            "suite_policy_commitment",
        ):
            _require_hash(name, getattr(self, name))
        if not self.tasks:
            raise EvidenceProtocolError("SUITE_TASKS_EMPTY")
        roots: set[str] = set()
        ids: set[str] = set()
        for task in self.tasks:
            task.validate()
            if task.suite_policy_commitment != self.suite_policy_commitment:
                raise EvidenceProtocolError("TASK_SUITE_POLICY_MISMATCH")
            if task.task_id in ids or task.root in roots:
                raise EvidenceProtocolError("DUPLICATE_TASK")
            ids.add(task.task_id)
            roots.add(task.root)
        for axis, threshold in self.axis_threshold_bps.items():
            if not isinstance(axis, EvidenceAxis):
                raise EvidenceProtocolError("EVIDENCE_AXIS_INVALID")
            _require_bps("axis_threshold_bps", threshold)

    def to_dict(self) -> dict[str, object]:
        return {
            "suite_kind": self.suite_kind,
            "suite_id": self.suite_id,
            "suite_policy_commitment": self.suite_policy_commitment,
            "tasks": [task.to_dict() for task in self.tasks],
            "axis_threshold_bps": {axis.value: self.axis_threshold_bps[axis] for axis in sorted(self.axis_threshold_bps, key=lambda a: a.value)},
            "strongest_constituent_baseline_commitment": self.strongest_constituent_baseline_commitment,
            "evaluated_system_commitment": self.evaluated_system_commitment,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI7_EVALUATION_SUITE_V1", self.to_dict())


@dataclass(frozen=True)
class CapabilityAxisAssessmentV1:
    axis: EvidenceAxis
    task_count: int
    trial_count: int
    mean_score_bps: int
    mean_calibration_error_bps: int
    threshold_bps: int
    complete: bool
    threshold_met: bool
    assessment_kind: str = CAPABILITY_AXIS_ASSESSMENT_KIND


@dataclass(frozen=True)
class AGIEvidenceAssessmentV1:
    suite_root: str
    status: AGIEvidenceStatus
    axis_assessments: Mapping[EvidenceAxis, CapabilityAxisAssessmentV1]
    hidden_answer_exposure_detected: bool
    safety_invariant_violation: bool
    assessment_kind: str = AGI_EVIDENCE_ASSESSMENT_KIND

    @property
    def root(self) -> str:
        _require_hash("suite_root", self.suite_root)
        payload = {
            "assessment_kind": self.assessment_kind,
            "suite_root": self.suite_root,
            "status": self.status.value,
            "hidden_answer_exposure_detected": self.hidden_answer_exposure_detected,
            "safety_invariant_violation": self.safety_invariant_violation,
            "axis_assessments": {
                axis.value: {
                    "assessment_kind": assessment.assessment_kind,
                    "task_count": assessment.task_count,
                    "trial_count": assessment.trial_count,
                    "mean_score_bps": assessment.mean_score_bps,
                    "mean_calibration_error_bps": assessment.mean_calibration_error_bps,
                    "threshold_bps": assessment.threshold_bps,
                    "complete": assessment.complete,
                    "threshold_met": assessment.threshold_met,
                }
                for axis, assessment in sorted(self.axis_assessments.items(), key=lambda item: item[0].value)
            },
        }
        return canonical_hash("AEGIS_UCI7_AGI_EVIDENCE_ASSESSMENT_V1", payload)


class AGIEvidenceEvaluator:
    """Pure deterministic evaluator for preregistered UCI-7 evidence manifests."""

    def evaluate(
        self,
        suite: EvaluationSuiteV1,
        results: Iterable[CapabilityTrialResultV1],
        *,
        hidden_answer_exposure_detected: bool = False,
        safety_invariant_violation: bool = False,
    ) -> AGIEvidenceAssessmentV1:
        suite.validate()
        task_axes = {task.axis for task in suite.tasks}
        missing_axes = [axis for axis in REQUIRED_EVIDENCE_AXES if axis not in task_axes or axis not in suite.axis_threshold_bps]
        if missing_axes:
            raise EvidenceProtocolError("REQUIRED_AXIS_MISSING")

        result_tuple = tuple(results)
        tasks_by_root = {task.root: task for task in suite.tasks}

        # Membership is checked before cardinality so stale/post-hoc suite rebinding
        # is distinguished from an ordinary missing trial.
        for result in result_tuple:
            result.validate()
            if result.task_spec_root not in tasks_by_root:
                raise EvidenceProtocolError("TASK_NOT_IN_SUITE")

        expected_keys = {
            (task.root, trial_index)
            for task in suite.tasks
            for trial_index in range(task.trial_count)
        }
        actual_keys = {(result.task_spec_root, result.trial_index) for result in result_tuple}
        if len(result_tuple) != len(expected_keys) or actual_keys != expected_keys:
            raise EvidenceProtocolError("TRIAL_CARDINALITY_MISMATCH")

        for result in result_tuple:
            task = tasks_by_root[result.task_spec_root]
            if result.checker_commitment != task.checker_commitment:
                raise EvidenceProtocolError("CHECKER_COMMITMENT_MISMATCH")
            if result.budget_commitment != task.budget_commitment:
                raise EvidenceProtocolError("BUDGET_COMMITMENT_MISMATCH")
            if task.contamination_class is ContaminationClass.EXPOSED:
                hidden_answer_exposure_detected = True

        assessments: dict[EvidenceAxis, CapabilityAxisAssessmentV1] = {}
        for axis in REQUIRED_EVIDENCE_AXES:
            axis_tasks = tuple(task for task in suite.tasks if task.axis is axis)
            axis_roots = {task.root for task in axis_tasks}
            axis_results = tuple(result for result in result_tuple if result.task_spec_root in axis_roots)
            mean_score = sum(result.checker_score_bps for result in axis_results) // len(axis_results)
            calibration_error = 0
            if axis is EvidenceAxis.METACOGNITIVE_CALIBRATION:
                calibration_error = sum(
                    abs(result.predicted_correctness_bps - (10_000 if result.checker_verdict else 0))
                    for result in axis_results
                ) // len(axis_results)
            threshold = suite.axis_threshold_bps[axis]
            complete = len(axis_results) == sum(task.trial_count for task in axis_tasks)
            threshold_met = complete and all(result.checker_verdict for result in axis_results) and mean_score >= threshold
            assessments[axis] = CapabilityAxisAssessmentV1(
                axis=axis,
                task_count=len(axis_tasks),
                trial_count=len(axis_results),
                mean_score_bps=mean_score,
                mean_calibration_error_bps=calibration_error,
                threshold_bps=threshold,
                complete=complete,
                threshold_met=threshold_met,
            )

        if hidden_answer_exposure_detected or safety_invariant_violation:
            status = AGIEvidenceStatus.HYPOTHESIS_REJECTED
        elif all(assessment.threshold_met for assessment in assessments.values()):
            status = AGIEvidenceStatus.PREREGISTERED_THRESHOLD_MET
        elif any(result.checker_verdict for result in result_tuple):
            status = AGIEvidenceStatus.PARTIAL_EVIDENCE
        else:
            status = AGIEvidenceStatus.INSUFFICIENT_EVIDENCE

        return AGIEvidenceAssessmentV1(
            suite_root=suite.root,
            status=status,
            axis_assessments=assessments,
            hidden_answer_exposure_detected=hidden_answer_exposure_detected,
            safety_invariant_violation=safety_invariant_violation,
        )
