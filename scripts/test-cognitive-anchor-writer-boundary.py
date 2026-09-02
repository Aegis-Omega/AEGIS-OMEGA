#!/usr/bin/env python3
"""Regression tests for the cognitive-anchor mutation boundary.

Candidate branches must have zero autonomous workflow writers. Expected cognitive
anchors are generated as read-only artifacts; applying them is an explicit normal
candidate commit so the resulting exact head receives the same CI/admission checks
as every other repository mutation.
"""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = REPO_ROOT / ".github" / "workflows"


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
    """Identify any workflow that stages governed anchors and advances a ref."""
    source = path.read_text(encoding="utf-8")
    stages_anchors = (
        "git add .claude.json skill-hashes.sha256" in source
        or "git add skill-hashes.sha256 .claude.json" in source
    )
    advances_ref = "git push" in source or "git update-ref" in source
    return stages_anchors and advances_ref


class CognitiveAnchorMutationBoundaryTests(TestCase):
    def test_no_workflow_autonomously_writes_cognitive_anchors(self) -> None:
        workflows = sorted(
            set(WORKFLOW_ROOT.glob("*.yml")) | set(WORKFLOW_ROOT.glob("*.yaml"))
        )
        writers = [path.name for path in workflows if writes_cognitive_anchors(path)]

        self.assertEqual(writers, [])

    def test_manifest_preview_is_read_only_exact_head_evidence(self) -> None:
        preview = WORKFLOW_ROOT / "cognitive-manifest-refresh.yml"
        source = preview.read_text(encoding="utf-8")

        self.assertEqual(workflow_contents_permission(preview), "read")
        self.assertFalse(writes_cognitive_anchors(preview))
        self.assertNotIn("contents: write", source)
        self.assertNotIn("git commit", source)
        self.assertNotIn("git push", source)
        self.assertIn("ref: ${{ github.sha }}", source)
        self.assertIn("persist-credentials: false", source)
        self.assertIn('--output-dir "$RUNNER_TEMP/cognitive-anchors"', source)
        self.assertIn("actions/upload-artifact@", source)
        self.assertIn("aegis-cognitive-anchor-preview-${{ github.sha }}", source)

    def test_automaton2_is_a_read_only_verifier(self) -> None:
        automaton2 = WORKFLOW_ROOT / "automaton-2.yml"

        self.assertEqual(workflow_contents_permission(automaton2), "read")
        self.assertFalse(writes_cognitive_anchors(automaton2))


if __name__ == "__main__":
    main()
