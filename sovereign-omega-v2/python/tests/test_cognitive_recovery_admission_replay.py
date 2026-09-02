from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
R6_R7_TEST_PATH = REPO_ROOT / "sovereign-omega-v2/python/tests/test_cognitive_recovery_admission_r6_r7.py"
VALIDATOR_PATH = REPO_ROOT / "scripts/validate-cognitive-recovery-admission.py"

REPLAY_DOMAIN = "AEGIS_COGNITIVE_RECOVERY_REPLAY_STATE_V1"


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


def replay_digest(value: dict) -> str:
    body = {key: item for key, item in value.items() if key != "replay_state_digest"}
    return hashlib.sha256(
        canonical_bytes({"domain": REPLAY_DOMAIN, "replay_state": body})
    ).hexdigest()


r6r7 = load_module("recovery_admission_replay_r6r7", R6_R7_TEST_PATH)
validator = load_module("recovery_admission_replay_validator", VALIDATOR_PATH)


class RecoveryAdmissionReplayTests(TestCase):
    def setUp(self) -> None:
        self.fixture = r6r7.R6R7Fixture()
        self.replay = self.make_replay_state()

    def tearDown(self) -> None:
        self.fixture.close()

    def make_replay_state(self, *, state: str = "UNUSED") -> dict:
        value = {
            "schema_version": "1.0.0",
            "repository_id": "Aegis-Omega/AEGIS-OMEGA",
            "request_digest": self.fixture.git.request["request_id"],
            "candidate_sha": self.fixture.git.request["candidate_sha"],
            "operator_approval_digest": self.fixture.git.request["operator_approval_digest"],
            "state": state,
            "generation": 7,
            "replay_state_digest": "0" * 64,
        }
        value["replay_state_digest"] = replay_digest(value)
        return value

    def evaluate(self, replay_state=None):
        return validator.evaluate(
            repo=self.fixture.git.repo,
            request=self.fixture.git.request,
            recovery_evidence=self.fixture.git.recovery_evidence,
            platform_observation=self.fixture.observation,
            operator_approval=self.fixture.approval,
            replay_state=self.replay if replay_state is None else replay_state,
            verifier_code_digest=r6r7.base.SHA256_6,
        )

    def assert_denied(self, receipt: dict, violation: str) -> None:
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertIn(violation, receipt["violations"], receipt)

    def test_unused_replay_state_verifies_but_atomic_consumption_remains_required(self) -> None:
        receipt = self.evaluate()
        self.assertEqual(
            receipt["verified_gates"],
            ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        )
        self.assertEqual(receipt["violations"], ["REPLAY:ATOMIC_CONSUMPTION_NOT_ESTABLISHED"])
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")

    def test_reserved_state_cannot_be_reused(self) -> None:
        replay = self.make_replay_state(state="RESERVED")
        self.assert_denied(self.evaluate(replay), "REPLAY:STATE_RESERVED")

    def test_consumed_state_cannot_be_reused(self) -> None:
        replay = self.make_replay_state(state="CONSUMED")
        self.assert_denied(self.evaluate(replay), "REPLAY:STATE_CONSUMED")

    def test_unknown_state_never_falls_back_to_unused(self) -> None:
        replay = self.make_replay_state(state="UNKNOWN")
        self.assert_denied(self.evaluate(replay), "REPLAY:STATE_UNKNOWN")

    def test_request_binding_mismatch_denies(self) -> None:
        replay = self.make_replay_state()
        replay["request_digest"] = "9" * 64
        replay["replay_state_digest"] = replay_digest(replay)
        self.assert_denied(self.evaluate(replay), "REPLAY:REQUEST_BINDING_MISMATCH")

    def test_candidate_binding_mismatch_denies(self) -> None:
        replay = self.make_replay_state()
        replay["candidate_sha"] = "9" * 40
        replay["replay_state_digest"] = replay_digest(replay)
        self.assert_denied(self.evaluate(replay), "REPLAY:CANDIDATE_BINDING_MISMATCH")

    def test_approval_binding_mismatch_denies(self) -> None:
        replay = self.make_replay_state()
        replay["operator_approval_digest"] = "9" * 64
        replay["replay_state_digest"] = replay_digest(replay)
        self.assert_denied(self.evaluate(replay), "REPLAY:APPROVAL_BINDING_MISMATCH")

    def test_replay_state_digest_mismatch_denies(self) -> None:
        replay = self.make_replay_state()
        replay["replay_state_digest"] = "9" * 64
        self.assert_denied(self.evaluate(replay), "REPLAY:DIGEST_MISMATCH")

    def test_missing_replay_state_stays_fail_closed(self) -> None:
        receipt = validator.evaluate(
            repo=self.fixture.git.repo,
            request=self.fixture.git.request,
            recovery_evidence=self.fixture.git.recovery_evidence,
            platform_observation=self.fixture.observation,
            operator_approval=self.fixture.approval,
            replay_state=None,
            verifier_code_digest=r6r7.base.SHA256_6,
        )
        self.assert_denied(receipt, "REPLAY:STATE_NOT_EVALUATED")


if __name__ == "__main__":
    main()
