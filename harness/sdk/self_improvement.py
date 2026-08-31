"""AEGIS bounded self-improvement evidence verifier v1.

This module verifies preregistered capability-improvement experiments. It is an
evidence kernel only: successful receipts carry ``authority_class == "NONE"``
and cannot grant execution, admission, merge, deployment, or canonical authority.

All verification-bound metric values are integer micro-units. Deterministic roots
use the repository-local domain-separated ``canonical_hash`` primitive.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Protocol

from harness.sdk.sovereign_execution import canonical_hash

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

NO_AUTHORITY = "NONE"
PASS = "PASS"
DENIED = "FAIL_IMPROVEMENT_DENIED"

DOM_HYPOTHESIS = "AEGIS_IMPROVEMENT_HYPOTHESIS_V1"
DOM_CONTRACT = "AEGIS_IMPROVEMENT_CONTRACT_V1"
DOM_CANDIDATE = "AEGIS_IMPROVEMENT_CANDIDATE_V1"
DOM_EVALUATION = "AEGIS_IMPROVEMENT_EVALUATION_V1"
DOM_VERIFICATION = "AEGIS_IMPROVEMENT_VERIFICATION_V1"
DOM_RECEIPT = "AEGIS_IMPROVEMENT_RECEIPT_V1"


class ImprovementError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ImprovementError(f"{name}:MALFORMED_ROOT")


def require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ImprovementError(f"{name}:INVALID_ID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ImprovementError(f"{name}:CONTROL_CHARACTER")


def require_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ImprovementError(f"{name}:INTEGER_REQUIRED")


def _require_unique(name: str, values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        raise ImprovementError(f"{name}:DUPLICATE")


class MetricDirection(str, Enum):
    MAXIMIZE = "MAXIMIZE"
    MINIMIZE = "MINIMIZE"


@dataclass(frozen=True)
class MetricRuleV1:
    metric_id: str
    direction: MetricDirection
    minimum_improvement_micros: int

    def __post_init__(self) -> None:
        require_id("metric_id", self.metric_id)
        require_int("minimum_improvement_micros", self.minimum_improvement_micros)
        if self.minimum_improvement_micros < 0:
            raise ImprovementError("minimum_improvement_micros:NEGATIVE")


@dataclass(frozen=True)
class MetricObservationV1:
    metric_id: str
    value_micros: int

    def __post_init__(self) -> None:
        require_id("metric_id", self.metric_id)
        require_int("value_micros", self.value_micros)


@dataclass(frozen=True)
class HypothesisEnvelopeV1:
    hypothesis_id: str
    baseline_artifact_root: str
    proposal_root: str
    search_policy_root: str
    declared_objective_root: str
    schema_version: str = "aegis.improvement-hypothesis.v1"

    def __post_init__(self) -> None:
        require_id("hypothesis_id", self.hypothesis_id)
        for name in (
            "baseline_artifact_root",
            "proposal_root",
            "search_policy_root",
            "declared_objective_root",
        ):
            require_hash(name, getattr(self, name))

    @property
    def root(self) -> str:
        return canonical_hash(DOM_HYPOTHESIS, asdict(self))


@dataclass(frozen=True)
class ExperimentContractV1:
    experiment_id: str
    hypothesis_root: str
    baseline_artifact_root: str
    evaluation_input_root: str
    withheld_labels_root: str
    environment_root: str
    evaluator_root: str
    evaluator_policy_root: str
    verifier_root: str
    policy_root: str
    max_trials: int
    metric_rules: tuple[MetricRuleV1, ...]
    schema_version: str = "aegis.improvement-contract.v1"

    def __post_init__(self) -> None:
        require_id("experiment_id", self.experiment_id)
        for name in (
            "hypothesis_root",
            "baseline_artifact_root",
            "evaluation_input_root",
            "withheld_labels_root",
            "environment_root",
            "evaluator_root",
            "evaluator_policy_root",
            "verifier_root",
            "policy_root",
        ):
            require_hash(name, getattr(self, name))
        require_int("max_trials", self.max_trials)
        if self.max_trials <= 0:
            raise ImprovementError("max_trials:NON_POSITIVE")
        if not self.metric_rules:
            raise ImprovementError("metric_rules:EMPTY")
        metric_ids = tuple(rule.metric_id for rule in self.metric_rules)
        _require_unique("metric_rules", metric_ids)

    @property
    def root(self) -> str:
        data = asdict(self)
        data["metric_rules"] = [
            {
                "metric_id": rule.metric_id,
                "direction": rule.direction.value,
                "minimum_improvement_micros": rule.minimum_improvement_micros,
            }
            for rule in sorted(self.metric_rules, key=lambda item: item.metric_id)
        ]
        return canonical_hash(DOM_CONTRACT, data)


@dataclass(frozen=True)
class CandidateObservationV1:
    experiment_contract_root: str
    hypothesis_root: str
    baseline_artifact_root: str
    candidate_artifact_root: str
    trial_index: int
    builder_root: str
    environment_root: str
    accessed_roots: tuple[str, ...]
    schema_version: str = "aegis.improvement-candidate-observation.v1"

    def __post_init__(self) -> None:
        for name in (
            "experiment_contract_root",
            "hypothesis_root",
            "baseline_artifact_root",
            "candidate_artifact_root",
            "builder_root",
            "environment_root",
        ):
            require_hash(name, getattr(self, name))
        require_int("trial_index", self.trial_index)
        if self.trial_index < 0:
            raise ImprovementError("trial_index:NEGATIVE")
        for root in self.accessed_roots:
            require_hash("accessed_root", root)
        _require_unique("accessed_roots", self.accessed_roots)

    @property
    def root(self) -> str:
        data = asdict(self)
        data["accessed_roots"] = sorted(self.accessed_roots)
        return canonical_hash(DOM_CANDIDATE, data)


@dataclass(frozen=True)
class EvaluationReceiptV1:
    experiment_contract_root: str
    baseline_artifact_root: str
    candidate_artifact_root: str
    evaluation_input_root: str
    environment_root: str
    evaluator_root: str
    evaluator_policy_root: str
    observed_candidate_access_roots: tuple[str, ...]
    baseline_metrics: tuple[MetricObservationV1, ...]
    candidate_metrics: tuple[MetricObservationV1, ...]
    contamination_detected: bool
    status: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.improvement-evaluation-receipt.v1"

    def __post_init__(self) -> None:
        for name in (
            "experiment_contract_root",
            "baseline_artifact_root",
            "candidate_artifact_root",
            "evaluation_input_root",
            "environment_root",
            "evaluator_root",
            "evaluator_policy_root",
        ):
            require_hash(name, getattr(self, name))
        for root in self.observed_candidate_access_roots:
            require_hash("observed_candidate_access_root", root)
        _require_unique(
            "observed_candidate_access_roots",
            self.observed_candidate_access_roots,
        )
        if not isinstance(self.contamination_detected, bool):
            raise ImprovementError("contamination_detected:BOOLEAN_REQUIRED")
        require_id("status", self.status)
        if not self.baseline_metrics or not self.candidate_metrics:
            raise ImprovementError("evaluation_metrics:EMPTY")
        _require_unique(
            "baseline_metrics",
            tuple(observation.metric_id for observation in self.baseline_metrics),
        )
        _require_unique(
            "candidate_metrics",
            tuple(observation.metric_id for observation in self.candidate_metrics),
        )

    @property
    def root(self) -> str:
        data = asdict(self)
        data["observed_candidate_access_roots"] = sorted(
            self.observed_candidate_access_roots
        )
        data["baseline_metrics"] = [
            asdict(item) for item in sorted(self.baseline_metrics, key=lambda item: item.metric_id)
        ]
        data["candidate_metrics"] = [
            asdict(item) for item in sorted(self.candidate_metrics, key=lambda item: item.metric_id)
        ]
        return canonical_hash(DOM_EVALUATION, data)


class TrustedEvaluationReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> EvaluationReceiptV1 | None: ...


@dataclass(frozen=True)
class ImprovementVerificationResultV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None

    def __post_init__(self) -> None:
        if self.status not in {PASS, DENIED}:
            raise ImprovementError("verification_status:INVALID")
        if self.verification_root is not None:
            require_hash("verification_root", self.verification_root)


@dataclass(frozen=True)
class ImprovementReceiptV1:
    hypothesis_root: str
    experiment_contract_root: str
    candidate_observation_root: str
    evaluation_receipt_root: str
    baseline_artifact_root: str
    candidate_artifact_root: str
    metric_improvements_micros: tuple[tuple[str, int], ...]
    verifier_root: str
    policy_root: str
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.improvement-receipt.v1"

    def __post_init__(self) -> None:
        for name in (
            "hypothesis_root",
            "experiment_contract_root",
            "candidate_observation_root",
            "evaluation_receipt_root",
            "baseline_artifact_root",
            "candidate_artifact_root",
            "verifier_root",
            "policy_root",
            "verification_root",
        ):
            require_hash(name, getattr(self, name))
        metric_ids: list[str] = []
        for metric_id, value in self.metric_improvements_micros:
            require_id("metric_id", metric_id)
            require_int("metric_improvement_micros", value)
            metric_ids.append(metric_id)
        _require_unique("metric_improvements_micros", tuple(metric_ids))
        if self.metric_improvements_micros != tuple(
            sorted(self.metric_improvements_micros, key=lambda item: item[0])
        ):
            raise ImprovementError("metric_improvements_micros:NONCANONICAL_ORDER")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["metric_improvements_micros"] = [
            [metric_id, value] for metric_id, value in self.metric_improvements_micros
        ]
        return canonical_hash(DOM_RECEIPT, data)


class ImprovementVerifierV1:
    def __init__(
        self,
        *,
        verifier_root: str,
        policy_root: str,
        evaluation_store: TrustedEvaluationReceiptStore,
    ) -> None:
        require_hash("verifier_root", verifier_root)
        require_hash("policy_root", policy_root)
        self.verifier_root = verifier_root
        self.policy_root = policy_root
        self.evaluation_store = evaluation_store

    @staticmethod
    def _deny(errors: list[str]) -> tuple[ImprovementVerificationResultV1, None]:
        return (
            ImprovementVerificationResultV1(
                DENIED,
                tuple(sorted(set(errors))),
                None,
            ),
            None,
        )

    def verify_and_issue(
        self,
        *,
        hypothesis: HypothesisEnvelopeV1,
        contract: ExperimentContractV1,
        candidate: CandidateObservationV1,
        evaluation_receipt_root: str,
    ) -> tuple[ImprovementVerificationResultV1, ImprovementReceiptV1 | None]:
        require_hash("evaluation_receipt_root", evaluation_receipt_root)
        errors: list[str] = []

        if contract.verifier_root != self.verifier_root:
            errors.append("VERIFIER_BINDING_FAILURE")
        if contract.policy_root != self.policy_root:
            errors.append("POLICY_BINDING_FAILURE")

        if (
            contract.hypothesis_root != hypothesis.root
            or contract.baseline_artifact_root != hypothesis.baseline_artifact_root
        ):
            errors.append("HYPOTHESIS_BINDING_FAILURE")

        if (
            candidate.experiment_contract_root != contract.root
            or candidate.hypothesis_root != hypothesis.root
            or candidate.baseline_artifact_root != contract.baseline_artifact_root
        ):
            errors.append("CANDIDATE_BINDING_FAILURE")
        if candidate.environment_root != contract.environment_root:
            errors.append("CANDIDATE_ENVIRONMENT_MISMATCH")
        if not 0 <= candidate.trial_index < contract.max_trials:
            errors.append("TRIAL_BOUND_FAILURE")
        if contract.withheld_labels_root in candidate.accessed_roots:
            errors.append("WITHHELD_LABEL_ACCESS_DETECTED")

        evaluation = self.evaluation_store.fetch_verified(evaluation_receipt_root)
        if evaluation is None or evaluation.root != evaluation_receipt_root:
            errors.append("EVALUATION_RECEIPT_UNTRUSTED")
            return self._deny(errors)

        if (
            evaluation.experiment_contract_root != contract.root
            or evaluation.baseline_artifact_root != contract.baseline_artifact_root
            or evaluation.candidate_artifact_root != candidate.candidate_artifact_root
            or evaluation.evaluation_input_root != contract.evaluation_input_root
            or evaluation.environment_root != contract.environment_root
        ):
            errors.append("EVALUATION_BINDING_FAILURE")
        if evaluation.evaluator_root != contract.evaluator_root:
            errors.append("EVALUATOR_BINDING_FAILURE")
        if evaluation.evaluator_policy_root != contract.evaluator_policy_root:
            errors.append("EVALUATOR_POLICY_BINDING_FAILURE")

        candidate_access = tuple(sorted(candidate.accessed_roots))
        independently_observed_access = tuple(
            sorted(evaluation.observed_candidate_access_roots)
        )
        if candidate_access != independently_observed_access:
            errors.append("ACCESS_OBSERVATION_BINDING_FAILURE")
        if contract.withheld_labels_root in evaluation.observed_candidate_access_roots:
            errors.append("WITHHELD_LABEL_ACCESS_DETECTED")

        if evaluation.contamination_detected:
            errors.append("EVALUATION_CONTAMINATION_DETECTED")
        if evaluation.status != PASS:
            errors.append("EVALUATION_STATUS_FAILURE")

        rules = {rule.metric_id: rule for rule in contract.metric_rules}
        baseline_metrics = {
            observation.metric_id: observation.value_micros
            for observation in evaluation.baseline_metrics
        }
        candidate_metrics = {
            observation.metric_id: observation.value_micros
            for observation in evaluation.candidate_metrics
        }
        expected_metric_ids = set(rules)
        if set(baseline_metrics) != expected_metric_ids or set(candidate_metrics) != expected_metric_ids:
            errors.append("METRIC_SET_MISMATCH")
            metric_improvements: tuple[tuple[str, int], ...] = ()
        else:
            deltas: list[tuple[str, int]] = []
            for metric_id in sorted(expected_metric_ids):
                rule = rules[metric_id]
                baseline_value = baseline_metrics[metric_id]
                candidate_value = candidate_metrics[metric_id]
                if rule.direction == MetricDirection.MAXIMIZE:
                    delta = candidate_value - baseline_value
                else:
                    delta = baseline_value - candidate_value
                deltas.append((metric_id, delta))
                if delta < rule.minimum_improvement_micros:
                    errors.append("METRIC_THRESHOLD_FAILURE")
            metric_improvements = tuple(deltas)

        if errors:
            return self._deny(errors)

        verification_root = canonical_hash(
            DOM_VERIFICATION,
            {
                "hypothesis_root": hypothesis.root,
                "experiment_contract_root": contract.root,
                "candidate_observation_root": candidate.root,
                "evaluation_receipt_root": evaluation.root,
                "baseline_artifact_root": contract.baseline_artifact_root,
                "candidate_artifact_root": candidate.candidate_artifact_root,
                "metric_improvements_micros": [
                    [metric_id, value] for metric_id, value in metric_improvements
                ],
                "verifier_root": self.verifier_root,
                "policy_root": self.policy_root,
                "status": PASS,
                "error_codes": [],
            },
        )
        receipt = ImprovementReceiptV1(
            hypothesis_root=hypothesis.root,
            experiment_contract_root=contract.root,
            candidate_observation_root=candidate.root,
            evaluation_receipt_root=evaluation.root,
            baseline_artifact_root=contract.baseline_artifact_root,
            candidate_artifact_root=candidate.candidate_artifact_root,
            metric_improvements_micros=metric_improvements,
            verifier_root=self.verifier_root,
            policy_root=self.policy_root,
            verification_root=verification_root,
        )
        return ImprovementVerificationResultV1(PASS, (), verification_root), receipt
