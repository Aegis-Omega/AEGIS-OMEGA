from __future__ import annotations

from dataclasses import asdict

import pytest

from harness.sdk.company_brain import (
    CompanyBrain,
    CompanyBrainError,
    CompanyGoalRequestV1,
    CompanyPolicyV1,
)
from harness.sdk.metacognitive_executive import (
    AuthorizationResultV1,
    MetacognitiveExecutive,
    MetacognitiveExecutiveError,
    PlanStepV1,
    PlanV1,
    VerifiedStepObservationV1,
    WorkerResultV1,
)

COMMIT = "a" * 40
POLICY = "b" * 64
STATE = "c" * 64
TARGET = "d" * 64
TRANSITION = "1" * 64
DECISION_RECEIPT = "2" * 64
OUTPUT = "3" * 64
EVIDENCE = "4" * 64
VERIFIER_RECEIPT = "5" * 64


def policy(**overrides):
    base = dict(
        policy_id="company-policy-v1",
        policy_commitment=POLICY,
        allowed_capabilities=("research", "code"),
        allowed_providers=("openai", "anthropic"),
        allowed_tools=("web", "repo"),
        max_cost_microunits=10_000,
        max_tokens=50_000,
        max_steps=8,
        consequence_ceiling="D3",
    )
    base.update(overrides)
    return CompanyPolicyV1(**base)


def request(**overrides):
    base = dict(
        goal_id="company-goal-1",
        objective="Find and verify the highest-value funding opportunity for AEGIS.",
        source_commit=COMMIT,
        authority_epoch=7,
        pre_state_root=STATE,
        requested_capabilities=("research",),
        requested_providers=("openai",),
        requested_tools=("web",),
        max_cost_microunits=1_000,
        max_tokens=5_000,
        max_steps=2,
        consequence_ceiling="D2",
        deterministic_nonce="company-goal-1-run-1",
    )
    base.update(overrides)
    return CompanyGoalRequestV1(**base)


def make_executive(*, authorization_outcome="PERMIT", planner_provider="openai", calls=None):
    calls = calls if calls is not None else {}
    calls.setdefault("planner", 0)
    calls.setdefault("worker", 0)

    def planner(goal):
        calls["planner"] += 1
        return PlanV1(
            goal_id=goal.goal_id,
            steps=(
                PlanStepV1(
                    step_id="s1",
                    objective_digest=goal.objective_digest,
                    dependency_ids=(),
                    capability_id="research",
                    provider=planner_provider,
                    tool="web",
                    max_cost_microunits=100,
                    max_tokens=500,
                    consequence_class="D1",
                    target_digest=TARGET,
                ),
            ),
        )

    def authorizer(step):
        return AuthorizationResultV1(
            step_id=step.step_id,
            outcome=authorization_outcome,
            transition_id=TRANSITION,
            decision_receipt_root=DECISION_RECEIPT,
            authority_basis="POLICY",
        )

    def worker(step, _authorization):
        calls["worker"] += 1
        return WorkerResultV1(
            step_id=step.step_id,
            status="SUCCEEDED",
            output_digest=OUTPUT,
            actual_cost_microunits=50,
            actual_tokens=250,
            evidence_roots=(EVIDENCE,),
        )

    def verifier(step, result):
        return VerifiedStepObservationV1(
            step_id=step.step_id,
            worker_output_digest=result.output_digest,
            verdict="PASS",
            evidence_roots=result.evidence_roots,
            verifier_receipt_root=VERIFIER_RECEIPT,
        )

    return MetacognitiveExecutive(
        planner=planner,
        predictor=lambda _goal, _step, _state: 9000,
        authorizer=authorizer,
        worker=worker,
        verifier=verifier,
    )


