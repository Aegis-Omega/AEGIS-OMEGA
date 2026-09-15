from __future__ import annotations

from dataclasses import replace

import pytest

from harness.sdk.metacognitive_executive import (
    AUTONOMOUS_D0_D2,
    REVIEW_REQUIRED,
    AuthorizationResultV1,
    GoalEnvelopeV1,
    MetacognitiveExecutive,
    MetacognitiveExecutiveError,
    PlanStepV1,
    PlanV1,
    VerifiedStepObservationV1,
    WorkerResultV1,
)
from harness.sdk.proof_trace import (
    DECISION,
    EXECUTION,
    MODEL,
    VERIFIER,
    verify_trace_bundle,
)

COMMIT = "a" * 40
POLICY = "b" * 64
STATE = "c" * 64
OBJECTIVE = "d" * 64
TARGET = "e" * 64
TRANSITION = "1" * 64
DECISION_RECEIPT = "2" * 64
OUTPUT = "3" * 64
EVIDENCE = "4" * 64
VERIFIER_RECEIPT = "5" * 64


def goal(**overrides):
    base = dict(
        goal_id="goal-1",
        objective_digest=OBJECTIVE,
        source_commit=COMMIT,
        policy_commitment=POLICY,
        authority_epoch=7,
        pre_state_root=STATE,
        allowed_capabilities=("research", "code"),
        allowed_providers=("openai", "anthropic"),
        allowed_tools=("web", "repo"),
        max_cost_microunits=1000,
        max_tokens=5000,
        max_steps=4,
        consequence_ceiling="D2",
        deterministic_nonce="goal-1-run-1",
    )
    base.update(overrides)
    return GoalEnvelopeV1(**base)


def step(
    step_id: str = "s1",
    *,
    dependencies=(),
    capability="research",
    provider="openai",
    tool="web",
    cost=100,
    tokens=500,
    consequence="D1",
):
    return PlanStepV1(
        step_id=step_id,
        objective_digest=OBJECTIVE,
        dependency_ids=tuple(dependencies),
        capability_id=capability,
        provider=provider,
        tool=tool,
        max_cost_microunits=cost,
        max_tokens=tokens,
        consequence_class=consequence,
        target_digest=TARGET,
    )


def plan(*steps):
    return PlanV1(goal_id="goal-1", steps=tuple(steps))


def permit(current_step: PlanStepV1, *, basis="POLICY"):
    return AuthorizationResultV1(
        step_id=current_step.step_id,
        outcome="PERMIT",
        transition_id=TRANSITION,
        decision_receipt_root=DECISION_RECEIPT,
        authority_basis=basis,
    )


def worker_success(current_step: PlanStepV1, _authorization: AuthorizationResultV1):
    return WorkerResultV1(
        step_id=current_step.step_id,
        status="SUCCEEDED",
        output_digest=OUTPUT,
        actual_cost_microunits=50,
        actual_tokens=250,
        evidence_roots=(EVIDENCE,),
    )


def verify_pass(current_step: PlanStepV1, result: WorkerResultV1):
    return VerifiedStepObservationV1(
        step_id=current_step.step_id,
        worker_output_digest=result.output_digest,
        verdict="PASS",
        evidence_roots=result.evidence_roots,
        verifier_receipt_root=VERIFIER_RECEIPT,
    )


def executive(
    current_plan: PlanV1,
    *,
    authorizer=permit,
    worker=worker_success,
    verifier=verify_pass,
    predictor=lambda _goal, _step, _state: 9000,
    initial_autonomy_mode=AUTONOMOUS_D0_D2,
    threshold=2500,
):
    return MetacognitiveExecutive(
        planner=lambda _goal: current_plan,
        predictor=predictor,
        authorizer=authorizer,
        worker=worker,
        verifier=verifier,
        initial_autonomy_mode=initial_autonomy_mode,
        calibration_error_threshold_bps=threshold,
    )


def test_successful_goal_runs_plan_authorize_execute_verify_and_closes_trace():
    runner = executive(plan(step("s1"), step("s2", dependencies=("s1",), tool="repo")))

    outcome = runner.run(goal())

    assert outcome.receipt.status == "COMPLETE"
    assert outcome.receipt.completed_step_ids == ("s1", "s2")
    assert outcome.receipt.failed_step_id is None
    assert outcome.receipt.authority == "EVIDENCE_ONLY"
    assert outcome.trace_bundle.final_control_state_root == STATE
    assert verify_trace_bundle(outcome.trace_bundle).valid is True

    kinds = [span.span_kind for span in outcome.trace_bundle.spans]
    assert kinds.count(MODEL) >= 3  # planner + one prediction per step
    assert kinds.count(DECISION) == 2
    assert kinds.count(EXECUTION) == 2
    assert kinds.count(VERIFIER) == 2


def test_planner_cannot_expand_provider_tool_capability_or_reserved_budget():
    cases = [
        (plan(step(provider="gemini")), "PLAN_PROVIDER_NOT_ALLOWED"),
        (plan(step(tool="shell")), "PLAN_TOOL_NOT_ALLOWED"),
        (plan(step(capability="deploy")), "PLAN_CAPABILITY_NOT_ALLOWED"),
        (plan(step(cost=1001)), "PLAN_COST_BUDGET_EXCEEDED"),
        (plan(step(tokens=5001)), "PLAN_TOKEN_BUDGET_EXCEEDED"),
    ]

    for current_plan, code in cases:
        with pytest.raises(MetacognitiveExecutiveError) as exc:
            executive(current_plan).run(goal())
        assert exc.value.code == code


