from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ZERO = "0" * 64
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
H5 = "5" * 64
H6 = "6" * 64
H7 = "7" * 64
H8 = "8" * 64
H9 = "9" * 64


def _load(name: str) -> dict:
    path = Path("schemas") / name
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def _pair(*, run_id=None, system_att=ZERO, baseline_att=ZERO) -> dict:
    return {
        "pair_kind": "PAIRED_BENCHMARK_TRIAL_V1",
        "campaign_root": H1,
        "track_root": H2,
        "task_trial_unit_root": H3,
        "system_result_root": H4,
        "baseline_result_root": H5,
        "system_runtime_commitment": H6,
        "baseline_runtime_commitment": H7,
        "budget_commitment": H8,
        "scorer_commitment": H9,
        "checker_run_id": run_id,
        "system_checker_attestation_root": system_att,
        "baseline_checker_attestation_root": baseline_att,
    }


def _bundle(*, status: str, verification_roots: list[str]) -> dict:
    return {
        "bundle_kind": "CAMPAIGN_EVIDENCE_BUNDLE_V1",
        "campaign_root": H1,
        "paired_trial_roots": [H2],
        "pair_verification_roots": verification_roots,
        "benchmark_adapter_executable_commitment": H3,
        "runner_environment_commitment": H4,
        "execution_receipt_bundle_commitment": H5,
        "evidence_status": status,
    }


def test_pair_verification_attestation_schema_exists_closed_and_nominal() -> None:
    schema = _load("pair-verification-attestation.v1.schema.json")
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["attestation_kind"]["const"] == "PAIR_VERIFICATION_ATTESTATION_V1"
    assert set(schema["required"]) == {
        "attestation_kind",
        "run_id",
        "pair_root",
        "campaign_root",
        "track_root",
        "task_trial_unit_root",
        "system_checker_attestation_root",
        "baseline_checker_attestation_root",
        "key_id",
        "mac_hex",
    }


def test_pair_schema_enforces_all_or_none_portable_result_attestation_fields() -> None:
    schema = _load("paired-benchmark-trial.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(_pair())
    validator.validate(_pair(run_id="run-1", system_att=H1, baseline_att=H2))

    with pytest.raises(jsonschema.ValidationError):
        validator.validate(_pair(run_id=None, system_att=H1, baseline_att=H2))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(_pair(run_id="run-1", system_att=ZERO, baseline_att=H2))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(_pair(run_id="run-1", system_att=H1, baseline_att=ZERO))


def test_bundle_schema_requires_pair_verification_roots_for_collective_status() -> None:
    schema = _load("campaign-evidence-bundle.v1.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(_bundle(status="HELD_OUT_EVIDENCE_COMPLETE", verification_roots=[]))
    validator.validate(_bundle(status="COLLECTIVE_CONTRIBUTION_EVALUABLE", verification_roots=[H6]))

    with pytest.raises(jsonschema.ValidationError):
        validator.validate(_bundle(status="COLLECTIVE_CONTRIBUTION_EVALUABLE", verification_roots=[]))

    duplicate = _bundle(status="COLLECTIVE_CONTRIBUTION_EVALUABLE", verification_roots=[H6, H6])
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(duplicate)
