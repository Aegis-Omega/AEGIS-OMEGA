from __future__ import annotations

from dataclasses import replace

from harness.sdk.self_improvement import (
    CandidateObservationV1,
    EvaluationReceiptV1,
    ExperimentContractV1,
    HypothesisEnvelopeV1,
    ImprovementVerifierV1,
    MetricDirection,
    MetricObservationV1,
    MetricRuleV1,
)
from harness.sdk.sovereign_execution import canonical_hash


def h(domain: str, value: object) -> str:
    return canonical_hash(domain, value)


class EvaluationStore:
    def __init__(self) -> None:
        self.data: dict[str, EvaluationReceiptV1] = {}

    def put(self, receipt: EvaluationReceiptV1) -> str:
        self.data[receipt.root] = receipt
        return receipt.root

    def fetch_verified(self, root: str):
        return self.data.get(root)


def make_case():
    baseline_root = h("BASELINE", "v1")
    candidate_root = h("CANDIDATE", "v2")
    evaluator_root = h("EVALUATOR", "independent-v1")
    evaluator_policy_root = h("EVALUATOR_POLICY", "v1")
    verifier_root = h("IMPROVEMENT_VERIFIER", "v1")
    policy_root = h("IMPROVEMENT_POLICY", "v1")
    evaluation_input_root = h("EVALUATION_INPUTS", "public-v1")
    withheld_labels_root = h("WITHHELD_LABELS", "secret-v1")
    environment_root = h("ENVIRONMENT", "python-3.12")

    hypothesis = HypothesisEnvelopeV1(
        hypothesis_id="hypothesis-1",
        baseline_artifact_root=baseline_root,
        proposal_root=h("PROPOSAL", "candidate-v2"),
        search_policy_root=h("SEARCH_POLICY", "bounded-v1"),
        declared_objective_root=h("OBJECTIVE", "improve-quality-without-latency-regression"),
    )
    rules = (
        MetricRuleV1("quality", MetricDirection.MAXIMIZE, 2_000),
        MetricRuleV1("latency", MetricDirection.MINIMIZE, 5_000),
    )
    contract = ExperimentContractV1(
        experiment_id="experiment-1",
        hypothesis_root=hypothesis.root,
        baseline_artifact_root=baseline_root,
        evaluation_input_root=evaluation_input_root,
        withheld_labels_root=withheld_labels_root,
        environment_root=environment_root,
        evaluator_root=evaluator_root,
        evaluator_policy_root=evaluator_policy_root,
        verifier_root=verifier_root,
        policy_root=policy_root,
        max_trials=3,
        metric_rules=rules,
    )
    candidate = CandidateObservationV1(
        experiment_contract_root=contract.root,
        hypothesis_root=hypothesis.root,
        baseline_artifact_root=baseline_root,
        candidate_artifact_root=candidate_root,
        trial_index=0,
        builder_root=h("BUILDER", "research-cell-v1"),
        environment_root=environment_root,
        accessed_roots=(evaluation_input_root,),
    )
    evaluation = EvaluationReceiptV1(
        experiment_contract_root=contract.root,
        baseline_artifact_root=baseline_root,
        candidate_artifact_root=candidate_root,
        evaluation_input_root=evaluation_input_root,
        environment_root=environment_root,
        evaluator_root=evaluator_root,
        evaluator_policy_root=evaluator_policy_root,
        observed_candidate_access_roots=(evaluation_input_root,),
        baseline_metrics=(
            MetricObservationV1("quality", 800_000),
            MetricObservationV1("latency", 200_000),
        ),
        candidate_metrics=(
            MetricObservationV1("quality", 806_000),
            MetricObservationV1("latency", 190_000),
        ),
        contamination_detected=False,
        status="PASS",
    )
    store = EvaluationStore()
    store.put(evaluation)
    verifier = ImprovementVerifierV1(
        verifier_root=verifier_root,
        policy_root=policy_root,
        evaluation_store=store,
    )
    return hypothesis, contract, candidate, evaluation, store, verifier


def test_valid_independent_improvement_issues_evidence_only_receipt():
    hypothesis, contract, candidate, evaluation, _, verifier = make_case()
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=candidate,
        evaluation_receipt_root=evaluation.root,
    )
    assert result.status == "PASS"
    assert result.error_codes == ()
    assert receipt is not None
    assert receipt.authority_class == "NONE"
    assert receipt.baseline_artifact_root == contract.baseline_artifact_root
    assert receipt.candidate_artifact_root == candidate.candidate_artifact_root
    assert dict(receipt.metric_improvements_micros) == {
        "latency": 10_000,
        "quality": 6_000,
    }


