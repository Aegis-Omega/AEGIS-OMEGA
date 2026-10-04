from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for


SCHEMAS = {
    Path("schemas/benchmark-track-spec.v1.schema.json"): ("track_kind", "BENCHMARK_TRACK_SPEC_V1"),
    Path("schemas/evaluation-campaign-manifest.v1.schema.json"): ("campaign_kind", "EVALUATION_CAMPAIGN_MANIFEST_V1"),
    Path("schemas/paired-benchmark-trial.v1.schema.json"): ("pair_kind", "PAIRED_BENCHMARK_TRIAL_V1"),
    Path("schemas/campaign-evidence-bundle.v1.schema.json"): ("bundle_kind", "CAMPAIGN_EVIDENCE_BUNDLE_V1"),
}


def test_uci8_schemas_are_closed_valid_and_nominally_distinct() -> None:
    seen_kinds: set[str] = set()
    for path, (kind_field, kind_value) in SCHEMAS.items():
        schema = json.loads(path.read_text(encoding="utf-8"))
        validator_for(schema).check_schema(schema)
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["properties"][kind_field]["const"] == kind_value
        assert kind_value not in seen_kinds
        seen_kinds.add(kind_value)


def test_track_schema_closes_nested_task_trial_units() -> None:
    schema = json.loads(Path("schemas/benchmark-track-spec.v1.schema.json").read_text(encoding="utf-8"))
    unit = schema["$defs"]["taskTrialUnit"]
    assert unit["type"] == "object"
    assert unit["additionalProperties"] is False
    assert unit["properties"]["unit_kind"]["const"] == "CAMPAIGN_TASK_TRIAL_UNIT_V1"
