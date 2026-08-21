"""AEGIS bounded metacognitive executive loop.

Goal -> plan -> self-predict -> authorize -> execute -> verify -> calibrate
     -> contract autonomy / continue -> evidence receipt.

The executive is not an authority root. Planner/predictor/worker/verifier output
is evidence only. Authorization is supplied by an external authority boundary.
This layer never emits an Admission span and cannot advance the control-state
root. Metacognition may contract autonomy, never auto-expand it.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Callable, Iterable, Literal

from harness.sdk.proof_trace import (
    DECISION,
    DECISION_AUTHORITY,
    DEFERRED,
    DENIED,
    ERROR,
    EXECUTION,
    MODEL,
    NO_AUTHORITY,
    OK,
    T1,
    T2,
    VERIFIER,
    ProofTraceBundleV1,
    TraceSDK,
    digest_payload,
)
from harness.sdk.sovereign_execution import canonical_hash

AUTONOMOUS_D0_D2 = "AUTONOMOUS_D0_D2"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
AUTONOMY_MODES = {AUTONOMOUS_D0_D2, REVIEW_REQUIRED}

CONSEQUENCE_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4}
AUTHORIZATION_OUTCOMES = {"PERMIT", "DENY", "DEFER"}
AUTHORITY_BASES = {"POLICY", "OPERATOR_APPROVAL"}
WORKER_STATUSES = {"SUCCEEDED", "FAILED", "DEFERRED"}
VERDICTS = {"PASS", "FAIL", "UNVERIFIED"}
EXECUTIVE_STATUSES = {"COMPLETE", "ESCALATE", "HALT"}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")


class MetacognitiveExecutiveError(ValueError):
    """Fail-closed executive error with stable machine-readable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise MetacognitiveExecutiveError(f"{name}:INVALID_ID")


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise MetacognitiveExecutiveError(f"{name}:INVALID_SHA256")


def _require_git(name: str, value: str) -> None:
    if not isinstance(value, str) or not GIT_RE.fullmatch(value):
        raise MetacognitiveExecutiveError(f"{name}:INVALID_GIT_OBJECT")


def _require_nonnegative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MetacognitiveExecutiveError(f"{name}:INVALID_NONNEGATIVE_INTEGER")


def _require_positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise MetacognitiveExecutiveError(f"{name}:INVALID_POSITIVE_INTEGER")


def _require_hashes(name: str, values: tuple[str, ...], *, nonempty: bool = False) -> None:
    if nonempty and not values:
        raise MetacognitiveExecutiveError(f"{name}:EMPTY")
    if len(set(values)) != len(values):
        raise MetacognitiveExecutiveError(f"{name}:DUPLICATE")
    for value in values:
        _require_hash(name, value)


@dataclass(frozen=True)
class GoalEnvelopeV1:
    goal_id: str
    objective_digest: str
    source_commit: str
    policy_commitment: str
    authority_epoch: int
    pre_state_root: str
    allowed_capabilities: tuple[str, ...]
    allowed_providers: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    max_cost_microunits: int
    max_tokens: int
    max_steps: int
    consequence_ceiling: str
    deterministic_nonce: str


@dataclass(frozen=True)
class PlanStepV1:
    step_id: str
    objective_digest: str
    dependency_ids: tuple[str, ...]
    capability_id: str
    provider: str
    tool: str
    max_cost_microunits: int
    max_tokens: int
    consequence_class: str
    target_digest: str


@dataclass(frozen=True)
class PlanV1:
    goal_id: str
    steps: tuple[PlanStepV1, ...]


@dataclass(frozen=True)
class AuthorizationResultV1:
    step_id: str
    outcome: Literal["PERMIT", "DENY", "DEFER"]
    transition_id: str
    decision_receipt_root: str
    authority_basis: Literal["POLICY", "OPERATOR_APPROVAL"]


@dataclass(frozen=True)
class WorkerResultV1:
    step_id: str
    status: Literal["SUCCEEDED", "FAILED", "DEFERRED"]
    output_digest: str
    actual_cost_microunits: int
    actual_tokens: int
    evidence_roots: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedStepObservationV1:
    step_id: str
    worker_output_digest: str
    verdict: Literal["PASS", "FAIL", "UNVERIFIED"]
    evidence_roots: tuple[str, ...]
    verifier_receipt_root: str


