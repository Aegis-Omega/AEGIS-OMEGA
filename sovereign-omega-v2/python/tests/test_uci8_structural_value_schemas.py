from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_DIR = Path("schemas")
H = lambda ch: ch * 64


def _load(name: str) -> dict:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def test_campaign_verification_receipt_schema_is_closed_and_collective_only() -> None:
    schema = _load("campaign-evidence-verification-receipt.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    payload = {
        "receipt_kind": "CAMPAIGN_EVIDENCE_VERIFICATION_RECEIPT_V1",
        "verification_id": "verification-1",
        "bundle_root": H("1"),
        "campaign_root": H("2"),
        "pair_verification_roots": [H("3")],
        "benchmark_adapter_executable_commitment": H("4"),
        "runner_environment_commitment": H("5"),
        "execution_receipt_bundle_commitment": H("6"),
        "verification_status": "COLLECTIVE_CONTRIBUTION_EVALUABLE",
        "key_id": "campaign-key-v1",
        "mac_hex": H("7"),
    }
    validator.validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**payload, "verification_status": "HELD_OUT_EVIDENCE_COMPLETE"})
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**payload, "extra": True})


def test_bundle_schema_cannot_self_assert_collective_status() -> None:
    schema = _load("campaign-evidence-bundle.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    payload = {
        "bundle_kind": "CAMPAIGN_EVIDENCE_BUNDLE_V1",
        "campaign_root": H("1"),
        "paired_trial_roots": [H("2")],
        "pair_verification_roots": [H("3")],
        "benchmark_adapter_executable_commitment": H("4"),
        "runner_environment_commitment": H("5"),
        "execution_receipt_bundle_commitment": H("6"),
        "evidence_status": "COLLECTIVE_CONTRIBUTION_EVALUABLE",
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)


def test_compute_budget_schema_has_tokens_and_calls_but_no_wall_clock() -> None:
    schema = _load("compute-budget.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    payload = {
        "budget_kind": "COMPUTE_BUDGET_V1",
        "max_input_tokens": 100000,
        "max_output_tokens": 20000,
        "max_model_calls": 8,
        "max_tool_calls": 12,
    }
    validator.validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**payload, "wall_clock_seconds": 120})


def test_compute_matched_baseline_schema_is_closed_and_nominal() -> None:
    schema = _load("compute-matched-baseline-spec.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    budget = {
        "budget_kind": "COMPUTE_BUDGET_V1",
        "max_input_tokens": 100000,
        "max_output_tokens": 20000,
        "max_model_calls": 8,
        "max_tool_calls": 12,
    }
    payload = {
        "spec_kind": "COMPUTE_MATCHED_BASELINE_SPEC_V1",
        "campaign_root": H("1"),
        "strongest_constituent_runtime_commitment": H("2"),
        "baseline_runtime_commitment": H("2"),
        "system_total_budget": budget,
        "baseline_total_budget": budget,
        "strategy": "BEST_OF_N_DETERMINISTIC_CHECKER",
        "strategy_commitment": H("3"),
    }
    validator.validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**payload, "strategy": "POST_HOC_PICK_BEST"})


def test_baseline_noise_calibration_schema_keeps_raw_measurement_evidence() -> None:
    schema = _load("baseline-noise-calibration.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    payload = {
        "calibration_kind": "BASELINE_NOISE_CALIBRATION_V1",
        "metric_id": "accuracy",
        "unit_id": "BPS",
        "calibration_run_ids": ["cal-1", "cal-2", "cal-3"],
        "baseline_values": [7000, 7100, 6900],
        "calibration_split_commitment": H("4"),
        "calibration_evidence_commitment": H("5"),
        "delta_floor": 200,
        "floor_rule": "MAX_OBSERVED_RANGE_V1",
    }
    validator.validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**payload, "calibration_run_ids": ["cal-1", "cal-2"]})


def test_preregistered_claim_schema_binds_compute_and_calibration_roots() -> None:
    schema = _load("preregistered-structural-value-claim.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    payload = {
        "claim_kind": "PREREGISTERED_STRUCTURAL_VALUE_CLAIM_V1",
        "campaign_root": H("1"),
        "comparison_task_population_commitment": H("2"),
        "compute_matched_baseline_root": H("3"),
        "calibration_roots": [H("4"), H("5"), H("6")],
    }
    validator.validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**payload, "calibration_roots": []})


def test_structural_claim_evaluation_schema_is_binary_only() -> None:
    schema = _load("structural-value-claim-evaluation.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    payload = {
        "evaluation_kind": "STRUCTURAL_VALUE_CLAIM_EVALUATION_V1",
        "claim_root": H("1"),
        "status": "FALSIFIED",
        "failing_metric_ids": ["horizon"],
    }
    validator.validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**payload, "status": "PARTIAL_SUCCESS"})
