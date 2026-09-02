from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_TEST_PATH = REPO_ROOT / "sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py"
VALIDATOR_PATH = REPO_ROOT / "scripts/validate-cognitive-recovery-admission.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_module("recovery_admission_base_tests", BASE_TEST_PATH)
validator = load_module("recovery_admission_hardening_validator", VALIDATOR_PATH)


class RecoveryAdmissionAuthorityHardeningTests(TestCase):
    def evaluate(self, fixture):
        return validator.evaluate(
            repo=fixture.repo,
            request=fixture.request,
            recovery_evidence=fixture.recovery_evidence,
            platform_observation={"state": "ENFORCED"},
            operator_approval={},
            verifier_code_digest=base.SHA256_6,
        )

    def test_partial_gate_set_can_never_mint_admission_authority(self) -> None:
        receipt = validator.build_receipt(
            request=base.valid_request(),
            verified_gates=["R0", "R1", "R2", "R3", "R4", "R5"],
            violations=[],
            platform_governance_state="ENFORCED",
            verifier_code_digest=base.SHA256_6,
        )
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")

    def test_repair_commit_itself_must_contain_pinned_repair_blob(self) -> None:
        fixture = base.MiniRecoveryRepo(validator)
        try:
            base.write_text(
                fixture.repo,
                base.ZERO_PARENT_VALIDATOR_PATH,
                "candidate-validator-v2-after-repair\n",
            )
            fixture.candidate = fixture._commit("candidate overrides repair validator")
            fixture.request["candidate_sha"] = fixture.candidate
            fixture.request["zero_parent_validator_blob"] = fixture.blob(
                fixture.candidate, base.ZERO_PARENT_VALIDATOR_PATH
            )
            fixture.request["expected_manifest_blob"] = fixture.blob(fixture.candidate, ".claude.json")
            fixture.request["expected_skill_hashes_blob"] = fixture.blob(
                fixture.candidate, "skill-hashes.sha256"
            )
            fixture.refresh_request_id()
            fixture.recovery_evidence = fixture.make_recovery_evidence()

            receipt = self.evaluate(fixture)
            self.assertTrue(
                any(item.startswith("R2:") for item in receipt["violations"]),
                receipt,
            )
            self.assertEqual(receipt["authority"], "NONE")
        finally:
            fixture.close()

    def test_allowlisted_manifest_cannot_enable_gcp_or_billing(self) -> None:
        fixture = base.MiniRecoveryRepo(validator)
        try:
            fixture.advance_candidate(
                ".claude.json",
                '{"state_hash":"recovered","gcp_enabled":true,"billing_enabled":true}\n',
                allow_path=True,
            )
            receipt = self.evaluate(fixture)
            self.assertTrue(
                any(item.startswith("R5:") for item in receipt["violations"]),
                receipt,
            )
            self.assertEqual(receipt["authority"], "NONE")
        finally:
            fixture.close()


if __name__ == "__main__":
    main()
