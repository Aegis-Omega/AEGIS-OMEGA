from __future__ import annotations

import pytest

from harness.sdk.evaluation_campaign import EvaluationCampaignError
from harness.sdk.evaluation_claim import (
    BaselineNoiseCalibrationV1,
    BaselineStrategy,
    CampaignRunLedgerV1,
    CollectiveClaimStatus,
    ComputeBudgetV1,
    ComputeMatchedBaselineSpecV1,
    MetricComparisonV1,
    PreregisteredStructuralValueClaimV1,
)

H = lambda ch: ch * 64


def _budget(*, input_tokens: int = 100_000, output_tokens: int = 20_000, model_calls: int = 8, tool_calls: int = 12):
    return ComputeBudgetV1(
        max_input_tokens=input_tokens,
        max_output_tokens=output_tokens,
        max_model_calls=model_calls,
        max_tool_calls=tool_calls,
    )


def _baseline(*, budget=None):
    return ComputeMatchedBaselineSpecV1.create(
        campaign_root=H("1"),
        strongest_constituent_runtime_commitment=H("2"),
        baseline_runtime_commitment=H("2"),
        system_total_budget=_budget(),
        baseline_total_budget=budget or _budget(),
        strategy=BaselineStrategy.BEST_OF_N_DETERMINISTIC_CHECKER,
        strategy_commitment=H("3"),
    )


def _calibration(metric_id: str, values: tuple[int, ...], *, split: str):
    return BaselineNoiseCalibrationV1.create(
        metric_id=metric_id,
        unit_id="BPS",
        calibration_run_ids=tuple(f"cal-{metric_id}-{i}" for i in range(len(values))),
        baseline_values=values,
        calibration_split_commitment=split,
        calibration_evidence_commitment=H("4"),
    )


def _claim(*, calibrations=None):
    calibrations = calibrations or (
        _calibration("accuracy", (7000, 7100, 6900), split=H("5")),
        _calibration("tool_success", (8000, 8050, 7950), split=H("6")),
        _calibration("horizon", (100, 105, 98), split=H("7")),
    )
    return PreregisteredStructuralValueClaimV1.create(
        campaign_root=H("1"),
        comparison_task_population_commitment=H("8"),
        compute_matched_baseline=_baseline(),
        calibrations=calibrations,
    )


def test_compute_budget_binds_tokens_and_call_counts_not_wall_clock() -> None:
    budget = _budget()
    assert budget.to_dict() == {
        "budget_kind": "COMPUTE_BUDGET_V1",
        "max_input_tokens": 100_000,
        "max_output_tokens": 20_000,
        "max_model_calls": 8,
        "max_tool_calls": 12,
    }
    assert "wall_clock" not in budget.to_dict()


def test_compute_matched_baseline_rejects_token_advantage() -> None:
    with pytest.raises(EvaluationCampaignError, match="COMPUTE_MATCH_TOKEN_BUDGET_MISMATCH"):
        _baseline(budget=_budget(output_tokens=19_999))


def test_compute_matched_baseline_rejects_call_advantage() -> None:
    with pytest.raises(EvaluationCampaignError, match="COMPUTE_MATCH_CALL_BUDGET_MISMATCH"):
        _baseline(budget=_budget(model_calls=7))


def test_compute_matched_baseline_must_use_preregistered_strongest_constituent_runtime() -> None:
    with pytest.raises(EvaluationCampaignError, match="COMPUTE_MATCH_BASELINE_RUNTIME_MISMATCH"):
        ComputeMatchedBaselineSpecV1.create(
            campaign_root=H("1"),
            strongest_constituent_runtime_commitment=H("2"),
            baseline_runtime_commitment=H("9"),
            system_total_budget=_budget(),
            baseline_total_budget=_budget(),
            strategy=BaselineStrategy.BEST_OF_N_DETERMINISTIC_CHECKER,
            strategy_commitment=H("3"),
        )


def test_delta_floor_is_derived_from_committed_baseline_run_to_run_range() -> None:
    calibration = _calibration("accuracy", (7000, 7100, 6900), split=H("5"))
    assert calibration.delta_floor == 200
    assert calibration.to_dict()["baseline_values"] == [7000, 7100, 6900]
    assert calibration.to_dict()["calibration_evidence_commitment"] == H("4")


