#!/usr/bin/env python3
"""Regression tests for cognitive-anchor writers and trusted admission controls."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = REPO_ROOT / ".github" / "workflows"
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
TRUSTED_WORKFLOW = WORKFLOW_ROOT / "trusted-cognitive-admission.yml"
TRUSTED_EVALUATOR = REPO_ROOT / "scripts" / "trusted-cognitive-admission.py"
ORG_RULESET_PAYLOAD = REPO_ROOT / "security" / "org-main-trusted-admission.payload.json"
REPOSITORY_ID = 1095915905
ZERO_HASH = "0" * 64


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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        source = (WORKFLOW_ROOT / "cognitive-manifest-refresh.yml").read_text(encoding="utf-8")
        self.assertIn("repair/cognitive-anchor-*", source)

    def test_writer_does_not_execute_from_candidate_pushes(self) -> None:
        source = (WORKFLOW_ROOT / "cognitive-manifest-refresh.yml").read_text(encoding="utf-8")
        self.assertNotIn("\n  push:\n", source)
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("github.ref == 'refs/heads/main'", source)

    def test_writer_requires_exact_admitted_main_before_mutation(self) -> None:
        source = (WORKFLOW_ROOT / "cognitive-manifest-refresh.yml").read_text(encoding="utf-8")
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
        source = (WORKFLOW_ROOT / "cognitive-manifest-refresh.yml").read_text(encoding="utf-8")
        self.assertIn("target_ref:", source)
        self.assertIn("steps.admission.outputs.allowed == 'true'", source)
        self.assertIn("TARGET_REF: ${{ inputs.target_ref }}", source)
        self.assertIn('git ls-remote --exit-code --heads origin "refs/heads/$TARGET_REF"', source)
        self.assertIn("ref: refs/heads/${{ inputs.target_ref }}", source)
        self.assertIn('git push origin "HEAD:refs/heads/$TARGET_REF"', source)
        self.assertNotIn('git push origin "HEAD:${{ inputs.target_ref }}"', source)

    def test_writer_actions_are_immutable_commit_pinned(self) -> None:
        source = (WORKFLOW_ROOT / "cognitive-manifest-refresh.yml").read_text(encoding="utf-8")
        self.assertIn(f"uses: actions/checkout@{CHECKOUT_SHA}", source)
        self.assertIn(f"uses: actions/setup-python@{SETUP_PYTHON_SHA}", source)
        self.assertNotIn("uses: actions/checkout@v", source)
        self.assertNotIn("uses: actions/setup-python@v", source)


class TrustedAdmissionBoundaryTests(TestCase):
    def test_trusted_ruleset_workflow_exists_and_is_read_only(self) -> None:
        self.assertTrue(TRUSTED_WORKFLOW.is_file(), "trusted ruleset workflow is missing")
        source = TRUSTED_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", source)
        self.assertNotIn("pull_request_target:", source)
        self.assertNotIn("workflow_dispatch:", source)
        self.assertNotIn("cancel-in-progress", source)
        self.assertEqual(workflow_contents_permission(TRUSTED_WORKFLOW), "read")
        for forbidden in (
            "contents: write",
            "checks: write",
            "id-token: write",
            "attestations: write",
            "pull-requests: write",
        ):
            self.assertNotIn(forbidden, source)

    def test_trusted_workflow_separates_source_base_and_candidate_data(self) -> None:
        self.assertTrue(TRUSTED_WORKFLOW.is_file(), "trusted ruleset workflow is missing")
        source = TRUSTED_WORKFLOW.read_text(encoding="utf-8")
        required = (
            "GITHUB_WORKFLOW_SHA",
            "github.workflow_sha",
            "path: trusted-source",
            "path: base-data",
            "path: candidate-data",
            "persist-credentials: false",
            "submodules: false",
            "lfs: false",
            "github.event.pull_request.head.repo.full_name",
            "os.path.islink",
            "MAX_SKILL_FILES",
            "MAX_COGNITIVE_BYTES",
            "trusted-source/scripts/trusted-cognitive-admission.py",
            "--candidate-root candidate-data",
            "--base-root base-data",
            "--workflow-sha \"$GITHUB_WORKFLOW_SHA\"",
        )
        for item in required:
            self.assertIn(item, source)
        self.assertIn(f"uses: actions/checkout@{CHECKOUT_SHA}", source)
        self.assertIn(f"uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", source)
        self.assertNotIn("candidate-data/scripts/", source)
        self.assertNotIn("working-directory: candidate-data", source)
        self.assertNotIn("pip install", source)

    def test_organization_ruleset_payload_source_pins_required_workflow(self) -> None:
        self.assertTrue(ORG_RULESET_PAYLOAD.is_file(), "organization ruleset payload is missing")
        payload = json.loads(ORG_RULESET_PAYLOAD.read_text(encoding="utf-8"))
        self.assertEqual(payload["target"], "branch")
        self.assertEqual(payload["enforcement"], "evaluate")
        self.assertEqual(payload.get("bypass_actors"), [])
        self.assertEqual(payload["conditions"]["repository_id"]["repository_ids"], [REPOSITORY_ID])
        self.assertEqual(payload["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        workflow_rule = next(rule for rule in payload["rules"] if rule["type"] == "workflows")
        self.assertFalse(workflow_rule["parameters"]["do_not_enforce_on_create"])
        workflows = workflow_rule["parameters"]["workflows"]
        self.assertEqual(len(workflows), 1)
        binding = workflows[0]
        self.assertEqual(binding["repository_id"], REPOSITORY_ID)
        self.assertEqual(binding["path"], ".github/workflows/trusted-cognitive-admission.yml")
        self.assertEqual(binding["ref"], "refs/heads/repair/trusted-ruleset-workflow-v1")
        self.assertRegex(binding["sha"], r"^[0-9a-f]{40}$")
        self.assertNotEqual(binding["sha"], ZERO_HASH[:40])

    def test_trusted_evaluator_admits_only_exact_regeneration(self) -> None:
        self.assertTrue(TRUSTED_EVALUATOR.is_file(), "trusted evaluator is missing")
        evaluator = load_module("trusted_cognitive_admission", TRUSTED_EVALUATOR)
        generator = load_module("trusted_generator_test", REPO_ROOT / "scripts" / "build-cognitive-manifest.py")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            candidate = root / "candidate"
            for repo in (base, candidate):
                skill = repo / ".claude" / "skills" / "test" / "SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text("---\nname: test-skill\n---\n# Test\n", encoding="utf-8")

            base_manifest, base_hashes = generator.build_manifest(
                base,
                source_ref="main",
                parent_state_hash="1" * 64,
            )
            (base / ".claude.json").write_text(generator.render_manifest(base_manifest), encoding="utf-8")
            (base / "skill-hashes.sha256").write_text(base_hashes, encoding="utf-8")

            candidate_manifest, candidate_hashes = generator.build_manifest(
                candidate,
                source_ref="feature/test",
                parent_state_hash=base_manifest["state_hash"],
            )
            (candidate / ".claude.json").write_text(
                generator.render_manifest(candidate_manifest), encoding="utf-8"
            )
            (candidate / "skill-hashes.sha256").write_text(candidate_hashes, encoding="utf-8")

            receipt = evaluator.evaluate(
                candidate_root=candidate,
                base_root=base,
                source_ref="feature/test",
                candidate_sha="a" * 40,
                base_sha="b" * 40,
                workflow_sha="c" * 40,
            )
            self.assertEqual(receipt["outcome"], "ADMITTED")
            self.assertEqual(receipt["violation_count"], 0)

            skill = candidate / ".claude" / "skills" / "test" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            denied = evaluator.evaluate(
                candidate_root=candidate,
                base_root=base,
                source_ref="feature/test",
                candidate_sha="a" * 40,
                base_sha="b" * 40,
                workflow_sha="c" * 40,
            )
            self.assertEqual(denied["outcome"], "DENIED")
            self.assertGreater(denied["violation_count"], 0)


if __name__ == "__main__":
    main()
