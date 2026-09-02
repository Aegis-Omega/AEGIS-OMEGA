from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase, main

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "cognitive-recovery-admission-request.v1.schema.json"
RECEIPT_SCHEMA_PATH = REPO_ROOT / "schemas" / "cognitive-recovery-admission-receipt.v1.schema.json"

SHA1_A = "a" * 40
SHA1_B = "b" * 40
SHA1_C = "c" * 40
SHA1_D = "d" * 40
SHA256_1 = "1" * 64
SHA256_2 = "2" * 64
SHA256_3 = "3" * 64
SHA256_4 = "4" * 64
SHA256_5 = "5" * 64
SHA256_6 = "6" * 64
SHA256_7 = "7" * 64
SHA256_8 = "8" * 64


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_request() -> dict:
    return {
        "schema_version": "1.0.0",
        "request_id": SHA256_1,
        "repository_id": "Aegis-Omega/AEGIS-OMEGA",
        "trusted_control_plane_sha": SHA1_A,
        "recovery_parent_sha": SHA1_B,
        "denied_base_sha": SHA1_C,
        "candidate_sha": SHA1_D,
        "zero_parent_repair_sha": "e" * 40,
        "zero_parent_validator_blob": "f" * 40,
        "zero_parent_test_blob": "0" * 40,
        "writer_workflow_blob": "1" * 40,
        "recovery_receipt_hash": SHA256_2,
        "denied_receipt_hash": SHA256_3,
        "counterfactual_admission_receipt_hash": SHA256_4,
        "recovery_artifact_digest": SHA256_5,
        "expected_manifest_blob": "2" * 40,
        "expected_skill_hashes_blob": "3" * 40,
        "expected_recovery_state_hash": SHA256_6,
        "allowed_changed_paths": [".claude.json", "skill-hashes.sha256"],
        "requested_transition": "COGNITIVE_CANONICAL_RECOVERY",
        "requested_authority": "RESTORE_PREVIOUSLY_ADMITTED_COGNITIVE_CONTROL_SURFACE",
        "expires_at": "2026-09-03T00:00:00Z",
        "operator_approval_digest": SHA256_7,
        "platform_governance_observation_digest": SHA256_8,
    }


class RecoveryAdmissionSchemaTests(TestCase):
    def test_request_schema_accepts_closed_valid_fixture(self) -> None:
        schema = load_schema(REQUEST_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(valid_request())

    def test_request_schema_rejects_authority_widening_field(self) -> None:
        request = valid_request()
        request["gcp_enabled"] = True
        errors = list(Draft202012Validator(load_schema(REQUEST_SCHEMA_PATH)).iter_errors(request))
        self.assertTrue(errors)


if __name__ == "__main__":
    main()
