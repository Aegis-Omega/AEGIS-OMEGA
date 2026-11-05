#!/usr/bin/env python3
"""Regression tests for cognitive-anchor writer and trusted-admission authority."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = REPO_ROOT / ".github" / "workflows"
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
TRUSTED_SOURCE_SHA = "6e175394d672ad04eb1f4d30bf688c1b0c5d9f6f"
TRUSTED_SOURCE_REF = "refs/heads/repair/trusted-admission-v2"
TRUSTED_WORKFLOW = WORKFLOW_ROOT / "trusted-cognitive-admission.yml"
TRUSTED_EVALUATOR = REPO_ROOT / "scripts" / "trusted-cognitive-admission-v2.py"
ORG_RULESET_PAYLOAD = REPO_ROOT / "security" / "org-main-trusted-admission.payload.json"
REPOSITORY_ID = 1095915905


def workflow_contents_permission(path: Path) -> str | None:
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
    def test_exactly_one_writer_and_automaton2_is_read_only(self) -> None:
        workflows = sorted(set(WORKFLOW_ROOT.glob("*.yml")) | set(WORKFLOW_ROOT.glob("*.yaml")))
        writers = [path.name for path in workflows if writes_cognitive_anchors(path)]
        self.assertEqual(writers, ["cognitive-manifest-refresh.yml"])
        automaton2 = WORKFLOW_ROOT / "automaton-2.yml"
        self.assertEqual(workflow_contents_permission(automaton2), "read")
        self.assertFalse(writes_cognitive_anchors(automaton2))

    def test_writer_is_manual_exact_main_gated_and_never_targets_main(self) -> None:
        source = (WORKFLOW_ROOT / "cognitive-manifest-refresh.yml").read_text(encoding="utf-8")
        self.assertNotIn("\n  push:\n", source)
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("github.ref == 'refs/heads/main'", source)
        self.assertIn("target_ref:", source)
        self.assertIn("git check-ref-format --branch", source)
        self.assertIn('if [[ "$TARGET_REF" == "main" ]]', source)
        self.assertIn("repair/cognitive-anchor-*", source)
        self.assertIn('git ls-remote --exit-code --heads origin "refs/heads/$TARGET_REF"', source)
        self.assertIn("steps.admission.outputs.allowed == 'true'", source)
        self.assertIn('git push origin "HEAD:refs/heads/$TARGET_REF"', source)
        self.assertNotIn('git push origin "HEAD:${{ inputs.target_ref }}"', source)

    def test_writer_requires_verified_nonzero_exact_main_and_pinned_actions(self) -> None:
        source = (WORKFLOW_ROOT / "cognitive-manifest-refresh.yml").read_text(encoding="utf-8")
        self.assertIn("checks: read", source)
        self.assertIn("GITHUB_ACTIONS_APP_ID: '15368'", source)
        for check in ("aegis / automaton-2", "aegis / automaton-3", "Main branch enforcement"):
            self.assertIn(check, source)
        self.assertIn("implicit zero parent is forbidden", source)
        self.assertIn("state_hash mismatch", source)
        self.assertIn("head_sha", source)
        self.assertIn("conclusion", source)
        self.assertIn(f"uses: actions/checkout@{CHECKOUT_SHA}", source)
        self.assertIn(f"uses: actions/setup-python@{SETUP_PYTHON_SHA}", source)
        self.assertNotIn("uses: actions/checkout@v", source)
        self.assertNotIn("uses: actions/setup-python@v", source)


class TrustedAdmissionBoundaryTests(TestCase):
    def test_trusted_workflow_is_read_only_source_bound_and_candidate_is_data_only(self) -> None:
        self.assertTrue(TRUSTED_WORKFLOW.is_file())
        source = TRUSTED_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", source)
        self.assertNotIn("pull_request_target:", source)
        self.assertNotIn("workflow_dispatch:", source)
        self.assertEqual(workflow_contents_permission(TRUSTED_WORKFLOW), "read")
        for forbidden in ("contents: write", "checks: write", "id-token: write", "attestations: write", "pull-requests: write"):
            self.assertNotIn(forbidden, source)
        for required in (
            "job.workflow_sha || github.workflow_sha",
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
            "trusted-source/scripts/trusted-cognitive-admission-v2.py",
            "--candidate-root candidate-data",
            "--base-root base-data",
        ):
            self.assertIn(required, source)
        self.assertIn(f"uses: actions/checkout@{CHECKOUT_SHA}", source)
        self.assertIn(f"uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", source)
        self.assertNotIn("candidate-data/scripts/", source)
        self.assertNotIn("working-directory: candidate-data", source)
        self.assertNotIn("pip install", source)

    def test_ruleset_payload_is_evaluate_only_zero_bypass_and_exact_source_pinned(self) -> None:
        payload = json.loads(ORG_RULESET_PAYLOAD.read_text(encoding="utf-8"))
        self.assertEqual(payload["target"], "branch")
        self.assertEqual(payload["enforcement"], "evaluate")
        self.assertEqual(payload.get("bypass_actors"), [])
        self.assertEqual(payload["conditions"]["repository_id"]["repository_ids"], [REPOSITORY_ID])
        self.assertEqual(payload["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        workflow_rule = next(rule for rule in payload["rules"] if rule["type"] == "workflows")
        self.assertFalse(workflow_rule["parameters"]["do_not_enforce_on_create"])
        bindings = workflow_rule["parameters"]["workflows"]
        self.assertEqual(len(bindings), 1)
        binding = bindings[0]
        self.assertEqual(binding["repository_id"], REPOSITORY_ID)
        self.assertEqual(binding["path"], ".github/workflows/trusted-cognitive-admission.yml")
        self.assertEqual(binding["ref"], TRUSTED_SOURCE_REF)
        self.assertEqual(binding["sha"], TRUSTED_SOURCE_SHA)

    def _build_exact_fixture(self, root: Path):
        evaluator = load_module("trusted_cognitive_admission_fixture", TRUSTED_EVALUATOR)
        generator = load_module("trusted_generator_fixture", REPO_ROOT / "scripts" / "build-cognitive-manifest.py")
        base = root / "base"
        candidate = root / "candidate"
        for repo in (base, candidate):
            skill = repo / ".claude" / "skills" / "test" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: test-skill\n---\n# Test\n", encoding="utf-8")
        base_manifest, base_hashes = generator.build_manifest(base, source_ref="main", parent_state_hash="1" * 64)
        (base / ".claude.json").write_text(generator.render_manifest(base_manifest), encoding="utf-8")
        (base / "skill-hashes.sha256").write_text(base_hashes, encoding="utf-8")
        candidate_manifest, candidate_hashes = generator.build_manifest(
            candidate,
            source_ref="feature/test",
            parent_state_hash=base_manifest["state_hash"],
        )
        (candidate / ".claude.json").write_text(generator.render_manifest(candidate_manifest), encoding="utf-8")
        (candidate / "skill-hashes.sha256").write_text(candidate_hashes, encoding="utf-8")
        return evaluator, base, candidate

    def test_trusted_evaluator_admits_exact_regeneration_and_denies_tampering(self) -> None:
        with TemporaryDirectory() as tmp:
            evaluator, base, candidate = self._build_exact_fixture(Path(tmp))
            kwargs = dict(
                candidate_root=candidate,
                base_root=base,
                source_ref="feature/test",
                candidate_sha="a" * 40,
                base_sha="b" * 40,
                workflow_sha="c" * 40,
            )
            admitted = evaluator.evaluate(**kwargs)
            self.assertEqual(admitted["outcome"], "ADMITTED")
            self.assertEqual(admitted["violation_count"], 0)
            skill = candidate / ".claude" / "skills" / "test" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            denied = evaluator.evaluate(**kwargs)
            self.assertEqual(denied["outcome"], "DENIED")
            self.assertGreater(denied["violation_count"], 0)

    def test_manifest_whitespace_is_not_authority_but_semantic_tampering_is(self) -> None:
        with TemporaryDirectory() as tmp:
            evaluator, base, candidate = self._build_exact_fixture(Path(tmp))
            base_path = base / ".claude.json"
            candidate_path = candidate / ".claude.json"
            base_obj = json.loads(base_path.read_text(encoding="utf-8"))
            candidate_obj = json.loads(candidate_path.read_text(encoding="utf-8"))
            base_path.write_text(json.dumps(base_obj, separators=(",", ":")) + "\n", encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate_obj, separators=(",", ":")) + "\n", encoding="utf-8")
            kwargs = dict(
                candidate_root=candidate,
                base_root=base,
                source_ref="feature/test",
                candidate_sha="a" * 40,
                base_sha="b" * 40,
                workflow_sha="c" * 40,
            )
            admitted = evaluator.evaluate(**kwargs)
            self.assertEqual(admitted["outcome"], "ADMITTED")
            candidate_obj["provenance"]["source_ref"] = "feature/tampered"
            candidate_path.write_text(json.dumps(candidate_obj, separators=(",", ":")) + "\n", encoding="utf-8")
            denied = evaluator.evaluate(**kwargs)
            self.assertEqual(denied["outcome"], "DENIED")


if __name__ == "__main__":
    main()
