from __future__ import annotations

from dataclasses import replace

import pytest

from harness.sdk.evaluation_campaign import EvaluationCampaignError
from harness.sdk.evaluation_claim import (
    BaselineNoiseCalibrationV1,
    BaselineStrategy,
    CollectiveClaimStatus,
    ComputeBudgetV1,
    ComputeMatchedBaselineSpecV1,
    ComputeUsageObservationV1,
    ComputeUsageRole,
    LocalComputeUsageMeterV1,
    MetricComparisonV1,
    PortableComputeUsageHMACV1,
    PreregisteredStructuralValueClaimV1,
)

H = lambda ch: ch * 64
RUN_ID = "structural-compute-run-1"
KEY = b"uci8-compute-usage-portable-hmac-key-32bytes-min"
METER = H("9")
EXECUTION_BUNDLE = H("8")


def _budget():
    return ComputeBudgetV1(
        max_input_tokens=100_000,
        max_output_tokens=20_000,
        max_model_calls=8,
        max_tool_calls=12,
    )


def _claim():
    baseline = ComputeMatchedBaselineSpecV1.create(
        campaign_root=H("1"),
        strongest_constituent_runtime_commitment=H("2"),
        baseline_runtime_commitment=H("2"),
        system_total_budget=_budget(),
        baseline_total_budget=_budget(),
        strategy=BaselineStrategy.BEST_OF_N_DETERMINISTIC_CHECKER,
        strategy_commitment=H("3"),
        meter_source_commitment=METER,
    )
    calibrations = (
        BaselineNoiseCalibrationV1.create(
            metric_id="accuracy",
            unit_id="BPS",
            calibration_run_ids=("cal-a-1", "cal-a-2", "cal-a-3"),
            baseline_values=(7000, 7100, 6900),
            calibration_split_commitment=H("4"),
            calibration_evidence_commitment=H("5"),
        ),
        BaselineNoiseCalibrationV1.create(
            metric_id="tool_success",
            unit_id="BPS",
            calibration_run_ids=("cal-t-1", "cal-t-2", "cal-t-3"),
            baseline_values=(8000, 8050, 7950),
            calibration_split_commitment=H("6"),
            calibration_evidence_commitment=H("7"),
        ),
    )
    return PreregisteredStructuralValueClaimV1.create(
        campaign_root=H("1"),
        comparison_task_population_commitment=H("a"),
        compute_matched_baseline=baseline,
        calibrations=calibrations,
    )


def _comparisons():
    return (
        MetricComparisonV1(metric_id="accuracy", unit_id="BPS", system_value=7300, baseline_value=7000),
        MetricComparisonV1(metric_id="tool_success", unit_id="BPS", system_value=8200, baseline_value=8000),
    )


def _attestations(*, baseline_input=90_000, baseline_output=18_000, baseline_model_calls=8, baseline_tool_calls=12):
    meter = LocalComputeUsageMeterV1(meter_source_commitment=METER)
    system_obs = meter.observe(
        run_id=RUN_ID,
        campaign_root=H("1"),
        role=ComputeUsageRole.SYSTEM,
        runtime_commitment=H("b"),
        input_tokens=90_000,
        output_tokens=18_000,
        model_calls=8,
        tool_calls=12,
        execution_receipt_bundle_commitment=EXECUTION_BUNDLE,
    )
    baseline_obs = meter.observe(
        run_id=RUN_ID,
        campaign_root=H("1"),
        role=ComputeUsageRole.BASELINE,
        runtime_commitment=H("2"),
        input_tokens=baseline_input,
        output_tokens=baseline_output,
        model_calls=baseline_model_calls,
        tool_calls=baseline_tool_calls,
        execution_receipt_bundle_commitment=EXECUTION_BUNDLE,
    )
    portable = PortableComputeUsageHMACV1(key_id="compute-usage-key-v1", secret_key=KEY)
    return portable, portable.issue(system_obs), portable.issue(baseline_obs)


def test_structural_claim_cannot_be_evaluated_without_actual_compute_evidence() -> None:
    with pytest.raises(EvaluationCampaignError, match="ACTUAL_COMPUTE_MATCH_REQUIRED"):
        _claim().evaluate(_comparisons())


def test_usage_attestation_issuer_rejects_publicly_constructed_observation() -> None:
    forged = ComputeUsageObservationV1(
        run_id=RUN_ID,
        campaign_root=H("1"),
        role=ComputeUsageRole.SYSTEM,
        runtime_commitment=H("b"),
        input_tokens=1,
        output_tokens=1,
        model_calls=1,
        tool_calls=0,
        execution_receipt_bundle_commitment=EXECUTION_BUNDLE,
        meter_source_commitment=METER,
    )
    portable = PortableComputeUsageHMACV1(key_id="compute-usage-key-v1", secret_key=KEY)
    with pytest.raises(EvaluationCampaignError, match="COMPUTE_USAGE_ISSUER_REQUIRES_METER_OBSERVATION"):
        portable.issue(forged)


def test_compute_usage_hmac_survives_reconstruction_and_detects_tampering() -> None:
    portable, system_att, _baseline_att = _attestations()
    portable.verify(replace(system_att))
    with pytest.raises(EvaluationCampaignError, match="COMPUTE_USAGE_MAC_INVALID"):
        portable.verify(replace(system_att, input_tokens=system_att.input_tokens + 1))


def test_baseline_actual_tokens_must_cover_system_actual_tokens() -> None:
    portable, system_att, baseline_att = _attestations(baseline_input=89_999)
    with pytest.raises(EvaluationCampaignError, match="ACTUAL_COMPUTE_BASELINE_TOKEN_USAGE_INSUFFICIENT"):
        _claim().evaluate(
            _comparisons(),
            system_usage=system_att,
            baseline_usage=baseline_att,
            usage_verifier=portable,
        )


def test_baseline_actual_model_calls_must_cover_system_model_calls() -> None:
    portable, system_att, baseline_att = _attestations(baseline_model_calls=7)
    with pytest.raises(EvaluationCampaignError, match="ACTUAL_COMPUTE_BASELINE_MODEL_CALLS_INSUFFICIENT"):
        _claim().evaluate(
            _comparisons(),
            system_usage=system_att,
            baseline_usage=baseline_att,
            usage_verifier=portable,
        )


def test_baseline_actual_tool_calls_must_cover_system_tool_calls() -> None:
    portable, system_att, baseline_att = _attestations(baseline_tool_calls=11)
    with pytest.raises(EvaluationCampaignError, match="ACTUAL_COMPUTE_BASELINE_TOOL_CALLS_INSUFFICIENT"):
        _claim().evaluate(
            _comparisons(),
            system_usage=system_att,
            baseline_usage=baseline_att,
            usage_verifier=portable,
        )


def test_usage_must_stay_within_preregistered_caps_and_meter_source() -> None:
    portable, system_att, baseline_att = _attestations()
    with pytest.raises(EvaluationCampaignError, match="ACTUAL_COMPUTE_USAGE_EXCEEDS_PREREGISTERED_CAP"):
        _claim().evaluate(
            _comparisons(),
            system_usage=replace(system_att, input_tokens=100_001, mac_hex=system_att.mac_hex),
            baseline_usage=baseline_att,
            usage_verifier=portable,
        )


def test_structural_claim_satisfies_only_after_portable_actual_compute_match() -> None:
    portable, system_att, baseline_att = _attestations()
    result = _claim().evaluate(
        _comparisons(),
        system_usage=system_att,
        baseline_usage=baseline_att,
        usage_verifier=portable,
    )
    assert result.status is CollectiveClaimStatus.SATISFIED
    assert result.failing_metric_ids == ()
