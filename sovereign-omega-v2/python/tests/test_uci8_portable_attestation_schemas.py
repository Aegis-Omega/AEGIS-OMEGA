from __future__ import annotations

import json
from pathlib import Path

import jsonschema


def test_checker_attestation_schema_exists_closed_and_nominal() -> None:
    path = Path("schemas/checker-result-attestation.v1.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["attestation_kind"]["const"] == "CHECKER_RESULT_ATTESTATION_V1"
    assert {
        "attestation_kind",
        "run_id",
        "task_spec_root",
        "trial_index",
        "result_root",
        "checker_commitment",
        "key_id",
        "mac_hex",
    } <= set(schema["required"])


def test_pair_schema_binds_portable_checker_replay_fields() -> None:
    path = Path("schemas/paired-benchmark-trial.v1.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    required = set(schema["required"])
    assert {
        "checker_run_id",
        "system_checker_attestation_root",
        "baseline_checker_attestation_root",
    } <= required
    assert schema["properties"]["checker_run_id"]["type"] == ["string", "null"]
    assert schema["properties"]["system_checker_attestation_root"]["pattern"] == "^[0-9a-f]{64}$"
    assert schema["properties"]["baseline_checker_attestation_root"]["pattern"] == "^[0-9a-f]{64}$"
