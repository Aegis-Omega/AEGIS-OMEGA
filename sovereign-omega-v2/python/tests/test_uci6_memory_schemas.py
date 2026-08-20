"""UCI-6 serialization contract: five nominal memory types stay distinct on disk."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for

H = "a" * 64
ZERO = "0" * 64

CASES = {
    "schemas/quarantined-evidence-memory-record.v1.schema.json": {
        "record_kind": "QUARANTINED_EVIDENCE_MEMORY_RECORD_V1",
        "content_digest": H,
        "media_type": "text/plain",
        "producer_ref": "provider:test",
        "source_ref": "artifact:test",
        "memory_class": "WORK_RESULT",
        "epistemic_tier": "T2",
        "authority": "EVIDENCE_ONLY",
        "authority_weight_bps": 0,
    },
    "schemas/memory-projection-request.v1.schema.json": {
        "request_kind": "MEMORY_PROJECTION_REQUEST_V1",
        "quarantine_root": H,
        "content_digest": H,
        "memory_class": "WORK_RESULT",
        "epistemic_tier": "T2",
        "memory_policy_commitment": H,
        "expected_memory_sequence": 0,
        "expected_memory_event_root": ZERO,
        "nonce": "projection-1",
    },
    "schemas/canonical-memory-record.v1.schema.json": {
        "record_kind": "CANONICAL_MEMORY_RECORD_V1",
        "projection_request_root": H,
        "source_quarantine_root": H,
        "content_digest": H,
        "memory_class": "WORK_RESULT",
        "epistemic_tier": "T2",
        "authority": "EVIDENCE_ONLY",
        "authority_weight_bps": 0,
        "source_transition_id": H,
        "source_admission_root": H,
        "memory_policy_commitment": H,
        "sequence": 1,
        "prior_memory_event_root": ZERO,
    },
    "schemas/memory-control-request.v1.schema.json": {
        "request_kind": "MEMORY_CONTROL_REQUEST_V1",
        "operation": "REVOKE",
        "target_memory_root": H,
        "replacement_memory_root": None,
        "memory_policy_commitment": H,
        "expected_memory_sequence": 1,
        "expected_memory_event_root": H,
        "nonce": "revoke-1",
    },
    "schemas/memory-control-record.v1.schema.json": {
        "record_kind": "MEMORY_CONTROL_RECORD_V1",
        "control_request_root": H,
        "operation": "REVOKE",
        "target_memory_root": H,
        "replacement_memory_root": None,
        "source_transition_id": H,
        "source_admission_root": H,
        "memory_policy_commitment": H,
        "sequence": 2,
        "prior_memory_event_root": H,
    },
}


def _validator(path: str):
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    validator_type = validator_for(schema)
    validator_type.check_schema(schema)
    return validator_type(schema)


def test_uci6_memory_schemas_are_closed_and_nominally_distinct() -> None:
    for path, payload in CASES.items():
        validator = _validator(path)
        validator.validate(payload)

        injected = dict(payload, authority_escalation="FORGED")
        assert list(validator.iter_errors(injected)), f"{path} accepted unknown field"

        discriminator = "request_kind" if "request_kind" in payload else "record_kind"
        wrong_kind = dict(payload, **{discriminator: "ADMISSION_RECORD_V1"})
        assert list(validator.iter_errors(wrong_kind)), f"{path} accepted wrong discriminator"


def test_memory_control_schema_enforces_operation_shape() -> None:
    path = "schemas/memory-control-request.v1.schema.json"
    validator = _validator(path)
    base = dict(CASES[path])

    bad_revoke = dict(base, replacement_memory_root=H)
    assert list(validator.iter_errors(bad_revoke))

    bad_supersede = dict(base, operation="SUPERSEDE", replacement_memory_root=None)
    assert list(validator.iter_errors(bad_supersede))