def test_delta_calibration_requires_independent_repeated_runs() -> None:
    with pytest.raises(EvaluationCampaignError, match="BASELINE_NOISE_REQUIRES_AT_LEAST_THREE_RUNS"):
        _calibration("accuracy", (7000, 7100), split=H("5"))
    with pytest.raises(EvaluationCampaignError, match="DUPLICATE_CALIBRATION_RUN_ID"):
        BaselineNoiseCalibrationV1.create(
            metric_id="accuracy",
            unit_id="BPS",
            calibration_run_ids=("same", "same", "other"),
            baseline_values=(7000, 7100, 6900),
            calibration_split_commitment=H("5"),
            calibration_evidence_commitment=H("4"),
        )


def test_claim_rejects_noise_calibration_from_comparison_population() -> None:
    bad = _calibration("accuracy", (7000, 7100, 6900), split=H("8"))
    with pytest.raises(EvaluationCampaignError, match="CALIBRATION_COMPARISON_POPULATION_COLLISION"):
        _claim(calibrations=(bad,))


def test_claim_is_strictly_binary_and_requires_all_preregistered_metrics() -> None:
    claim = _claim()
    assert {status.value for status in CollectiveClaimStatus} == {"SATISFIED", "FALSIFIED"}
    with pytest.raises(EvaluationCampaignError, match="CLAIM_METRIC_SET_MISMATCH"):
        claim.evaluate((MetricComparisonV1(metric_id="accuracy", unit_id="BPS", system_value=7400, baseline_value=7000),))


def test_two_of_three_metrics_is_falsified_not_partial_success() -> None:
    claim = _claim()
    result = claim.evaluate((
        MetricComparisonV1(metric_id="accuracy", unit_id="BPS", system_value=7300, baseline_value=7000),
        MetricComparisonV1(metric_id="tool_success", unit_id="BPS", system_value=8200, baseline_value=8000),
        MetricComparisonV1(metric_id="horizon", unit_id="BPS", system_value=105, baseline_value=100),
    ))
    assert result.status is CollectiveClaimStatus.FALSIFIED
    assert result.failing_metric_ids == ("horizon",)


def test_all_metrics_must_meet_preregistered_noise_floors() -> None:
    claim = _claim()
    result = claim.evaluate((
        MetricComparisonV1(metric_id="accuracy", unit_id="BPS", system_value=7200, baseline_value=7000),
        MetricComparisonV1(metric_id="tool_success", unit_id="BPS", system_value=8100, baseline_value=8000),
        MetricComparisonV1(metric_id="horizon", unit_id="BPS", system_value=107, baseline_value=100),
    ))
    assert result.status is CollectiveClaimStatus.SATISFIED
    assert result.failing_metric_ids == ()


def test_run_ledger_requires_start_before_terminal_and_keeps_abandoned_attempt(tmp_path) -> None:
    ledger = CampaignRunLedgerV1(tmp_path / "campaign-runs.sqlite")
    claim = _claim()
    for calibration in claim.calibrations:
        ledger.record_calibration(calibration)
    ledger.freeze_claim(claim)
    with pytest.raises(EvaluationCampaignError, match="RUN_START_REQUIRED"):
        ledger.complete_run(run_id="never-started", result_commitment=H("a"))
    ledger.start_run(run_id="attempt-1", claim=claim, seed_commitment=H("b"))
    ledger.abandon_run(run_id="attempt-1", reason="infra_failure", reason_commitment=H("c"))
    attempts = ledger.attempts(claim.campaign_root)
    assert [(a.run_id, a.terminal_status, a.reason) for a in attempts] == [("attempt-1", "ABANDONED", "infra_failure")]


def test_seed_reroll_cannot_hide_previous_campaign_attempt(tmp_path) -> None:
    ledger = CampaignRunLedgerV1(tmp_path / "campaign-runs.sqlite")
    claim = _claim()
    for calibration in claim.calibrations:
        ledger.record_calibration(calibration)
    ledger.freeze_claim(claim)
    ledger.start_run(run_id="attempt-1", claim=claim, seed_commitment=H("b"))
    ledger.abandon_run(run_id="attempt-1", reason="infra_failure", reason_commitment=H("c"))
    ledger.start_run(run_id="attempt-2", claim=claim, seed_commitment=H("d"))
    ledger.complete_run(run_id="attempt-2", result_commitment=H("e"))
    attempts = ledger.attempts(claim.campaign_root)
    assert [a.run_id for a in attempts] == ["attempt-1", "attempt-2"]
    assert [a.terminal_status for a in attempts] == ["ABANDONED", "COMPLETED"]
