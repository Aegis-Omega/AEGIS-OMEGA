from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "cognitive-recovery-admission-request.v1.schema.json"
RECEIPT_SCHEMA_PATH = REPO_ROOT / "schemas" / "cognitive-recovery-admission-receipt.v1.schema.json"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate-cognitive-recovery-admission.py"

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

ZERO_PARENT_VALIDATOR_PATH = "scripts/validate-automaton2.py"
ZERO_PARENT_TEST_PATH = "sovereign-omega-v2/python/tests/test_automaton2.py"
WRITER_WORKFLOW_PATH = ".github/workflows/cognitive-manifest-refresh.yml"


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def valid_receipt() -> dict:
    return {
        "receipt_kind": "AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1",
        "schema_version": "1.0.0",
        "request_digest": SHA256_1,
        "repository_id": "Aegis-Omega/AEGIS-OMEGA",
        "candidate_sha": SHA1_D,
        "denied_base_sha": SHA1_C,
        "trusted_control_plane_sha": SHA1_A,
        "recovery_parent_sha": SHA1_B,
        "recovery_receipt_hash": SHA256_2,
        "writer_workflow_blob": "1" * 40,
        "platform_governance_observation_digest": SHA256_8,
        "platform_governance_state": "ENFORCED",
        "operator_approval_digest": SHA256_7,
        "verified_gates": ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        "violations": [],
        "outcome": "RECOVERY_ADMISSION_GRANTED",
        "scope": "ONE_EXACT_CANONICAL_RECOVERY_TRANSITION",
        "authority": "RECOVERY_ADMISSION_ONLY",
        "mutation_authority": "NONE",
        "verifier_identity": "offline:aegis-cognitive-recovery-admission-v1",
        "verifier_code_digest": SHA256_6,
        "receipt_hash": SHA256_5,
    }


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def write_text(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class MiniRecoveryRepo:
    def __init__(self, validator) -> None:
        self.validator = validator
        self.tmp = TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        run_git(self.repo, "init")
        run_git(self.repo, "config", "user.email", "aegis-test@example.invalid")
        run_git(self.repo, "config", "user.name", "AEGIS Test")

        write_text(self.repo, ZERO_PARENT_VALIDATOR_PATH, "trusted-validator\n")
        write_text(self.repo, ZERO_PARENT_TEST_PATH, "trusted-test\n")
        write_text(self.repo, WRITER_WORKFLOW_PATH, "trusted-writer\n")
        write_text(self.repo, ".github/workflows/automaton-2.yml", "trusted-automaton-workflow\n")
        write_text(self.repo, "scripts/build-cognitive-manifest.py", "trusted-builder\n")
        write_text(self.repo, "schemas/cognitive-state.v1.schema.json", "{}\n")
        write_text(self.repo, ".claude.json", '{"state_hash":"trusted"}\n')
        write_text(self.repo, "skill-hashes.sha256", "trusted-skills\n")
        self.trusted = self._commit("trusted root")

        run_git(self.repo, "checkout", "-b", "incident")
        run_git(self.repo, "commit", "--allow-empty", "-m", "recovery parent")
        self.recovery_parent = run_git(self.repo, "rev-parse", "HEAD")
        write_text(self.repo, ".claude.json", '{"state_hash":"malformed"}\n')
        write_text(self.repo, "skill-hashes.sha256", "malformed-skills\n")
        self.denied_base = self._commit("denied base")

        run_git(self.repo, "checkout", "-b", "repair", self.trusted)
        write_text(self.repo, ZERO_PARENT_VALIDATOR_PATH, "zero-parent-validator-v1\n")
        write_text(self.repo, ZERO_PARENT_TEST_PATH, "zero-parent-test-v1\n")
        write_text(self.repo, WRITER_WORKFLOW_PATH, "single-writer-v1\n")
        self.zero_parent_repair = self._commit("zero parent repair")
        write_text(self.repo, ".claude.json", '{"state_hash":"recovered"}\n')
        write_text(self.repo, "skill-hashes.sha256", "recovered-skills\n")
        self.candidate = self._commit("recovery candidate")

        self.request = {
            "schema_version": "1.0.0",
            "request_id": "0" * 64,
            "repository_id": "Aegis-Omega/AEGIS-OMEGA",
            "trusted_control_plane_sha": self.trusted,
            "recovery_parent_sha": self.recovery_parent,
            "denied_base_sha": self.denied_base,
            "candidate_sha": self.candidate,
            "zero_parent_repair_sha": self.zero_parent_repair,
            "zero_parent_validator_blob": self.blob(self.candidate, ZERO_PARENT_VALIDATOR_PATH),
            "zero_parent_test_blob": self.blob(self.candidate, ZERO_PARENT_TEST_PATH),
            "writer_workflow_blob": self.blob(self.candidate, WRITER_WORKFLOW_PATH),
            "recovery_receipt_hash": SHA256_2,
            "denied_receipt_hash": SHA256_3,
            "counterfactual_admission_receipt_hash": SHA256_4,
            "recovery_artifact_digest": SHA256_5,
            "expected_manifest_blob": self.blob(self.candidate, ".claude.json"),
            "expected_skill_hashes_blob": self.blob(self.candidate, "skill-hashes.sha256"),
            "expected_recovery_state_hash": SHA256_6,
            "allowed_changed_paths": sorted({
                ".claude.json",
                "skill-hashes.sha256",
                ZERO_PARENT_VALIDATOR_PATH,
                ZERO_PARENT_TEST_PATH,
                WRITER_WORKFLOW_PATH,
            }),
            "requested_transition": "COGNITIVE_CANONICAL_RECOVERY",
            "requested_authority": "RESTORE_PREVIOUSLY_ADMITTED_COGNITIVE_CONTROL_SURFACE",
            "expires_at": "2026-09-03T00:00:00Z",
            "operator_approval_digest": SHA256_7,
            "platform_governance_observation_digest": SHA256_8,
        }
        self.refresh_request_id()
        self.recovery_evidence = self.make_recovery_evidence()

    def close(self) -> None:
        self.tmp.cleanup()

    def _commit(self, message: str) -> str:
        run_git(self.repo, "add", "-A")
        run_git(self.repo, "commit", "-m", message)
        return run_git(self.repo, "rev-parse", "HEAD")

    def blob(self, commit: str, path: str) -> str:
        return run_git(self.repo, "rev-parse", f"{commit}:{path}")

    def refresh_request_id(self) -> None:
        self.request["request_id"] = self.validator.request_digest(self.request)

    def make_recovery_evidence(self) -> dict:
        return {
            "receipt_kind": "AEGIS_COGNITIVE_RECOVERY_RECEIPT_V1",
            "outcome": "RECOVERY_VERIFIED",
            "production_admission": "NONE",
            "authority": "NONE",
            "candidate_sha": self.request["candidate_sha"],
            "denied_base_sha": self.request["denied_base_sha"],
            "recovery_parent_sha": self.request["recovery_parent_sha"],
            "receipt_hash": self.request["recovery_receipt_hash"],
            "denied_receipt_hash": self.request["denied_receipt_hash"],
            "recovery_validation_receipt_hash": self.request["counterfactual_admission_receipt_hash"],
            "artifact_digest": self.request["recovery_artifact_digest"],
        }

    def advance_candidate(self, path: str, content: str, *, allow_path: bool) -> None:
        write_text(self.repo, path, content)
        self.candidate = self._commit(f"candidate change {path}")
        self.request["candidate_sha"] = self.candidate
        self.request["expected_manifest_blob"] = self.blob(self.candidate, ".claude.json")
        self.request["expected_skill_hashes_blob"] = self.blob(self.candidate, "skill-hashes.sha256")
        if allow_path and path not in self.request["allowed_changed_paths"]:
            self.request["allowed_changed_paths"] = sorted([*self.request["allowed_changed_paths"], path])
        self.refresh_request_id()
        self.recovery_evidence = self.make_recovery_evidence()


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

    def test_receipt_schema_accepts_authority_bounded_fixture(self) -> None:
        schema = load_schema(RECEIPT_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(valid_receipt())

    def test_receipt_schema_rejects_mutation_authority(self) -> None:
        receipt = valid_receipt()
        receipt["mutation_authority"] = "WRITE_MAIN"
        errors = list(Draft202012Validator(load_schema(RECEIPT_SCHEMA_PATH)).iter_errors(receipt))
        self.assertTrue(errors)


class RecoveryAdmissionDigestTests(TestCase):
    def test_request_digest_ignores_only_request_id(self) -> None:
        validator = load_module("recovery_admission", VALIDATOR_PATH)
        left = valid_request()
        right = valid_request()
        right["request_id"] = "9" * 64
        self.assertEqual(validator.request_digest(left), validator.request_digest(right))
        right["candidate_sha"] = "8" * 40
        self.assertNotEqual(validator.request_digest(left), validator.request_digest(right))

    def test_canonical_json_rejects_nan(self) -> None:
        validator = load_module("recovery_admission_nan", VALIDATOR_PATH)
        with self.assertRaises(ValueError):
            validator.canonical_bytes({"x": float("nan")})

    def test_receipt_sorts_and_deduplicates_gate_sets(self) -> None:
        validator = load_module("recovery_admission_receipt_set", VALIDATOR_PATH)
        request = valid_request()
        first = validator.build_receipt(
            request=request,
            verified_gates=["R3", "R1", "R3"],
            violations=["R5:z", "R2:a", "R5:z"],
            platform_governance_state="UNKNOWN",
            verifier_code_digest=SHA256_6,
        )
        second = validator.build_receipt(
            request=request,
            verified_gates=["R1", "R3"],
            violations=["R2:a", "R5:z"],
            platform_governance_state="UNKNOWN",
            verifier_code_digest=SHA256_6,
        )
        self.assertEqual(first["verified_gates"], ["R1", "R3"])
        self.assertEqual(first["violations"], ["R2:a", "R5:z"])
        self.assertEqual(first["receipt_hash"], second["receipt_hash"])


class RecoveryAdmissionR0R5Tests(TestCase):
    def setUp(self) -> None:
        self.validator = load_module(f"recovery_admission_git_{self._testMethodName}", VALIDATOR_PATH)
        self.fixture = MiniRecoveryRepo(self.validator)

    def tearDown(self) -> None:
        self.fixture.close()

    def evaluate(self, request=None, recovery_evidence=None):
        return self.validator.evaluate(
            repo=self.fixture.repo,
            request=request or self.fixture.request,
            recovery_evidence=recovery_evidence or self.fixture.recovery_evidence,
            platform_observation={"state": "ENFORCED"},
            operator_approval={},
            verifier_code_digest=SHA256_6,
        )

    def assert_gate_violation(self, receipt: dict, gate: str) -> None:
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertTrue(any(item.startswith(f"{gate}:") for item in receipt["violations"]), receipt)

    def test_valid_r0_r5_fixture_stays_denied_until_r6_r7(self) -> None:
        receipt = self.evaluate()
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["verified_gates"], ["R0", "R1", "R2", "R3", "R4", "R5"])
        self.assertIn("R6:NOT_EVALUATED", receipt["violations"])
        self.assertIn("R7:NOT_EVALUATED", receipt["violations"])
        self.assertEqual(receipt["platform_governance_state"], "ENFORCED")
        self.assertEqual(receipt["mutation_authority"], "NONE")

    def test_request_id_mismatch_denies(self) -> None:
        request = copy.deepcopy(self.fixture.request)
        request["request_id"] = "9" * 64
        self.assert_gate_violation(self.evaluate(request=request), "R0")

    def test_declared_recovery_parent_must_match_denied_base_parent(self) -> None:
        request = copy.deepcopy(self.fixture.request)
        request["recovery_parent_sha"] = self.fixture.trusted
        request["request_id"] = self.validator.request_digest(request)
        self.assert_gate_violation(self.evaluate(request=request), "R1")

    def test_candidate_must_descend_from_exact_zero_parent_repair(self) -> None:
        request = copy.deepcopy(self.fixture.request)
        request["zero_parent_repair_sha"] = self.fixture.recovery_parent
        request["request_id"] = self.validator.request_digest(request)
        self.assert_gate_violation(self.evaluate(request=request), "R2")

    def test_zero_parent_validator_blob_mismatch_denies(self) -> None:
        request = copy.deepcopy(self.fixture.request)
        request["zero_parent_validator_blob"] = "9" * 40
        request["request_id"] = self.validator.request_digest(request)
        self.assert_gate_violation(self.evaluate(request=request), "R2")

    def test_unrelated_path_denies_even_when_other_evidence_matches(self) -> None:
        self.fixture.advance_candidate("unrelated.txt", "unrelated\n", allow_path=False)
        self.assert_gate_violation(self.evaluate(), "R3")

    def test_recovery_artifact_digest_mismatch_denies(self) -> None:
        evidence = copy.deepcopy(self.fixture.recovery_evidence)
        evidence["artifact_digest"] = "9" * 64
        self.assert_gate_violation(self.evaluate(recovery_evidence=evidence), "R4")

    def test_gcp_or_provider_authority_path_always_denies(self) -> None:
        self.fixture.advance_candidate("gcp/provider.json", '{"enabled":true,"billing":true}\n', allow_path=True)
        self.assert_gate_violation(self.evaluate(), "R5")


if __name__ == "__main__":
    main()
