from __future__ import annotations

import json
from pathlib import Path

import jsonschema


def test_track_schema_serializes_descriptive_resolution_without_inferential_status() -> None:
    schema = json.loads(Path("schemas/benchmark-track-spec.v1.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    required = set(schema["required"])
    assert {
        "measurement_resolution_bps",
        "measurement_resolution_basis_commitment",
    } <= required
    assert schema["properties"]["measurement_resolution_bps"]["type"] == ["integer", "null"]
    assert schema["properties"]["measurement_resolution_basis_commitment"]["pattern"] == "^[0-9a-f]{64}$"
    serialized = json.dumps(schema)
    assert "p_value" not in serialized
    assert "confidence_interval" not in serialized
    assert "statistical_significance" not in serialized
