from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "cudaq-reproducibility-spike.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")

CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"


class CudaqReproducibilityContract(unittest.TestCase):
    def test_actions_are_immutable_sha_pinned(self) -> None:
        self.assertIn(f"actions/checkout@{CHECKOUT_SHA}", TEXT)
        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_SHA}", TEXT)
        self.assertIn(f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", TEXT)
        self.assertNotRegex(TEXT, r"actions/(?:checkout|setup-python|upload-artifact)@v\d")

    def test_cudaq_top_level_version_is_pinned(self) -> None:
        self.assertIn("cudaq==0.15.1", TEXT)
        self.assertNotRegex(TEXT, r"pip install[^\n]*\bcudaq\s*(?:$|\\n)")

    def test_pull_request_runs_bind_exact_candidate_head(self) -> None:
        self.assertIn("pull_request:", TEXT)
        self.assertIn("CANDIDATE_SHA: ${{ github.event.pull_request.head.sha || github.sha }}", TEXT)
        self.assertRegex(TEXT, r"ref:\s*\$\{\{\s*env\.CANDIDATE_SHA\s*\}\}")
        self.assertIn("'head_sha': os.environ['CANDIDATE_SHA']", TEXT)
        self.assertIn("cudaq-reproducibility-spike-${{ env.CANDIDATE_SHA }}", TEXT)

    def test_environment_fingerprint_is_receipt_bound(self) -> None:
        required_literals = (
            "environment.lock.txt",
            "environment_lock_sha256",
            "python_version",
            "runner_os",
            "runner_arch",
        )
        for literal in required_literals:
            with self.subTest(literal=literal):
                self.assertIn(literal, TEXT)
        self.assertRegex(TEXT, r"sha256sum[^\n]*environment\.lock\.txt")

    def test_scope_remains_simulator_only_and_non_authoritative(self) -> None:
        self.assertIn("cudaq.set_target('qpp-cpu')", TEXT)
        self.assertIn("'gpu_acceleration_tested': False", TEXT)
        self.assertIn("'qpu_hardware_tested': False", TEXT)
        self.assertIn("'physics_claim_effect': 'NONE'", TEXT)
        self.assertIn("'authority_effect': 'NONE'", TEXT)


if __name__ == "__main__":
    unittest.main()