@dataclass(frozen=True)
class ExecutiveSelfStateV1:
    autonomy_mode: str
    scored_predictions: int
    absolute_calibration_error_sum_bps: int

    @property
    def mean_absolute_calibration_error_bps(self) -> int | None:
        if self.scored_predictions == 0:
            return None
        return self.absolute_calibration_error_sum_bps // self.scored_predictions


@dataclass(frozen=True)
class MetacognitiveExecutiveReceiptV1:
    receipt_kind: Literal["METACOGNITIVE_EXECUTIVE_RECEIPT_V1"]
    goal_id: str
    objective_digest: str
    policy_commitment: str
    authority_epoch: int
    pre_state_root: str
    status: Literal["COMPLETE", "ESCALATE", "HALT"]
    completed_step_ids: tuple[str, ...]
    failed_step_id: str | None
    total_cost_microunits: int
    total_tokens: int
    mean_absolute_calibration_error_bps: int | None
    autonomy_mode: str
    trace_bundle_root: str
    authority: Literal["EVIDENCE_ONLY"]
    receipt_digest: str


@dataclass(frozen=True)
class MetacognitiveExecutiveOutcomeV1:
    receipt: MetacognitiveExecutiveReceiptV1
    trace_bundle: ProofTraceBundleV1


Planner = Callable[[GoalEnvelopeV1], PlanV1]
Predictor = Callable[[GoalEnvelopeV1, PlanStepV1, ExecutiveSelfStateV1], int]
Authorizer = Callable[[PlanStepV1], AuthorizationResultV1]
Worker = Callable[[PlanStepV1, AuthorizationResultV1], WorkerResultV1]
Verifier = Callable[[PlanStepV1, WorkerResultV1], VerifiedStepObservationV1]


def _record_causal_span(
    trace,
    *,
    name: str,
    span_kind: str,
    causal_parent_ids: Iterable[str],
    **finish_kwargs,
):
    """Respect ProofTrace's split start/finish API for causal dependencies."""
    handle = trace.start_span(
        name=name,
        span_kind=span_kind,
        causal_parent_ids=tuple(causal_parent_ids),
    )
    return trace.finish_span(handle, **finish_kwargs)


