from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_TEST_PATH = REPO_ROOT / "sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate-cognitive-recovery-admission.py"

PLATFORM_DOMAIN = "AEGIS_PLATFORM_GOVERNANCE_OBSERVATION_V1"
APPROVAL_DOMAIN = "AEGIS_RECOVERY_OPERATOR_APPROVAL_V1"
REQUIRED_CHECKS = [
    "Main branch enforcement",
    "aegis / automaton-2",
    "aegis / automaton-3",
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def domain_digest(domain: str, envelope_key: str, value: dict, self_field: str) -> str:
    body = {key: item for key, item in value.items() if key != self_field}
    return hashlib.sha256(
        canonical_bytes({"domain": domain, envelope_key: body})
    ).hexdigest()


base = load_module("recovery_admission_task4_base", BASE_TEST_PATH)
validator = load_module("recovery_admission_task4_validator", VALIDATOR_PATH)


class R6R7Fixture:
    def __init__(self) -> None:
        self.git = base.MiniRecoveryRepo(validator)
        self.observation = self.make_observation()
        self.approval: dict = {}
        self.rebind_observation_and_request()
        self.rebind_approval()

    def close(self) -> None:
        self.git.close()

    def make_observation(self, *, state: str = "ENFORCED") -> dict:
        observation = {
            "schema_version": "1.0.0",
            "repository_id": "Aegis-Omega/AEGIS-OMEGA",
            "observed_for_candidate_sha": self.git.request["candidate_sha"],
            "state": state,
            "observed_at": "2026-09-02T15:30:00Z",
            "ruleset_ids": [123],
            "required_checks": list(REQUIRED_CHECKS),
            "observation_digest": "0" * 64,
        }
        observation["observation_digest"] = domain_digest(
            PLATFORM_DOMAIN, "observation", observation, "observation_digest"
        )
        return observation

    def rebind_observation_and_request(self) -> None:
        self.observation["observation_digest"] = domain_digest(
            PLATFORM_DOMAIN, "observation", self.observation, "observation_digest"
        )
        self.git.request["platform_governance_observation_digest"] = self.observation[
            "observation_digest"
        ]
        self.git.refresh_request_id()

    def rebind_approval(self) -> None:
        self.approval = {
            "schema_version": "1.0.0",
            "request_digest": self.git.request["request_id"],
            "candidate_sha": self.git.request["candidate_sha"],
            "decision": "APPROVE_RECOVERY_ADMISSION_EVALUATION",
            "approval_digest": "0" * 64,
        }
        self.approval["approval_digest"] = domain_digest(
            APPROVAL_DOMAIN, "approval", self.approval, "approval_digest"
        )
        self.git.request["operator_approval_digest"] = self.approval["approval_digest"]

    def rebind_all(self) -> None:
        self.rebind_observation_and_request()
        self.rebind_approval()

    def evaluate(self):
        return validator.evaluate(
            repo=self.git.repo,
            request=self.git.request,
            recovery_evidence=self.git.recovery_evidence,
            platform_observation=self.observation,
            operator_approval=self.approval,
            verifier_code_digest=base.SHA256_6,
        )


class RecoveryAdmissionR6R7Tests(TestCase):
    def setUp(self) -> None:
        self.fixture = R6R7Fixture()

    def tearDown(self) -> None:
        self.fixture.close()

    def assert_specific_gate_violation(self, receipt: dict, expected: str) -> None:
        gate = expected.split(":", 1)[0]
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertIn(expected, receipt["violations"], receipt)
        self.assertNotIn(f"{gate}:NOT_EVALUATED", receipt["violations"], receipt)
        self.assertNotIn(gate, receipt["verified_gates"], receipt)

    def test_valid_r6_r7_evidence_verifies_but_replay_barrier_keeps_denied(self) -> None:
        receipt = self.fixture.evaluate()
        self.assertEqual(
            receipt["verified_gates"],
            ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        )
        self.assertEqual(receipt["violations"], ["R0:REPLAY_STATE_NOT_EVALUATED"])
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertEqual(receipt["platform_governance_state"], "ENFORCED")

    def test_disabled_governance_denies_r6_with_valid_digest(self) -> None:
        self.fixture.observation["state"] = "DISABLED"
        self.fixture.rebind_all()
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R6:PLATFORM_STATE_NOT_ENFORCED"
        )

    def test_unknown_governance_denies_r6_with_valid_digest(self) -> None:
        self.fixture.observation["state"] = "UNKNOWN"
        self.fixture.rebind_all()
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R6:PLATFORM_STATE_NOT_ENFORCED"
        )

    def test_platform_observation_candidate_binding_mismatch_denies_r6(self) -> None:
        self.fixture.observation["observed_for_candidate_sha"] = "9" * 40
        self.fixture.rebind_all()
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R6:CANDIDATE_BINDING_MISMATCH"
        )

    def test_platform_observation_digest_mismatch_denies_r6(self) -> None:
        self.fixture.observation["observation_digest"] = "9" * 64
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R6:OBSERVATION_DIGEST_MISMATCH"
        )

    def test_platform_observation_after_request_expiry_denies_r6(self) -> None:
        self.fixture.observation["observed_at"] = "2026-09-03T00:00:01Z"
        self.fixture.rebind_all()
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R6:OBSERVATION_AFTER_REQUEST_EXPIRY"
        )

    def test_platform_governance_requires_ruleset_ids(self) -> None:
        self.fixture.observation["ruleset_ids"] = []
        self.fixture.rebind_all()
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R6:RULESET_IDS_MISSING"
        )

    def test_platform_governance_requires_all_required_checks(self) -> None:
        self.fixture.observation["required_checks"] = REQUIRED_CHECKS[:-1]
        self.fixture.rebind_all()
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R6:REQUIRED_CHECKS_MISSING"
        )

    def test_operator_approval_request_digest_binding_mismatch_denies_r7(self) -> None:
        self.fixture.approval["request_digest"] = "9" * 64
        self.fixture.approval["approval_digest"] = domain_digest(
            APPROVAL_DOMAIN, "approval", self.fixture.approval, "approval_digest"
        )
        self.fixture.git.request["operator_approval_digest"] = self.fixture.approval[
            "approval_digest"
        ]
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R7:REQUEST_BINDING_MISMATCH"
        )

    def test_operator_approval_candidate_binding_mismatch_denies_r7(self) -> None:
        self.fixture.approval["candidate_sha"] = "9" * 40
        self.fixture.approval["approval_digest"] = domain_digest(
            APPROVAL_DOMAIN, "approval", self.fixture.approval, "approval_digest"
        )
        self.fixture.git.request["operator_approval_digest"] = self.fixture.approval[
            "approval_digest"
        ]
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R7:CANDIDATE_BINDING_MISMATCH"
        )

    def test_operator_approval_decision_mismatch_denies_r7(self) -> None:
        self.fixture.approval["decision"] = "APPROVE_SOMETHING_ELSE"
        self.fixture.approval["approval_digest"] = domain_digest(
            APPROVAL_DOMAIN, "approval", self.fixture.approval, "approval_digest"
        )
        self.fixture.git.request["operator_approval_digest"] = self.fixture.approval[
            "approval_digest"
        ]
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R7:DECISION_NOT_APPROVED"
        )

    def test_operator_approval_digest_mismatch_denies_r7(self) -> None:
        self.fixture.approval["approval_digest"] = "9" * 64
        self.assert_specific_gate_violation(
            self.fixture.evaluate(), "R7:APPROVAL_DIGEST_MISMATCH"
        )


if __name__ == "__main__":
    main()
