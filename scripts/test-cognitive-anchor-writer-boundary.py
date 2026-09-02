#!/usr/bin/env python3
"""Regression tests for exclusive ownership of cognitive-anchor writes."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = REPO_ROOT / ".github" / "workflows"
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"


def workflow_contents_permission(path: Path) -> str | None:
    """Return the workflow-level contents permission without a YAML dependency."""
    in_permissions = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "permissions:":
            in_permissions = True
            continue
        if in_permissions and line and not line.startswith("  "):
            break
        if in_permissions and line.startswith("  contents:"):
            return line.split(":", 1)[1].strip()
    return None


def writes_cognitive_anchors(path: Path) -> bool:
    """Identify a workflow that stages both governed anchors and pushes them."""
    source = path.read_text(encoding="utf-8")
    stages_anchors = (
        "git add .claude.json skill-hashes.sha256" in source
        or "git add skill-hashes.sha256 .claude.json" in source
    )
    return stages_anchors and "git push" in source


class CognitiveAnchorWriterBoundaryTests(TestCase):
    def test_exactly_one_workflow_writes_cognitive_anchors(self) -> None:
        workflows = sorted(
            set(WORKFLOW_ROOT.glob("*.yml")) | set(WORKFLOW_ROOT.glob("*.yaml"))
        )
        writers = [path.name for path in workflows if writes_cognitive_anchors(path)]

        self.assertEqual(writers, ["cognitive-manifest-refresh.yml"])

    def test_automaton2_is_a_read_only_verifier(self) -> None:
        automaton2 = WORKFLOW_ROOT / "automaton-2.yml"

        self.assertEqual(workflow_contents_permission(automaton2), "read")
        self.assertFalse(writes_cognitive_anchors(automaton2))

    def test_recovery_branches_are_not_auto_mutated(self) -> None:
        refresh = WORKFLOW_ROOT / "cognitive-manifest-refresh.yml"
        source = refresh.read_text(encoding="utf-8")

        self.assertIn("repair/cognitive-anchor-*", source)

    def test_writer_does_not_execute_from_candidate_pushes(self) -> None:
        refresh = WORKFLOW_ROOT / "cognitive-manifest-refresh.yml"
        source = refresh.read_text(encoding="utf-8")

        self.assertNotIn("\n  push:\n", source)
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("github.ref == 'refs/heads/main'", source)

    def test_writer_requires_exact_admitted_main_before_mutation(self) -> None:
        refresh = WORKFLOW_ROOT / "cognitive-manifest-refresh.yml"
        source = refresh.read_text(encoding="utf-8")

        self.assertIn("checks: read", source)
        self.assertIn("GITHUB_ACTIONS_APP_ID: '15368'", source)
        self.assertIn("aegis / automaton-2", source)
        self.assertIn("aegis / automaton-3", source)
        self.assertIn("Main branch enforcement", source)
        self.assertIn("implicit zero parent is forbidden", source)
        self.assertIn("state_hash mismatch", source)
        self.assertIn("head_sha", source)
        self.assertIn("conclusion", source)
        self.assertIn("app", source)
        self.assertIn("id", source)

    def test_writer_targets_existing_remote_branch_only_after_admission_gate(self) -> None:
        refresh = WORKFLOW_ROOT / "cognitive-manifest-refresh.yml"
        source = refresh.read_text(encoding="utf-8")

        self.assertIn("target_ref:", source)
        self.assertIn("steps.admission.outputs.allowed == 'true'", source)
        self.assertIn("TARGET_REF: ${{ inputs.target_ref }}", source)
        self.assertIn('git ls-remote --exit-code --heads origin "refs/heads/$TARGET_REF"', source)
        self.assertIn("ref: refs/heads/${{ inputs.target_ref }}", source)
        self.assertIn('git push origin "HEAD:refs/heads/$TARGET_REF"', source)
        self.assertNotIn('git push origin "HEAD:${{ inputs.target_ref }}"', source)

    def test_writer_actions_are_immutable_commit_pinned(self) -> None:
        refresh = WORKFLOW_ROOT / "cognitive-manifest-refresh.yml"
        source = refresh.read_text(encoding="utf-8")

        self.assertIn(f"uses: actions/checkout@{CHECKOUT_SHA}", source)
        self.assertIn(f"uses: actions/setup-python@{SETUP_PYTHON_SHA}", source)
        self.assertNotIn("uses: actions/checkout@v", source)
        self.assertNotIn("uses: actions/setup-python@v", source)


if __name__ == "__main__":
    main()