def test_company_policy_is_a_hard_upper_bound_not_a_model_suggestion():
    brain = CompanyBrain(policy(), make_executive())

    cases = [
        (request(requested_capabilities=("deploy",)), "REQUEST_CAPABILITY_NOT_ALLOWED"),
        (request(requested_providers=("gemini",)), "REQUEST_PROVIDER_NOT_ALLOWED"),
        (request(requested_tools=("shell",)), "REQUEST_TOOL_NOT_ALLOWED"),
        (request(max_cost_microunits=10_001), "REQUEST_COST_BUDGET_EXCEEDED"),
        (request(max_tokens=50_001), "REQUEST_TOKEN_BUDGET_EXCEEDED"),
        (request(max_steps=9), "REQUEST_STEP_BUDGET_EXCEEDED"),
        (request(consequence_ceiling="D4"), "REQUEST_CONSEQUENCE_CEILING_EXCEEDED"),
    ]

    for current_request, code in cases:
        with pytest.raises(CompanyBrainError) as exc:
            brain.run(current_request)
        assert exc.value.code == code


def test_company_policy_cannot_enable_d4_even_when_configured_that_way():
    with pytest.raises(CompanyBrainError) as exc:
        CompanyBrain(policy(consequence_ceiling="D4"), make_executive())
    assert exc.value.code == "POLICY_D4_FORBIDDEN"


def test_successful_company_goal_runs_metacognitive_loop_and_emits_evidence_only_receipt():
    brain = CompanyBrain(policy(), make_executive())

    outcome = brain.run(request())

    assert outcome.receipt.status == "DONE"
    assert outcome.receipt.authority == "EVIDENCE_ONLY"
    assert outcome.receipt.executive_status == "COMPLETE"
    assert outcome.receipt.trace_bundle_root == outcome.executive_outcome.trace_bundle.root
    assert outcome.executive_outcome.trace_bundle.final_control_state_root == STATE
    assert outcome.receipt.total_cost_microunits == 50
    assert outcome.receipt.total_tokens == 250

    rendered = repr(asdict(outcome.receipt))
    assert request().objective not in rendered


def test_deferred_authorization_never_calls_worker_and_routes_to_operator_attention():
    calls = {}
    brain = CompanyBrain(policy(), make_executive(authorization_outcome="DEFER", calls=calls))

    outcome = brain.run(request())

    assert calls["worker"] == 0
    assert outcome.receipt.status == "WAITING_OPERATOR"
    assert outcome.receipt.executive_status == "ESCALATE"
    assert outcome.receipt.operator_attention_required is True


def test_denied_authorization_halts_without_calling_worker():
    calls = {}
    brain = CompanyBrain(policy(), make_executive(authorization_outcome="DENY", calls=calls))

    outcome = brain.run(request())

    assert calls["worker"] == 0
    assert outcome.receipt.status == "HALTED"
    assert outcome.receipt.executive_status == "HALT"
    assert outcome.receipt.operator_attention_required is False


def test_provider_planner_cannot_escape_company_request_bounds():
    brain = CompanyBrain(policy(), make_executive(planner_provider="anthropic"))

    with pytest.raises(MetacognitiveExecutiveError) as exc:
        brain.run(request(requested_providers=("openai",)))
    assert exc.value.code == "PLAN_PROVIDER_NOT_ALLOWED"


def test_same_bound_company_run_replays_to_same_receipt_and_trace_root():
    first = CompanyBrain(policy(), make_executive()).run(request())
    second = CompanyBrain(policy(), make_executive()).run(request())

    assert first.receipt.receipt_digest == second.receipt.receipt_digest
    assert first.receipt.trace_bundle_root == second.receipt.trace_bundle_root


def test_objective_text_is_digest_bound_but_not_copied_into_receipt():
    brain = CompanyBrain(policy(), make_executive())

    first = brain.run(request(objective="Research funding option A."))
    second = brain.run(request(objective="Research funding option B."))

    assert first.receipt.objective_digest != second.receipt.objective_digest
    assert "Research funding option A." not in repr(asdict(first.receipt))
    assert "Research funding option B." not in repr(asdict(second.receipt))
