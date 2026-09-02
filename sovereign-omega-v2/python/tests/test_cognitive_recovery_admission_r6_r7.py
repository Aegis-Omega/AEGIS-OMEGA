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


base = load_module("recovery_admission_task4_base", BASE_TEST_PATH)
validator = load_module("recovery_admission_task4_validator", VALIDATOR_PATH)

REQUIRED_CHECKS = [
    "Main branch enforcement",
    "aegis / automaton-2",
    "aegis / automaton-3",
]


class RecoveryAdmissionR6R7Tests(TestCase):
    def setUp(self) -> None:
        self.fixture = base.MiniRecoveryRepo(validator)

    def tearDown(self) -> None:
        self.fixture.close()

    def platform_observation(self, *, state: str = "ENFORCED") -> dict:
        observation = {
            "schema_version": "1.0.0",
            "repository_id": "Aegis-Omega/AEGIS-OMEGA",
            "observed_for_candidate_sha": self.fixture.request["candidate_sha"],
            "state": state,
            "ruleset_ids": [123],
            "required_checks": REQUIRED_CHECKS,
            "observation_digest": "0" * 64,
        }
        observation["observation_digest"] = validator.platform_observation_digest(observation)
        return observation

    def operator_approval(self) -> dict:
        approval = {
            "schema_version": "1.0.0",
            "request_digest": self.fixture.request["request_id"],
            "candidate_sha": self.fixture.request["candidate_sha"],
            "decision": "APPROVE_RECOVERY_ADMISSION_EVALUATION",
            "approval_digest": "0" * 64,
        }
        approval["approval_digest"] = validator.operator_approval_digest(approval)
        return approval

    def evaluate(self, observation=None, approval=None):
        observation = observation or self.platform_observation()
        approval = approval or self.operator_approval()
        self.fixture.request["platform_governance_observation_digest"] = observation["observation_digest"]
        self.fixture.request["operator_approval_digest"] = approval["approval_digest"]
        self.fixture.refresh_request_id()
        approval["request_digest"] = self.fixture.request["request_id"]
        approval["approval_digest"] = validator.operator_approval_digest(approval)
        self.fixture.request["operator_approval_digest"] = approval["approval_digest"]
        return validator.evaluate(
            repo=self.fixture.repo,
            request=self.fixture.request,
            recovery_evidence=self.fixture.recovery_evidence,
            platform_observation=observation,
            operator_approval=approval,
            verifier_code_digest=base.SHA256_6,
        )

    def assert_gate(self, receipt: dict, gate: str) -> None:
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertTrue(any(item.startswith(f"{gate}:") for item in receipt["violations"]), receipt)

    def test_valid_synthetic_r0_r7_evidence_grants_only_offline_admission(self) -> None:
        receipt = self.evaluate()
        self.assertEqual(receipt["outcome"], "RECOVERY_ADMISSION_GRANTED")
        self.assertEqual(receipt["authority"], "RECOVERY_ADMISSION_ONLY")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertEqual(receipt["verified_gates"], ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"])
        self.assertEqual(receipt["violations"], [])

    def test_disabled_and_unknown_platform_governance_deny_r6(self) -> None:
        for state in ("DISABLED", "UNKNOWN"):
            with self.subTest(state=state):
                observation = self.platform_observation(state=state)
                self.assert_gate(self.evaluate(observation=observation), "R6")

    def test_platform_observation_is_candidate_bound(self) -> None:
        observation = self.platform_observation()
        observation["observed_for_candidate_sha"] = "9" * 40
        observation["observation_digest"] = validator.platform_observation_digest(observation)
        self.assert_gate(self.evaluate(observation=observation), "R6")

    def test_platform_observation_digest_mismatch_denies_r6(self) -> None:
        observation = self.platform_observation()
        observation["observation_digest"] = "9" * 64
        self.assert_gate(self.evaluate(observation=observation), "R6")

    def test_platform_governance_requires_ruleset_and_required_checks(self) -> None:
        observation = self.platform_observation()
        observation["ruleset_ids"] = []
        observation["required_checks"] = ["aegis / automaton-2"]
        observation["observation_digest"] = validator.platform_observation_digest(observation)
        self.assert_gate(self.evaluate(observation=observation), "R6")

    def test_operator_approval_fields_are_all_bound(self) -> None:
        mutations = {
            "request_digest": "9" * 64,
            "candidate_sha": "9" * 40,
            "decision": "DENY",
            "approval_digest": "9" * 64,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                observation = self.platform_observation()
                approval = self.operator_approval()
                self.fixture.request["platform_governance_observation_digest"] = observation["observation_digest"]
                self.fixture.request["operator_approval_digest"] = approval["approval_digest"]
                self.fixture.refresh_request_id()
                approval["request_digest"] = self.fixture.request["request_id"]
                approval["approval_digest"] = validator.operator_approval_digest(approval)
                self.fixture.request["operator_approval_digest"] = approval["approval_digest"]
                approval[field] = value
                receipt = validator.evaluate(
                    repo=self.fixture.repo,
                    request=self.fixture.request,
                    recovery_evidence=self.fixture.recovery_evidence,
                    platform_observation=observation,
                    operator_approval=approval,
                    verifier_code_digest=base.SHA256_6,
                )
                self.assert_gate(receipt, "R7")


if __name__ == "__main__":
    main()
