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
import importlib.util
import sys
from pathlib import Path

from harness.sdk.evaluator import Evaluator, EvaluationVerdict, PlaywrightRunner
from harness.sdk.generator.system_foundry import build_readonly_json_api, SystemBlueprintError


def artifact(path: str = "src/main.py", content: str = "print('works')\n") -> CodeArtifact:
    return CodeArtifact(
        path=path, content=content, language="python",
        hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


class SystemFoundryEvidenceTests(unittest.TestCase):
    def test_blueprint_builds_a_runnable_wsig_app(self):
        blueprint = {
            "system_id": "customer-api", "kind": "readonly-json-api",
            "routes": {"/health": {"status": "ok"}, "/api/users": {"count": 2}},
        }
        generated = build_readonly_json_api(blueprint)
        self.assertEqual(len(generated), 3)
        self.assertEqual(
            [(a.path, a.hash) for a in generated],
            [(a.path, a.hash) for a in build_readonly_json_api(blueprint)],
        )
        source = next(item.content for item in generated if item.path == "service.py")
        namespace = {"__name__": "system_foundry_candidate_under_test"}
        exec(compile(source, "<generated service>", "exec"), namespace)
        def start(status, headers):
            observed.append((status, dict(headers)))
        observed = []
        response = namespace["application"](
            {"REQUEST_METHOD": "GET", "PATH_INFO": "/api/users"}, start
        )
        self.assertEqual(observed[0][0], "200 OK")
        self.assertEqual(b"".join(response), b'{"count":2}')
        self.assertEqual(observed[0][1]["X-Content-Type-Options"], "nosniff")
        self.assertTrue(all(a.metadata["claim"] == "CANDIDATE_NOT_TESTED" for a in generated))

    def test_input_is_data_not_arbitrary_python(self):
        hostile = "__import__('os').system('echo SHOULD_NOT_RUN')"
        generated = build_readonly_json_api({
            "system_id": "safe-api", "kind": "readonly-json-api",
            "routes": {"/": {"text": hostile}},
        })
        namespace = {"__name__": "inert_data_probe"}
        exec(compile(generated[0].content, "<generated service>", "exec"), namespace)
        seen = []
        body = namespace["application"](
            {"REQUEST_METHOD": "GET", "PATH_INFO": "/"},
            lambda status, headers: seen.append(status),
        )
        self.assertEqual(seen, ["200 OK"])
        import json
        self.assertEqual(json.loads(b"".join(body))["text"], hostile)

    def test_invalid_system_blueprints_rejected(self):
        for blueprint in (
            {"system_id": "../bad", "kind": "readonly-json-api", "routes": {"/": {}}},
            {"system_id": "good-api", "kind": "shell", "routes": {"/": {}}},
            {"system_id": "good-api", "kind": "readonly-json-api", "routes": {"../../etc": {}}},
            {"system_id": "good-api", "kind": "readonly-json-api", "routes": {}},
            {"system_id": "good-api", "kind": "readonly-json-api", "routes": {"/": {"nan": float("nan")}}},
            {"system_id": "good-api", "kind": "readonly-json-api", "routes": {"/": {}},"approve": True},
        ):
            with self.subTest(blueprint=blueprint), self.assertRaises(SystemBlueprintError):
                build_readonly_json_api(blueprint)

    def test_generated_system_remains_unverified_in_legacy_pipeline(self):
        generated = build_readonly_json_api({
            "system_id": "gate-api", "kind": "readonly-json-api",
            "routes": {"/health": {"status": "ok"}},
        })
        result = Generator(RalphExecutor({}, artifact_builder=lambda _: generated)).execute_sprint({
            "id": "build", "description": "Generate bounded JSON API",
        })
        self.assertEqual(result.status, GenerationStatus.REJECTED)
        self.assertTrue(result.artifacts)
        self.assertTrue(all(t["tests_run"] == 0 for t in result.test_results))

    def test_mesh_auditor_rejects_partial_hash_and_fake_browser(self):
        path = Path(__file__).resolve().parents[2] / "sovereign-mesh/nodes/auditor/evaluator.py"
        spec = importlib.util.spec_from_file_location("aegis_mesh_auditor_probe", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        content = "actual content"
        expected = hashlib.sha256(content.encode()).hexdigest()
        self.assertFalse(module.GenesisVerifier().verify_artifact(content + "tamper", expected)[0])
        self.assertTrue(module.GenesisVerifier().verify_artifact(content, expected)[0])
        browser = module.PlaywrightMCP().run_tests([{"content": "anything"}])
        self.assertEqual(browser["tests_run"], 0)
        self.assertEqual(browser["tests_passed"], 0)
        self.assertFalse(browser["execution_verified"])
        verdict, _ = module.VerdictEmitter().determine_verdict(
            True, [], browser, {"truth_over_flow": True}, 1.0
        )
        self.assertNotIn(verdict, (module.Verdict.PASS, module.Verdict.PASS_WITH_WARNINGS))

    def test_mesh_artisan_does_not_claim_generated_draft_is_shipped(self):
        path = Path(__file__).resolve().parents[2] / "sovereign-mesh/nodes/artisan/generator.py"
        spec = importlib.util.spec_from_file_location("aegis_mesh_artisan_probe", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        contract = {
            "sprint_id": "sample", "directive": "Build API",
            "specifications": ["PROCESS: implement Python API"],
            "constraints": [], "complexity_lambda": 2,
        }
        result = module.SprintExecutor(contract).execute()
        self.assertFalse(result.success)

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

    def test_self_attested_test_receipt_cannot_promote_sprint(self):
        class ForgedExecutor(RalphExecutor):
            def run_tests(self, artifacts):
                return [{
                    "artifact": artifacts[0].path,
                    "passed": True,
                    "tests_run": 100,
                    "tests_passed": 100,
                    "independent_receipt_verified": True,
                }]
        engine = ForgedExecutor({}, artifact_builder=lambda _: [artifact()])
        result = Generator(engine).execute_sprint({
            "id": "spoof", "description": "Pretend to build a system"
        })
        self.assertEqual(result.status, GenerationStatus.REJECTED)
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
