from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PATH = REPO_ROOT / "scripts" / "cognitive-recovery-admission-cli.py"
R6_R7_TEST_PATH = REPO_ROOT / "sovereign-omega-v2/python/tests/test_cognitive_recovery_admission_r6_r7.py"
REPLAY_TEST_PATH = REPO_ROOT / "sovereign-omega-v2/python/tests/test_cognitive_recovery_admission_replay.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r6r7 = load_module("recovery_admission_cli_r6r7_fixture", R6_R7_TEST_PATH)
replay_contract = load_module("recovery_admission_cli_replay_contract", REPLAY_TEST_PATH)


class RecoveryAdmissionCliTests(TestCase):
    def setUp(self) -> None:
        self.fixture = r6r7.R6R7Fixture()
        self.tmp = TemporaryDirectory()
        self.inputs = Path(self.tmp.name)
        self.request_path = self.write_json("request.json", self.fixture.git.request)
        self.recovery_path = self.write_json("recovery.json", self.fixture.git.recovery_evidence)
        self.platform_path = self.write_json("platform.json", self.fixture.observation)
        self.approval_path = self.write_json("approval.json", self.fixture.approval)
        self.replay_path = self.write_json("replay.json", self.make_replay_state())

    def tearDown(self) -> None:
        self.tmp.cleanup()
        self.fixture.close()

    def make_replay_state(self) -> dict:
        value = {
            "schema_version": "1.0.0",
            "repository_id": "Aegis-Omega/AEGIS-OMEGA",
            "request_digest": self.fixture.git.request["request_id"],
            "candidate_sha": self.fixture.git.request["candidate_sha"],
            "operator_approval_digest": self.fixture.git.request["operator_approval_digest"],
            "state": "UNUSED",
            "generation": 7,
            "replay_state_digest": "0" * 64,
        }
        value["replay_state_digest"] = replay_contract.replay_digest(value)
        return value

    def write_json(self, name: str, value: dict) -> Path:
        path = self.inputs / name
        path.write_text(
            json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return path

    def run_cli(self, *, include_replay: bool = False) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(CLI_PATH),
            "--repo",
            str(self.fixture.git.repo),
            "--request",
            str(self.request_path),
            "--recovery-evidence",
            str(self.recovery_path),
            "--platform-observation",
            str(self.platform_path),
            "--operator-approval",
            str(self.approval_path),
        ]
        if include_replay:
            command.extend(["--replay-state", str(self.replay_path)])
        return subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_cli_emits_fail_closed_receipt_with_successful_evaluation_exit(self) -> None:
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertEqual(receipt["verified_gates"], ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"])
        self.assertEqual(receipt["violations"], ["R0:REPLAY_STATE_NOT_EVALUATED"])
        self.assertEqual(result.stderr, "")

    def test_cli_accepts_replay_state_without_granting_authority(self) -> None:
        result = self.run_cli(include_replay=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertEqual(receipt["verified_gates"], ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"])
        self.assertEqual(receipt["violations"], ["REPLAY:ATOMIC_CONSUMPTION_NOT_ESTABLISHED"])
        self.assertEqual(result.stderr, "")

    def test_invalid_replay_state_json_fails_closed_without_partial_receipt(self) -> None:
        self.replay_path.write_text("{not-json\n", encoding="utf-8")
        result = self.run_cli(include_replay=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("INPUT_ERROR", result.stderr)

    def test_cli_is_byte_deterministic_for_identical_inputs(self) -> None:
        first = self.run_cli()
        second = self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_cli_does_not_mutate_repository(self) -> None:
        before = subprocess.run(
            ["git", "-C", str(self.fixture.git.repo), "status", "--porcelain"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout
        result = self.run_cli(include_replay=True)
        after = subprocess.run(
            ["git", "-C", str(self.fixture.git.repo), "status", "--porcelain"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)

    def test_invalid_json_fails_closed_without_partial_receipt(self) -> None:
        self.request_path.write_text("{not-json\n", encoding="utf-8")
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("INPUT_ERROR", result.stderr)

    def test_missing_input_fails_closed_without_partial_receipt(self) -> None:
        self.approval_path.unlink()
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("INPUT_ERROR", result.stderr)


if __name__ == "__main__":
    main()
