"""System Foundry contract: generating a filename is not building a system.

Focused falsifiers for legacy Planner/Generator/Evaluator evidence.
No inference API, browser, Docker, paid calls, or production mutation.
"""
from __future__ import annotations

import hashlib
import unittest

from harness.sdk.generator import (
    CodeArtifact, GenerationStatus, Generator, RalphExecutor,
)
from harness.sdk.evaluator import Evaluator, EvaluationVerdict, PlaywrightRunner


def artifact(path: str = "src/main.py", content: str = "print('works')\n") -> CodeArtifact:
    return CodeArtifact(
        path=path, content=content, language="python",
        hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


class SystemFoundryEvidenceTests(unittest.TestCase):
    def test_missing_builder_cannot_generate_fake_rust(self):
        engine = RalphExecutor(constraints={})
        self.assertEqual(engine.execute("Build a payment platform"), [])
        self.assertEqual(engine.execution_log[-1]["outcome"], "DENIED_NO_IMPLEMENTATION_ADAPTER")
        result = Generator(engine).execute_sprint({"id": "t", "description": "Build a platform"})
        self.assertEqual(result.status, GenerationStatus.REJECTED)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.artifacts, [])

    def test_candidate_with_valid_hash_is_not_complete_without_tests(self):
        engine = RalphExecutor(constraints={}, artifact_builder=lambda _: [artifact()])
        result = Generator(engine).execute_sprint({"id": "t", "description": "Build service"})
        self.assertEqual(result.status, GenerationStatus.REJECTED)
        self.assertEqual(result.artifacts[0].path, "src/main.py")
        self.assertEqual(result.test_results[0]["tests_run"], 0)
        self.assertFalse(result.test_results[0]["passed"])
        self.assertEqual(result.confidence, 0.0)

    def test_forged_artifact_digest_denied(self):
        bad = artifact()
        bad.hash = "0" * 64
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            RalphExecutor({}, artifact_builder=lambda _: [bad]).execute("task")

    def test_path_traversal_denied(self):
        with self.assertRaisesRegex(ValueError, "PATH_UNSAFE"):
            RalphExecutor({}, artifact_builder=lambda _: [artifact("../outside.py")]).execute("task")

    def test_duplicate_artifact_path_denied(self):
        with self.assertRaisesRegex(ValueError, "PATH_DUPLICATE"):
            RalphExecutor({}, artifact_builder=lambda _: [artifact(), artifact()]).execute("task")

    def test_empty_artifact_denied(self):
        with self.assertRaisesRegex(ValueError, "CONTENT_EMPTY"):
            RalphExecutor({}, artifact_builder=lambda _: [artifact(content="")]).execute("task")

    def test_default_playwright_cannot_assert_browser_pass(self):
        results = PlaywrightRunner().run_tests(["app/index.html"])
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].passed)
        self.assertEqual(results[0].duration_ms, 0.0)
        self.assertEqual(results[0].error_message, "PLAYWRIGHT_EXECUTION_NOT_CONFIGURED")

    def test_no_artifacts_still_produces_negative_qa(self):
        results = PlaywrightRunner().run_tests([])
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].passed)

    def test_malicious_reported_pass_does_not_pass_evaluator(self):
        fabricated = {
            "task_id": "forged", "status": "complete", "confidence": 1.0,
            "artifacts": [{"path": "app.py", "language": "python", "content_hash": "0" * 64}],
            "test_results": [{"passed": True, "tests_run": 100, "tests_passed": 100}],
        }
        report = Evaluator().evaluate(fabricated)
        self.assertNotIn(report.verdict, (EvaluationVerdict.PASS, EvaluationVerdict.PASS_WITH_WARNINGS))
        self.assertIn("INDEPENDENT_TEST_EVIDENCE_MISSING", report.errors)
        self.assertFalse(report.constitutional_checks["genesis_seal_verified"])
        self.assertFalse(report.playwright_results[0].passed)

    def test_no_artifact_and_no_tests_cannot_pass(self):
        report = Evaluator().evaluate({
            "task_id": "empty", "status": "complete", "confidence": 1.0,
            "artifacts": [], "test_results": [],
        })
        self.assertEqual(report.verdict, EvaluationVerdict.REJECT_REROLL)
        self.assertIn("NO_BUILD_ARTIFACTS", report.errors)


if __name__ == "__main__":
    unittest.main()
