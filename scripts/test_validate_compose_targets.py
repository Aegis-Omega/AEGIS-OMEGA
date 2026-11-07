#!/usr/bin/env python3
"""Literal build-target regressions, including the AEGIS #775 mismatch class."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("validate_compose_targets.py")
spec = importlib.util.spec_from_file_location("aegis_compose_check", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ComposeTargetContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        path = self.root / "sovereign-omega-v2"
        path.mkdir()
        self.df = path / "Dockerfile"
        self.df.write_text("FROM python:3.11-slim\nCMD ['python']\n", encoding="utf-8")
        self.compose = """services:
  bridge:
    build:
      context: ./sovereign-omega-v2
      dockerfile: Dockerfile
      target: runtime
    ports:
      - '7890:7890'
volumes:
  data:
"""

    def check(self, text=None):
        return module.evaluate(self.root, self.compose if text is None else text)

    def test_native_ci_uses_real_compose_source(self):
        workflow = (SOURCE.parents[1] / ".github" / "workflows" / "repository-knowledge.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/validate_compose_targets.py --repo .", workflow)
        self.assertNotIn("id-token: write", workflow)

    def test_native_ci_validates_full_compose_graph_without_deployment(self):
        workflow = (SOURCE.parents[1] / ".github" / "workflows" / "repository-knowledge.yml").read_text(encoding="utf-8")
        self.assertIn("docker compose --profile agents config --quiet", workflow)
        self.assertNotIn("docker compose up", workflow)

    def test_nonexistent_stage_is_failed(self):
        out = self.check()
        self.assertEqual(out["status"], "FAILED")
        self.assertEqual(out["services"][0]["reason"], "BUILD_TARGET_NOT_FOUND")

    def test_named_stage_is_pass(self):
        self.df.write_text("FROM python:3.11-slim AS runtime\n", encoding="utf-8")
        self.assertEqual(self.check()["status"], "PASS")

    def test_no_target_defaults_to_final_stage(self):
        self.assertEqual(self.check(self.compose.replace("      target: runtime\n", ""))["status"], "PASS")

    def test_target_is_case_insensitive(self):
        self.df.write_text("FROM python:3.11-slim as RUNTIME\n", encoding="utf-8")
        self.assertEqual(self.check()["status"], "PASS")

    def test_missing_dockerfile_is_failed(self):
        self.df.unlink()
        self.assertEqual(self.check()["services"][0]["reason"], "DOCKERFILE_MISSING")

    def test_unresolved_dockerfile_path_is_unknown(self):
        text = self.compose.replace("dockerfile: Dockerfile", "dockerfile: ${DOCKERFILE}")
        self.assertEqual(self.check(text)["status"], "UNKNOWN")

    def test_unsupported_build_scalar_is_unknown(self):
        text = "services:\n  bridge:\n    build: .\n"
        self.assertEqual(self.check(text)["status"], "UNKNOWN")

    def test_no_parseable_services_is_unknown(self):
        self.assertEqual(self.check("services: {}\n")["status"], "UNKNOWN")

    def test_no_builds_is_unknown(self):
        self.assertEqual(self.check("services:\n  proxy:\n    image: nginx\n")["status"], "UNKNOWN")

    def test_multiple_builds_failed_closed(self):
        text = self.compose.replace("    ports:", "    build:\n      context: .\n    ports:")
        self.assertEqual(self.check(text)["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
