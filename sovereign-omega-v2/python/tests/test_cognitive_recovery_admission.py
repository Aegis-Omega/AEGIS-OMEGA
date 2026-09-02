from __future__ import annotations

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


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def write_file(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def blob_sha(repo: Path, ref: str, path: str) -> str:
    return git(repo, "rev-parse", f"{ref}:{path}")


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
        "expires_at": "2099-09-03T00:00:00Z",
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

    def test_receipt_schema_accepts_closed_valid_fixture(self) -> None:
        schema = load_schema(RECEIPT_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(valid_receipt())

    def test_receipt_schema_rejects_mutation_authority_widening(self) -> None:
        receipt = valid_receipt()
        receipt["mutation_authority"] = "MAIN_WRITE"
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


class RecoveryAdmissionReceiptDigestTests(TestCase):
    def test_build_receipt_is_deterministic_and_domain_separated(self) -> None:
        validator = load_module("recovery_admission_receipt", VALIDATOR_PATH)
        request = valid_request()
        kwargs = {
            "request": request,
            "platform_governance_state": "ENFORCED",
            "verified_gates": ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"],
            "violations": [],
            "outcome": "RECOVERY_ADMISSION_GRANTED",
            "verifier_code_digest": SHA256_6,
        }
        first = validator.build_receipt(**kwargs)
        second = validator.build_receipt(**kwargs)
        self.assertEqual(first, second)
        self.assertNotIn("timestamp", first)
        self.assertEqual(first["mutation_authority"], "NONE")
        self.assertEqual(first["authority"], "RECOVERY_ADMISSION_ONLY")

        body = dict(first)
        observed_hash = body.pop("receipt_hash")
        expected_hash = validator.sha256_hex(
            validator.canonical_bytes({"domain": validator.RECEIPT_DOMAIN, "receipt": body})
        )
        self.assertEqual(observed_hash, expected_hash)
        Draft202012Validator(load_schema(RECEIPT_SCHEMA_PATH)).validate(first)

    def test_denied_receipt_is_schema_valid_and_has_no_authority(self) -> None:
        validator = load_module("recovery_admission_denied_receipt", VALIDATOR_PATH)
        receipt = validator.build_receipt(
            request=valid_request(),
            platform_governance_state="UNKNOWN",
            verified_gates=["R0"],
            violations=["R6: platform governance not enforced"],
            outcome="DENIED",
            verifier_code_digest=SHA256_6,
        )
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        Draft202012Validator(load_schema(RECEIPT_SCHEMA_PATH)).validate(receipt)


class RecoveryAdmissionEvaluationTests(TestCase):
    def make_fixture(self, *, unrelated: bool = False, gcp_path: bool = False):
        validator = load_module("recovery_admission_fixture", VALIDATOR_PATH)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.name", "AEGIS Test")
        git(repo, "config", "user.email", "aegis-test@example.invalid")

        write_file(repo, "control.txt", "trusted\n")
        write_file(repo, "scripts/validate-automaton2.py", "print('trusted validator')\n")
        write_file(repo, "sovereign-omega-v2/python/tests/test_automaton2.py", "print('trusted test')\n")
        write_file(repo, ".github/workflows/cognitive-manifest-refresh.yml", "name: trusted-writer\n")
        write_file(repo, ".claude.json", '{"state_hash":"trusted"}\n')
        write_file(repo, "skill-hashes.sha256", "trusted skill hashes\n")
        trusted = commit_all(repo, "trusted control plane")

        write_file(repo, "parent.txt", "recovery parent\n")
        recovery_parent = commit_all(repo, "recovery parent")

        write_file(repo, ".claude.json", '{"state_hash":"denied"}\n')
        write_file(repo, "skill-hashes.sha256", "denied skill hashes\n")
        denied = commit_all(repo, "denied base")

        write_file(repo, ".claude.json", '{"state_hash":"recovered"}\n')
        write_file(repo, "skill-hashes.sha256", "recovered skill hashes\n")
        write_file(repo, "scripts/validate-automaton2.py", "print('zero-parent repair validator')\n")
        write_file(repo, "sovereign-omega-v2/python/tests/test_automaton2.py", "print('zero-parent repair test')\n")
        write_file(repo, ".github/workflows/cognitive-manifest-refresh.yml", "name: hardened-writer\n")
        if unrelated:
            write_file(repo, "unrelated.txt", "not part of recovery\n")
        if gcp_path:
            write_file(repo, "gcp/provider.json", '{"enabled":true,"billing":true}\n')
        candidate = commit_all(repo, "recovery candidate")

        allowed = [
            ".claude.json",
            ".github/workflows/cognitive-manifest-refresh.yml",
            "scripts/validate-automaton2.py",
            "skill-hashes.sha256",
            "sovereign-omega-v2/python/tests/test_automaton2.py",
        ]
        if gcp_path:
            # Deliberately malicious allowlist widening: R5 must still deny.
            allowed.append("gcp/provider.json")

        request = {
            "schema_version": "1.0.0",
            "request_id": "0" * 64,
            "repository_id": "Aegis-Omega/AEGIS-OMEGA",
            "trusted_control_plane_sha": trusted,
            "recovery_parent_sha": recovery_parent,
            "denied_base_sha": denied,
            "candidate_sha": candidate,
            "zero_parent_repair_sha": candidate,
            "zero_parent_validator_blob": blob_sha(repo, candidate, "scripts/validate-automaton2.py"),
            "zero_parent_test_blob": blob_sha(repo, candidate, "sovereign-omega-v2/python/tests/test_automaton2.py"),
            "writer_workflow_blob": blob_sha(repo, candidate, ".github/workflows/cognitive-manifest-refresh.yml"),
            "recovery_receipt_hash": SHA256_2,
            "denied_receipt_hash": SHA256_3,
            "counterfactual_admission_receipt_hash": SHA256_4,
            "recovery_artifact_digest": SHA256_5,
            "expected_manifest_blob": blob_sha(repo, candidate, ".claude.json"),
            "expected_skill_hashes_blob": blob_sha(repo, candidate, "skill-hashes.sha256"),
            "expected_recovery_state_hash": SHA256_6,
            "allowed_changed_paths": sorted(allowed),
            "requested_transition": "COGNITIVE_CANONICAL_RECOVERY",
            "requested_authority": "RESTORE_PREVIOUSLY_ADMITTED_COGNITIVE_CONTROL_SURFACE",
            "expires_at": "2099-09-03T00:00:00Z",
            "operator_approval_digest": SHA256_7,
            "platform_governance_observation_digest": SHA256_8,
        }
        request["request_id"] = validator.request_digest(request)

        recovery_evidence = {
            "receipt_kind": "AEGIS_COGNITIVE_RECOVERY_RECEIPT_V1",
            "outcome": "RECOVERY_VERIFIED",
            "production_admission": "NONE",
            "authority": "NONE",
            "candidate_sha": request["candidate_sha"],
            "denied_base_sha": request["denied_base_sha"],
            "recovery_parent_sha": request["recovery_parent_sha"],
            "receipt_hash": request["recovery_receipt_hash"],
            "denied_receipt_hash": request["denied_receipt_hash"],
            "recovery_validation_receipt_hash": request["counterfactual_admission_receipt_hash"],
            "artifact_digest": request["recovery_artifact_digest"],
        }
        platform_observation = {
            "schema_version": "1.0.0",
            "repository_id": request["repository_id"],
            "observed_for_candidate_sha": request["candidate_sha"],
            "state": "ENFORCED",
            "ruleset_ids": [123],
            "required_checks": [
                "aegis / automaton-2",
                "aegis / automaton-3",
                "Main branch enforcement",
            ],
            "observation_digest": request["platform_governance_observation_digest"],
        }
        operator_approval = {
            "schema_version": "1.0.0",
            "repository_id": request["repository_id"],
            "request_digest": request["request_id"],
            "candidate_sha": request["candidate_sha"],
            "decision": "APPROVE_ONE_EXACT_CANONICAL_RECOVERY_TRANSITION",
            "approval_digest": request["operator_approval_digest"],
        }
        return validator, repo, request, recovery_evidence, platform_observation, operator_approval

    def evaluate_fixture(self, **fixture_options):
        validator, repo, request, evidence, observation, approval = self.make_fixture(**fixture_options)
        receipt = validator.evaluate(
            repo=repo,
            request=request,
            recovery_evidence=evidence,
            platform_observation=observation,
            operator_approval=approval,
            verifier_code_digest=SHA256_6,
        )
        return validator, repo, request, evidence, observation, approval, receipt

    def test_clean_fixture_has_no_r0_through_r5_violations(self) -> None:
        *_, receipt = self.evaluate_fixture()
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertFalse(any(v.startswith(tuple(f"R{i}:" for i in range(6))) for v in receipt["violations"]))
        self.assertTrue(any(v.startswith("R6:") for v in receipt["violations"]))
        self.assertTrue(any(v.startswith("R7:") for v in receipt["violations"]))

    def test_r0_request_self_hash_mismatch_denies(self) -> None:
        validator, repo, request, evidence, observation, approval = self.make_fixture()
        request["request_id"] = "9" * 64
        receipt = validator.evaluate(
            repo=repo,
            request=request,
            recovery_evidence=evidence,
            platform_observation=observation,
            operator_approval=approval,
            verifier_code_digest=SHA256_6,
        )
        self.assertTrue(any(v.startswith("R0:") for v in receipt["violations"]))

    def test_r1_unresolvable_trusted_root_denies(self) -> None:
        validator, repo, request, evidence, observation, approval = self.make_fixture()
        request["trusted_control_plane_sha"] = "9" * 40
        request["request_id"] = validator.request_digest(request)
        receipt = validator.evaluate(
            repo=repo,
            request=request,
            recovery_evidence=evidence,
            platform_observation=observation,
            operator_approval=approval,
            verifier_code_digest=SHA256_6,
        )
        self.assertTrue(any(v.startswith("R1:") for v in receipt["violations"]))

    def test_r2_exact_validator_blob_mismatch_denies(self) -> None:
        validator, repo, request, evidence, observation, approval = self.make_fixture()
        request["zero_parent_validator_blob"] = "9" * 40
        request["request_id"] = validator.request_digest(request)
        receipt = validator.evaluate(
            repo=repo,
            request=request,
            recovery_evidence=evidence,
            platform_observation=observation,
            operator_approval=approval,
            verifier_code_digest=SHA256_6,
        )
        self.assertTrue(any(v.startswith("R2:") for v in receipt["violations"]))

    def test_r3_unrelated_candidate_path_denies(self) -> None:
        *_, receipt = self.evaluate_fixture(unrelated=True)
        self.assertTrue(any(v.startswith("R3:") for v in receipt["violations"]))

    def test_r4_recovery_artifact_binding_mismatch_denies(self) -> None:
        validator, repo, request, evidence, observation, approval = self.make_fixture()
        evidence["artifact_digest"] = "9" * 64
        receipt = validator.evaluate(
            repo=repo,
            request=request,
            recovery_evidence=evidence,
            platform_observation=observation,
            operator_approval=approval,
            verifier_code_digest=SHA256_6,
        )
        self.assertTrue(any(v.startswith("R4:") for v in receipt["violations"]))

    def test_r5_gcp_authority_widening_denies_even_if_allowlisted(self) -> None:
        *_, receipt = self.evaluate_fixture(gcp_path=True)
        self.assertTrue(any(v.startswith("R5:") for v in receipt["violations"]))


if __name__ == "__main__":
    main()
