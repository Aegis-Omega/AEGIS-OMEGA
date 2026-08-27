from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = {
    "CAPABILITY_TASK_SPEC_V1": REPO_ROOT / "schemas/capability-task-spec.v1.schema.json",
    "CAPABILITY_TRIAL_RESULT_V1": REPO_ROOT / "schemas/capability-trial-result.v1.schema.json",
    "EVALUATION_SUITE_V1": REPO_ROOT / "schemas/evaluation-suite.v1.schema.json",
    "AGI_EVIDENCE_ASSESSMENT_V1": REPO_ROOT / "schemas/agi-evidence-assessment.v1.schema.json",
}


def test_uci7_schema_files_are_draft_2020_12_closed_and_valid() -> None:
    for expected_kind, path in SCHEMAS.items():
        schema = json.loads(path.read_text(encoding="utf-8"))
        validator_for(schema).check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
        kind_property = next(
            value
            for key, value in schema["properties"].items()
            if key in {"task_kind", "result_kind", "suite_kind", "assessment_kind"}
        )
        assert kind_property["const"] == expected_kind


def test_uci7_task_schema_rejects_unknown_field_and_wrong_kind() -> None:
    schema = json.loads(SCHEMAS["CAPABILITY_TASK_SPEC_V1"].read_text(encoding="utf-8"))
    validator = validator_for(schema)(schema)
    valid = {
        "task_kind": "CAPABILITY_TASK_SPEC_V1",
        "task_id": "arc-hidden-001",
        "axis": "NOVEL_ABSTRACTION_TRANSFER",
        "domain": "abstract-reasoning",
        "hidden_case_commitment": "1" * 64,
        "checker_commitment": "2" * 64,
        "budget_commitment": "3" * 64,
        "human_reference_commitment": "4" * 64,
        "trial_count": 3,
        "contamination_class": "HELD_OUT",
        "suite_policy_commitment": "5" * 64,
    }
    validator.validate(valid)
    assert list(validator.iter_errors({**valid, "authority": "FORGED"}))
    assert list(validator.iter_errors({**valid, "task_kind": "AGI_PROVEN"}))
