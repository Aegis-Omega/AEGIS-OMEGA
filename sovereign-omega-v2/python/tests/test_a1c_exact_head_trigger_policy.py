#!/usr/bin/env python3
"""Fail-closed policy tests for hosted A1c exact-head execution."""
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = (
    REPO_ROOT / ".github/workflows/weil-corn-o0-a1c.yml",
    REPO_ROOT / ".github/workflows/coq-formal-attestation.yml",
)
EXACT_BRANCH_TRIGGER = """  push:
    branches:
      - proof/corn-o0-completion-equivalence-v1
"""


class A1cExactHeadTriggerPolicyTests(unittest.TestCase):
    def test_formal_workflows_execute_on_exact_branch_push(self) -> None:
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                source = workflow.read_text(encoding="utf-8")
                self.assertIn(EXACT_BRANCH_TRIGGER, source)

    def test_hosted_formal_execution_remains_read_only(self) -> None:
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                source = workflow.read_text(encoding="utf-8")
                self.assertIn("permissions:\n  contents: read", source)
                self.assertNotIn("contents: write", source)


if __name__ == "__main__":
    unittest.main()