def test_withheld_label_access_fails_closed():
    hypothesis, contract, candidate, evaluation, _, verifier = make_case()
    contaminated_access = replace(
        candidate,
        accessed_roots=tuple(sorted((contract.evaluation_input_root, contract.withheld_labels_root))),
    )
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=contaminated_access,
        evaluation_receipt_root=evaluation.root,
    )
    assert receipt is None
    assert "WITHHELD_LABEL_ACCESS_DETECTED" in result.error_codes


def test_withheld_label_access_cannot_be_hidden_by_candidate_self_report():
    hypothesis, contract, candidate, evaluation, store, verifier = make_case()
    evaluator_observed_leak = replace(
        evaluation,
        observed_candidate_access_roots=tuple(
            sorted((contract.evaluation_input_root, contract.withheld_labels_root))
        ),
    )
    assert evaluator_observed_leak.root != evaluation.root
    store.put(evaluator_observed_leak)
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=candidate,
        evaluation_receipt_root=evaluator_observed_leak.root,
    )
    assert receipt is None
    assert "WITHHELD_LABEL_ACCESS_DETECTED" in result.error_codes
    assert "ACCESS_OBSERVATION_BINDING_FAILURE" in result.error_codes


def test_candidate_access_report_must_match_independent_observation():
    hypothesis, contract, candidate, evaluation, store, verifier = make_case()
    extra_safe_root = h("PUBLIC_RESOURCE", "extra")
    evaluator_observation = replace(
        evaluation,
        observed_candidate_access_roots=tuple(
            sorted((contract.evaluation_input_root, extra_safe_root))
        ),
    )
    store.put(evaluator_observation)
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=candidate,
        evaluation_receipt_root=evaluator_observation.root,
    )
    assert receipt is None
    assert "ACCESS_OBSERVATION_BINDING_FAILURE" in result.error_codes


def test_evaluation_receipt_cannot_be_spliced_to_different_candidate():
    hypothesis, contract, candidate, evaluation, _, verifier = make_case()
    spliced_candidate = replace(
        candidate,
        candidate_artifact_root=h("CANDIDATE", "spliced-v3"),
    )
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=spliced_candidate,
        evaluation_receipt_root=evaluation.root,
    )
    assert receipt is None
    assert "EVALUATION_BINDING_FAILURE" in result.error_codes


def test_candidate_cannot_select_different_evaluator():
    hypothesis, contract, candidate, evaluation, store, verifier = make_case()
    forged = replace(
        evaluation,
        evaluator_root=h("EVALUATOR", "candidate-selected"),
    )
    assert forged.root != evaluation.root
    store.put(forged)
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=candidate,
        evaluation_receipt_root=forged.root,
    )
    assert receipt is None
    assert "EVALUATOR_BINDING_FAILURE" in result.error_codes


def test_metric_regression_fails_preregistered_gate():
    hypothesis, contract, candidate, evaluation, store, verifier = make_case()
    regressing = replace(
        evaluation,
        candidate_metrics=(
            MetricObservationV1("quality", 799_000),
            MetricObservationV1("latency", 205_000),
        ),
    )
    store.put(regressing)
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=candidate,
        evaluation_receipt_root=regressing.root,
    )
    assert receipt is None
    assert "METRIC_THRESHOLD_FAILURE" in result.error_codes


def test_untrusted_evaluation_receipt_fails_closed():
    hypothesis, contract, candidate, _, _, verifier = make_case()
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=candidate,
        evaluation_receipt_root=h("UNTRUSTED_EVALUATION", 1),
    )
    assert receipt is None
    assert result.error_codes == ("EVALUATION_RECEIPT_UNTRUSTED",)


def test_contamination_flag_fails_closed():
    hypothesis, contract, candidate, evaluation, store, verifier = make_case()
    contaminated = replace(evaluation, contamination_detected=True)
    store.put(contaminated)
    result, receipt = verifier.verify_and_issue(
        hypothesis=hypothesis,
        contract=contract,
        candidate=candidate,
        evaluation_receipt_root=contaminated.root,
    )
    assert receipt is None
    assert "EVALUATION_CONTAMINATION_DETECTED" in result.error_codes
