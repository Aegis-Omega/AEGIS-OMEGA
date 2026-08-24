"""Evidence-pipeline integration guards kept outside the canonical test runner.

The canonical runner executes the security falsifiers in
``test_effect_chain_main_integration.py``.  These two meta-tests invoke that
runner and its receipt validator, so keeping them separate prevents recursion.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class EffectChainEvidenceIntegrationTests(unittest.TestCase):
    def test_canonical_runner_covers_pr1_through_pr4_and_security_guards(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            summary_path = tmp / "summary.json"
            log_path = tmp / "tests.log"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/run-automaton3-tests.py",
                    "--output",
                    str(summary_path),
                    "--log",
                    str(log_path),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(129, summary["expected_test_count"])
        self.assertEqual(129, summary["actual_test_count"])
        self.assertTrue(summary["verify_effect_asserted"])
        self.assertTrue(summary["effect_receipt_verifier_gated_asserted"])
        self.assertTrue(summary["complete_verification_asserted"])
        self.assertTrue(summary["complete_verification_receipt_binding_asserted"])
        self.assertTrue(summary["effect_chain_security_guards_asserted"])
        self.assertTrue(
            summary["concurrent_file_mutation_snapshot_proof_not_established_asserted"]
        )

    def test_candidate_receipt_reports_current_effect_chain_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            summary_path = tmp / "summary.json"
            log_path = tmp / "tests.log"
            mcp_log_path = tmp / "mcp.log"
            receipt_path = tmp / "receipt.json"
            manifest_path = tmp / "manifest.json"

            runner = subprocess.run(
                [
                    sys.executable,
                    "scripts/run-automaton3-tests.py",
                    "--output",
                    str(summary_path),
                    "--log",
                    str(log_path),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, runner.returncode, runner.stdout + runner.stderr)
            mcp_log_path.write_text("AUTOMATON3_MCP_PASS\n", encoding="utf-8")

            validator = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate-automaton3.py",
                    "--candidate-sha",
                    "a" * 40,
                    "--expected-parent-sha",
                    "b" * 40,
                    "--test-summary",
                    str(summary_path),
                    "--mcp-log",
                    str(mcp_log_path),
                    "--receipt-output",
                    str(receipt_path),
                    "--manifest-output",
                    str(manifest_path),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, validator.returncode, validator.stdout + validator.stderr)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        for artifact in (receipt, manifest):
            self.assertEqual("IMPLEMENTED_VERSION_BOUND_REFERENCE", artifact["verify_effect"])
            self.assertEqual(
                "VERIFY_EFFECT_TRUE_GATED_REFERENCE",
                artifact["effect_receipt_production"],
            )
            self.assertEqual(
                "IMPLEMENTED_EXACT_BUNDLE_REFERENCE",
                artifact["complete_verification"],
            )
            self.assertEqual("UNAVAILABLE", artifact["effect_bound_admission"])
            self.assertEqual(
                "NOT_ESTABLISHED",
                artifact["concurrent_file_mutation_snapshot_proof"],
            )
            self.assertEqual(
                "PROCESS_LOCAL_ISSUING_INSTANCE_ONLY",
                artifact["adapter_scope_binding"],
            )

        paths = {record["path"] for record in manifest["files"]}
        self.assertIn("harness/sdk/effect_verifier.py", paths)
        self.assertIn("harness/sdk/complete_verifier.py", paths)
        self.assertIn(
            "sovereign-omega-v2/python/tests/test_effect_verifier_pr3.py",
            paths,
        )
        self.assertIn(
            "sovereign-omega-v2/python/tests/test_complete_verifier_pr4.py",
            paths,
        )
        self.assertIn(
            "sovereign-omega-v2/python/tests/test_effect_chain_main_integration.py",
            paths,
        )
        self.assertIn(
            "sovereign-omega-v2/python/tests/test_effect_chain_evidence_integration.py",
            paths,
        )


if __name__ == "__main__":
    unittest.main()