class MetacognitiveExecutive:
    """Deterministic evidence-bound executive with monotone autonomy contraction."""

    def __init__(
        self,
        *,
        planner: Planner,
        predictor: Predictor,
        authorizer: Authorizer,
        worker: Worker,
        verifier: Verifier,
        initial_autonomy_mode: str = AUTONOMOUS_D0_D2,
        calibration_error_threshold_bps: int = 2500,
    ) -> None:
        if initial_autonomy_mode not in AUTONOMY_MODES:
            raise MetacognitiveExecutiveError("AUTONOMY_MODE_UNSUPPORTED")
        if (
            isinstance(calibration_error_threshold_bps, bool)
            or not isinstance(calibration_error_threshold_bps, int)
            or not 0 <= calibration_error_threshold_bps <= 10000
        ):
            raise MetacognitiveExecutiveError("CALIBRATION_THRESHOLD_INVALID")
        self._planner = planner
        self._predictor = predictor
        self._authorizer = authorizer
        self._worker = worker
        self._verifier = verifier
        self._initial_autonomy_mode = initial_autonomy_mode
        self._calibration_error_threshold_bps = calibration_error_threshold_bps

    def run(self, goal: GoalEnvelopeV1) -> MetacognitiveExecutiveOutcomeV1:
        self._validate_goal(goal)
        trace = TraceSDK.start_trace(
            workflow_name="metacognitive-executive-v1",
            source_commit=goal.source_commit,
            policy_commitment=goal.policy_commitment,
            genesis_control_state_root=goal.pre_state_root,
            deterministic_nonce=goal.deterministic_nonce,
            group_id=goal.goal_id,
            metadata={
                "contract": "METACOGNITIVE_EXECUTIVE_V1",
                "authority": "EVIDENCE_ONLY",
                "raw_payloads": False,
            },
        )

        current_plan = self._planner(goal)
        planner_span = trace.record_span(
            name="planner",
            span_kind=MODEL,
            epistemic_tier=T2,
            input_digest=digest_payload(
                {
                    "goal_id": goal.goal_id,
                    "objective_digest": goal.objective_digest,
                    "pre_state_root": goal.pre_state_root,
                }
            ),
            output_digest=digest_payload(asdict(current_plan)),
        )
        self._validate_plan(goal, current_plan)

        self_state = ExecutiveSelfStateV1(
            autonomy_mode=self._initial_autonomy_mode,
            scored_predictions=0,
            absolute_calibration_error_sum_bps=0,
        )
        completed: list[str] = []
        total_cost = 0
        total_tokens = 0

        for current_step in current_plan.steps:
            predicted_success_bps = self._predictor(goal, current_step, self_state)
            self._validate_prediction(predicted_success_bps)
            prediction_span = _record_causal_span(
                trace,
                name=f"predict:{current_step.step_id}",
                span_kind=MODEL,
                causal_parent_ids=(planner_span.span_id,),
                epistemic_tier=T2,
                input_digest=digest_payload(
                    {
                        "step_id": current_step.step_id,
                        "autonomy_mode": self_state.autonomy_mode,
                        "scored_predictions": self_state.scored_predictions,
                    }
                ),
                output_digest=digest_payload(
                    {
                        "step_id": current_step.step_id,
                        "predicted_success_bps": predicted_success_bps,
                    }
                ),
            )

            authorization = self._authorizer(current_step)
            self._validate_authorization(current_step, authorization)
            decision_status = {"PERMIT": OK, "DENY": DENIED, "DEFER": DEFERRED}[
                authorization.outcome
            ]
            decision_span = _record_causal_span(
                trace,
                name=f"authorize:{current_step.step_id}",
                span_kind=DECISION,
                causal_parent_ids=(prediction_span.span_id,),
                status=decision_status,
                authority_class=(
                    DECISION_AUTHORITY if authorization.outcome == "PERMIT" else NO_AUTHORITY
                ),
                epistemic_tier=T1,
                transition_id=authorization.transition_id,
                input_digest=digest_payload(
                    {
                        "step_id": current_step.step_id,
                        "consequence_class": current_step.consequence_class,
                        "target_digest": current_step.target_digest,
                    }
                ),
                output_digest=digest_payload(
                    {
                        "outcome": authorization.outcome,
                        "authority_basis": authorization.authority_basis,
                    }
                ),
                receipt_roots=(authorization.decision_receipt_root,),
            )

            if authorization.outcome == "DEFER":
                self_state = self._contract_autonomy(self_state)
                return self._finish(
                    goal,
                    trace,
                    self_state,
                    "ESCALATE",
                    completed,
                    current_step.step_id,
                    total_cost,
                    total_tokens,
                )
            if authorization.outcome == "DENY":
                return self._finish(
                    goal,
                    trace,
                    self_state,
                    "HALT",
                    completed,
                    current_step.step_id,
                    total_cost,
                    total_tokens,
                )
            if (
                current_step.consequence_class == "D3"
                and authorization.authority_basis != "OPERATOR_APPROVAL"
            ):
                raise MetacognitiveExecutiveError("D3_OPERATOR_APPROVAL_REQUIRED")

            result = self._worker(current_step, authorization)
            self._validate_worker_result(current_step, result)
            new_total_cost = total_cost + result.actual_cost_microunits
            new_total_tokens = total_tokens + result.actual_tokens
            if new_total_cost > goal.max_cost_microunits:
                raise MetacognitiveExecutiveError("ACTUAL_GOAL_COST_EXCEEDED")
            if new_total_tokens > goal.max_tokens:
                raise MetacognitiveExecutiveError("ACTUAL_GOAL_TOKEN_BUDGET_EXCEEDED")
            total_cost = new_total_cost
            total_tokens = new_total_tokens

            execution_span = _record_causal_span(
                trace,
                name=f"execute:{current_step.step_id}",
                span_kind=EXECUTION,
                causal_parent_ids=(decision_span.span_id,),
                status={"SUCCEEDED": OK, "FAILED": ERROR, "DEFERRED": DEFERRED}[
                    result.status
                ],
                authority_class=NO_AUTHORITY,
                epistemic_tier=T2,
                transition_id=authorization.transition_id,
                input_digest=digest_payload(
                    {
                        "step_id": current_step.step_id,
                        "provider": current_step.provider,
                        "tool": current_step.tool,
                        "capability_id": current_step.capability_id,
                    }
                ),
                output_digest=result.output_digest,
                evidence_roots=result.evidence_roots,
            )

            observation = self._verifier(current_step, result)
            self._validate_verified_observation(current_step, result, observation)
            _record_causal_span(
                trace,
                name=f"verify:{current_step.step_id}",
                span_kind=VERIFIER,
                causal_parent_ids=(execution_span.span_id,),
                status=(OK if observation.verdict == "PASS" else ERROR),
                authority_class=NO_AUTHORITY,
                epistemic_tier=T2,
                input_digest=result.output_digest,
                output_digest=digest_payload(asdict(observation)),
                receipt_roots=(observation.verifier_receipt_root,),
                evidence_roots=observation.evidence_roots,
            )

            if observation.verdict == "UNVERIFIED":
                self_state = self._contract_autonomy(self_state)
                return self._finish(
                    goal,
                    trace,
                    self_state,
                    "ESCALATE",
                    completed,
                    current_step.step_id,
                    total_cost,
                    total_tokens,
                )

            actual_success_bps = 10000 if observation.verdict == "PASS" else 0
            absolute_error = abs(predicted_success_bps - actual_success_bps)
            self_state = ExecutiveSelfStateV1(
                autonomy_mode=self_state.autonomy_mode,
                scored_predictions=self_state.scored_predictions + 1,
                absolute_calibration_error_sum_bps=(
                    self_state.absolute_calibration_error_sum_bps + absolute_error
                ),
            )

            if observation.verdict == "FAIL":
                self_state = self._contract_autonomy(self_state)
                return self._finish(
                    goal,
                    trace,
                    self_state,
                    "HALT",
                    completed,
                    current_step.step_id,
                    total_cost,
                    total_tokens,
                )

            completed.append(current_step.step_id)
            mean_error = self_state.mean_absolute_calibration_error_bps
            if mean_error is not None and mean_error > self._calibration_error_threshold_bps:
                self_state = self._contract_autonomy(self_state)
                return self._finish(
                    goal,
                    trace,
                    self_state,
                    "ESCALATE",
                    completed,
                    None,
                    total_cost,
                    total_tokens,
                )

        return self._finish(
            goal,
            trace,
            self_state,
            "COMPLETE",
            completed,
            None,
            total_cost,
            total_tokens,
        )

    @staticmethod
    def _contract_autonomy(state: ExecutiveSelfStateV1) -> ExecutiveSelfStateV1:
        if state.autonomy_mode == REVIEW_REQUIRED:
            return state
        return ExecutiveSelfStateV1(
            autonomy_mode=REVIEW_REQUIRED,
            scored_predictions=state.scored_predictions,
            absolute_calibration_error_sum_bps=state.absolute_calibration_error_sum_bps,
        )

    @staticmethod
    def _validate_goal(goal: GoalEnvelopeV1) -> None:
        _require_id("goal_id", goal.goal_id)
        _require_hash("objective_digest", goal.objective_digest)
        _require_git("source_commit", goal.source_commit)
        _require_hash("policy_commitment", goal.policy_commitment)
        _require_nonnegative_int("authority_epoch", goal.authority_epoch)
        _require_hash("pre_state_root", goal.pre_state_root)
        _require_nonnegative_int("max_cost_microunits", goal.max_cost_microunits)
        _require_nonnegative_int("max_tokens", goal.max_tokens)
        _require_positive_int("max_steps", goal.max_steps)
        if goal.consequence_ceiling not in CONSEQUENCE_ORDER:
            raise MetacognitiveExecutiveError("GOAL_CONSEQUENCE_CEILING_UNSUPPORTED")
        _require_id("deterministic_nonce", goal.deterministic_nonce)
        for name, values in (
            ("allowed_capabilities", goal.allowed_capabilities),
            ("allowed_providers", goal.allowed_providers),
            ("allowed_tools", goal.allowed_tools),
        ):
            if not values or len(set(values)) != len(values):
                raise MetacognitiveExecutiveError(f"{name}:EMPTY_OR_DUPLICATE")
            for value in values:
                _require_id(name, value)

    @staticmethod
    def _validate_plan(goal: GoalEnvelopeV1, current_plan: PlanV1) -> None:
        if current_plan.goal_id != goal.goal_id:
            raise MetacognitiveExecutiveError("PLAN_GOAL_BINDING_MISMATCH")
        if len(current_plan.steps) > goal.max_steps:
            raise MetacognitiveExecutiveError("PLAN_STEP_LIMIT_EXCEEDED")

        all_ids = {current_step.step_id for current_step in current_plan.steps}
        if len(all_ids) != len(current_plan.steps):
            raise MetacognitiveExecutiveError("PLAN_STEP_ID_DUPLICATE")
        seen: set[str] = set()
        reserved_cost = 0
        reserved_tokens = 0
        for current_step in current_plan.steps:
            _require_id("step_id", current_step.step_id)
            _require_hash("step_objective_digest", current_step.objective_digest)
            if current_step.objective_digest != goal.objective_digest:
                raise MetacognitiveExecutiveError("PLAN_OBJECTIVE_BINDING_MISMATCH")
            _require_id("capability_id", current_step.capability_id)
            _require_id("provider", current_step.provider)
            _require_id("tool", current_step.tool)
            _require_hash("target_digest", current_step.target_digest)
            _require_nonnegative_int("step_max_cost_microunits", current_step.max_cost_microunits)
            _require_nonnegative_int("step_max_tokens", current_step.max_tokens)
            if current_step.consequence_class not in CONSEQUENCE_ORDER:
                raise MetacognitiveExecutiveError("PLAN_CONSEQUENCE_CLASS_UNSUPPORTED")
            if current_step.consequence_class == "D4":
                raise MetacognitiveExecutiveError("D4_EXECUTION_FORBIDDEN")
            if (
                CONSEQUENCE_ORDER[current_step.consequence_class]
                > CONSEQUENCE_ORDER[goal.consequence_ceiling]
            ):
                raise MetacognitiveExecutiveError("PLAN_CONSEQUENCE_CEILING_EXCEEDED")
            if current_step.capability_id not in goal.allowed_capabilities:
                raise MetacognitiveExecutiveError("PLAN_CAPABILITY_NOT_ALLOWED")
            if current_step.provider not in goal.allowed_providers:
                raise MetacognitiveExecutiveError("PLAN_PROVIDER_NOT_ALLOWED")
            if current_step.tool not in goal.allowed_tools:
                raise MetacognitiveExecutiveError("PLAN_TOOL_NOT_ALLOWED")
            for dependency_id in current_step.dependency_ids:
                _require_id("dependency_id", dependency_id)
                if dependency_id == current_step.step_id:
                    raise MetacognitiveExecutiveError("PLAN_DEPENDENCY_SELF_REFERENCE")
                if dependency_id not in all_ids:
                    raise MetacognitiveExecutiveError("PLAN_DEPENDENCY_UNKNOWN")
                if dependency_id not in seen:
                    raise MetacognitiveExecutiveError("PLAN_NOT_TOPOLOGICALLY_ORDERED")
            reserved_cost += current_step.max_cost_microunits
            reserved_tokens += current_step.max_tokens
            if reserved_cost > goal.max_cost_microunits:
                raise MetacognitiveExecutiveError("PLAN_COST_BUDGET_EXCEEDED")
            if reserved_tokens > goal.max_tokens:
                raise MetacognitiveExecutiveError("PLAN_TOKEN_BUDGET_EXCEEDED")
            seen.add(current_step.step_id)

    @staticmethod
    def _validate_prediction(predicted_success_bps: int) -> None:
        if (
            isinstance(predicted_success_bps, bool)
            or not isinstance(predicted_success_bps, int)
            or not 0 <= predicted_success_bps <= 10000
        ):
            raise MetacognitiveExecutiveError("PREDICTED_SUCCESS_BPS_INVALID")

    @staticmethod
    def _validate_authorization(
        current_step: PlanStepV1,
        authorization: AuthorizationResultV1,
    ) -> None:
        if authorization.step_id != current_step.step_id:
            raise MetacognitiveExecutiveError("AUTHORIZATION_STEP_BINDING_MISMATCH")
        if authorization.outcome not in AUTHORIZATION_OUTCOMES:
            raise MetacognitiveExecutiveError("AUTHORIZATION_OUTCOME_UNSUPPORTED")
        _require_hash("transition_id", authorization.transition_id)
        _require_hash("decision_receipt_root", authorization.decision_receipt_root)
        if authorization.authority_basis not in AUTHORITY_BASES:
            raise MetacognitiveExecutiveError("AUTHORIZATION_BASIS_UNSUPPORTED")

    @staticmethod
    def _validate_worker_result(current_step: PlanStepV1, result: WorkerResultV1) -> None:
        if result.step_id != current_step.step_id:
            raise MetacognitiveExecutiveError("WORKER_STEP_BINDING_MISMATCH")
        if result.status not in WORKER_STATUSES:
            raise MetacognitiveExecutiveError("WORKER_STATUS_UNSUPPORTED")
        _require_hash("worker_output_digest", result.output_digest)
        _require_nonnegative_int("actual_cost_microunits", result.actual_cost_microunits)
        _require_nonnegative_int("actual_tokens", result.actual_tokens)
        if result.actual_cost_microunits > current_step.max_cost_microunits:
            raise MetacognitiveExecutiveError("ACTUAL_STEP_COST_EXCEEDED")
        if result.actual_tokens > current_step.max_tokens:
            raise MetacognitiveExecutiveError("ACTUAL_STEP_TOKEN_BUDGET_EXCEEDED")
        _require_hashes("worker_evidence_root", result.evidence_roots, nonempty=True)

    @staticmethod
    def _validate_verified_observation(
        current_step: PlanStepV1,
        result: WorkerResultV1,
        observation: VerifiedStepObservationV1,
    ) -> None:
        if observation.step_id != current_step.step_id:
            raise MetacognitiveExecutiveError("VERIFIER_STEP_BINDING_MISMATCH")
        if observation.worker_output_digest != result.output_digest:
            raise MetacognitiveExecutiveError("VERIFIER_OUTPUT_BINDING_MISMATCH")
        if observation.verdict not in VERDICTS:
            raise MetacognitiveExecutiveError("VERIFIER_VERDICT_UNSUPPORTED")
        _require_hash("verifier_receipt_root", observation.verifier_receipt_root)
        _require_hashes("verifier_evidence_root", observation.evidence_roots, nonempty=True)

    @staticmethod
    def _finish(
        goal: GoalEnvelopeV1,
        trace,
        self_state: ExecutiveSelfStateV1,
        status: str,
        completed: list[str],
        failed_step_id: str | None,
        total_cost: int,
        total_tokens: int,
    ) -> MetacognitiveExecutiveOutcomeV1:
        if status not in EXECUTIVE_STATUSES:
            raise MetacognitiveExecutiveError("EXECUTIVE_STATUS_UNSUPPORTED")
        trace_bundle = trace.close()
        body = {
            "receipt_kind": "METACOGNITIVE_EXECUTIVE_RECEIPT_V1",
            "goal_id": goal.goal_id,
            "objective_digest": goal.objective_digest,
            "policy_commitment": goal.policy_commitment,
            "authority_epoch": goal.authority_epoch,
            "pre_state_root": goal.pre_state_root,
            "status": status,
            "completed_step_ids": list(completed),
            "failed_step_id": failed_step_id,
            "total_cost_microunits": total_cost,
            "total_tokens": total_tokens,
            "mean_absolute_calibration_error_bps": self_state.mean_absolute_calibration_error_bps,
            "autonomy_mode": self_state.autonomy_mode,
            "trace_bundle_root": trace_bundle.root,
            "authority": "EVIDENCE_ONLY",
        }
        receipt_digest = canonical_hash("AEGIS_METACOGNITIVE_EXECUTIVE_RECEIPT_V1", body)
        receipt = MetacognitiveExecutiveReceiptV1(
            receipt_kind="METACOGNITIVE_EXECUTIVE_RECEIPT_V1",
            goal_id=goal.goal_id,
            objective_digest=goal.objective_digest,
            policy_commitment=goal.policy_commitment,
            authority_epoch=goal.authority_epoch,
            pre_state_root=goal.pre_state_root,
            status=status,  # type: ignore[arg-type]
            completed_step_ids=tuple(completed),
            failed_step_id=failed_step_id,
            total_cost_microunits=total_cost,
            total_tokens=total_tokens,
            mean_absolute_calibration_error_bps=self_state.mean_absolute_calibration_error_bps,
            autonomy_mode=self_state.autonomy_mode,
            trace_bundle_root=trace_bundle.root,
            authority="EVIDENCE_ONLY",
            receipt_digest=receipt_digest,
        )
        return MetacognitiveExecutiveOutcomeV1(receipt=receipt, trace_bundle=trace_bundle)