def test_d4_is_always_denied_even_if_goal_ceiling_is_d4():
    with pytest.raises(MetacognitiveExecutiveError) as exc:
        executive(plan(step(consequence="D4"))).run(goal(consequence_ceiling="D4"))
    assert exc.value.code == "D4_EXECUTION_FORBIDDEN"


def test_d3_requires_operator_approval_authority_basis():
    d3_goal = goal(consequence_ceiling="D3")
    d3_plan = plan(step(consequence="D3"))

    with pytest.raises(MetacognitiveExecutiveError) as exc:
        executive(d3_plan, authorizer=lambda s: permit(s, basis="POLICY")).run(d3_goal)
    assert exc.value.code == "D3_OPERATOR_APPROVAL_REQUIRED"

    approved = executive(
        d3_plan,
        authorizer=lambda s: permit(s, basis="OPERATOR_APPROVAL"),
    ).run(d3_goal)
    assert approved.receipt.status == "COMPLETE"


def test_defer_never_executes_worker_and_returns_escalation():
    calls = {"worker": 0}

    def defer(current_step: PlanStepV1):
        return AuthorizationResultV1(
            step_id=current_step.step_id,
            outcome="DEFER",
            transition_id=TRANSITION,
            decision_receipt_root=DECISION_RECEIPT,
            authority_basis="POLICY",
        )

    def forbidden_worker(current_step, authorization):
        calls["worker"] += 1
        return worker_success(current_step, authorization)

    outcome = executive(plan(step()), authorizer=defer, worker=forbidden_worker).run(goal())

    assert calls["worker"] == 0
    assert outcome.receipt.status == "ESCALATE"
    assert outcome.receipt.failed_step_id == "s1"
    assert outcome.trace_bundle.final_control_state_root == STATE


def test_unverified_outcome_escalates_and_never_advances_control_state():
    def unverified(current_step: PlanStepV1, result: WorkerResultV1):
        return VerifiedStepObservationV1(
            step_id=current_step.step_id,
            worker_output_digest=result.output_digest,
            verdict="UNVERIFIED",
            evidence_roots=result.evidence_roots,
            verifier_receipt_root=VERIFIER_RECEIPT,
        )

    outcome = executive(plan(step()), verifier=unverified).run(goal())

    assert outcome.receipt.status == "ESCALATE"
    assert outcome.receipt.autonomy_mode == REVIEW_REQUIRED
    assert outcome.trace_bundle.final_control_state_root == STATE


def test_large_prediction_error_contracts_autonomy_instead_of_expanding_it():
    outcome = executive(
        plan(step()),
        predictor=lambda _goal, _step, _state: 0,
        threshold=2500,
    ).run(goal())

    assert outcome.receipt.status == "ESCALATE"
    assert outcome.receipt.mean_absolute_calibration_error_bps == 10000
    assert outcome.receipt.autonomy_mode == REVIEW_REQUIRED


def test_perfect_calibration_cannot_auto_expand_review_required_mode():
    outcome = executive(
        plan(step()),
        predictor=lambda _goal, _step, _state: 10000,
        initial_autonomy_mode=REVIEW_REQUIRED,
        threshold=2500,
    ).run(goal())

    assert outcome.receipt.status == "COMPLETE"
    assert outcome.receipt.mean_absolute_calibration_error_bps == 0
    assert outcome.receipt.autonomy_mode == REVIEW_REQUIRED


def test_actual_worker_budget_overrun_fails_closed():
    def expensive(current_step: PlanStepV1, _authorization: AuthorizationResultV1):
        return replace(
            worker_success(current_step, _authorization),
            actual_cost_microunits=current_step.max_cost_microunits + 1,
        )

    with pytest.raises(MetacognitiveExecutiveError) as exc:
        executive(plan(step()), worker=expensive).run(goal())
    assert exc.value.code == "ACTUAL_STEP_COST_EXCEEDED"


def test_plan_dependencies_must_be_closed_and_topologically_ordered():
    with pytest.raises(MetacognitiveExecutiveError) as missing:
        executive(plan(step("s1", dependencies=("missing",)))).run(goal())
    assert missing.value.code == "PLAN_DEPENDENCY_UNKNOWN"

    with pytest.raises(MetacognitiveExecutiveError) as forward:
        executive(plan(step("s2", dependencies=("s1",)), step("s1"))).run(goal())
    assert forward.value.code == "PLAN_NOT_TOPOLOGICALLY_ORDERED"


def test_same_bound_inputs_replay_to_identical_receipt_and_trace_root():
    current_plan = plan(step("s1"), step("s2", dependencies=("s1",), tool="repo"))
    first = executive(current_plan).run(goal())
    second = executive(current_plan).run(goal())

    assert first.receipt.receipt_digest == second.receipt.receipt_digest
    assert first.trace_bundle.root == second.trace_bundle.root
