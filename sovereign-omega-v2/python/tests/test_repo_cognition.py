#!/usr/bin/env python3
"""RED-first contract for repository cognition and Claude lifecycle wiring.

The production implementation lives at scripts/repo_cognition.py. Repository
cognition is only useful if every agent lifecycle boundary consumes it without
silently upgrading unavailable/stale state into verified repository knowledge.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "scripts" / "repo_cognition.py"
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
SESSION_START_PATH = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"
POST_COMPACT_PATH = REPO_ROOT / ".claude" / "hooks" / "post-compact-reanchor.sh"
USER_PROMPT_PATH = REPO_ROOT / ".claude" / "hooks" / "user-prompt-intake.sh"

spec = importlib.util.spec_from_file_location("repo_cognition", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load {MODULE_PATH}")
repo_cognition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repo_cognition)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.STDOUT
    ).strip()


def init_repo(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "repo-cognition@example.invalid")
    git(root, "config", "user.name", "Repo Cognition Test")


def commit_all(root: Path, message: str) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)


class RepoCognitionContractTests(unittest.TestCase):
    def make_repo(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        init_repo(root)
        (root / "src").mkdir()
        (root / "docs").mkdir()
        (root / ".aegis").mkdir()
        (root / "src" / "alpha.py").write_text(
            "class Alpha:\n    pass\n\ndef solve(value):\n    return value\n",
            encoding="utf-8",
        )
        (root / "src" / "beta.ts").write_text(
            "export interface Beta { value: number }\n"
            "export function route(x: number) { return x }\n",
            encoding="utf-8",
        )
        (root / "docs" / "README.md").write_text(
            "# Test corpus\n\nRepository cognition fixture.\n", encoding="utf-8"
        )
        # Generated cognition output is tracked but must not participate in its
        # own corpus root, otherwise the root becomes self-referential.
        (root / ".aegis" / "repo-cognition-v1.json").write_text(
            "{}\n", encoding="utf-8"
        )
        commit_all(root, "fixture")
        return root

    def test_build_indexes_every_eligible_tracked_file(self) -> None:
        root = self.make_repo()
        manifest = repo_cognition.build_repository_corpus(root)

        self.assertEqual(manifest["schema"], "AEGIS_REPO_COGNITION_V1")
        self.assertEqual(manifest["tracked_file_count"], 4)
        self.assertEqual(manifest["eligible_file_count"], 3)
        self.assertEqual(manifest["indexed_file_count"], 3)
        self.assertEqual(manifest["coverage"], 1.0)
        self.assertEqual(
            manifest["excluded_generated_paths"],
            [".aegis/repo-cognition-v1.json"],
        )
        self.assertEqual(
            [entry["path"] for entry in manifest["files"]],
            ["docs/README.md", "src/alpha.py", "src/beta.ts"],
        )
        for entry in manifest["files"]:
            self.assertRegex(entry["git_blob_sha"], r"^[0-9a-f]{40}$")
            self.assertRegex(entry["content_sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(entry["size_bytes"], 0)
            self.assertIn("kind", entry)

    def test_symbol_hints_make_content_addressable_without_claiming_semantics(self) -> None:
        root = self.make_repo()
        manifest = repo_cognition.build_repository_corpus(root)
        by_path = {entry["path"]: entry for entry in manifest["files"]}

        self.assertIn("Alpha", by_path["src/alpha.py"]["symbol_hints"])
        self.assertIn("solve", by_path["src/alpha.py"]["symbol_hints"])
        self.assertIn("Beta", by_path["src/beta.ts"]["symbol_hints"])
        self.assertIn("route", by_path["src/beta.ts"]["symbol_hints"])
        self.assertEqual(by_path["docs/README.md"]["heading_hint"], "Test corpus")

    def test_corpus_root_changes_when_source_content_changes(self) -> None:
        root = self.make_repo()
        before = repo_cognition.build_repository_corpus(root)["corpus_root"]

        (root / "src" / "alpha.py").write_text(
            "class Alpha:\n    pass\n\ndef solve(value):\n    return value + 1\n",
            encoding="utf-8",
        )
        commit_all(root, "change source")
        after = repo_cognition.build_repository_corpus(root)["corpus_root"]

        self.assertNotEqual(before, after)

    def test_verify_fails_closed_on_stale_manifest(self) -> None:
        root = self.make_repo()
        manifest_path = root / ".aegis" / "repo-cognition-v1.json"
        manifest = repo_cognition.build_repository_corpus(root)
        manifest_path.write_text(
            repo_cognition.render_manifest(manifest), encoding="utf-8"
        )
        commit_all(root, "record cognition")

        ok, reasons = repo_cognition.verify_repository_corpus(root, manifest_path)
        self.assertTrue(ok, reasons)
        self.assertEqual(reasons, [])

        (root / "src" / "new.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(root, "add unseen file")

        ok, reasons = repo_cognition.verify_repository_corpus(root, manifest_path)
        self.assertFalse(ok)
        self.assertTrue(any("stale" in reason.lower() for reason in reasons), reasons)

    def test_manifest_is_deterministic_for_same_source_tree(self) -> None:
        root = self.make_repo()
        one = repo_cognition.render_manifest(
            repo_cognition.build_repository_corpus(root)
        )
        two = repo_cognition.render_manifest(
            repo_cognition.build_repository_corpus(root)
        )
        self.assertEqual(one, two)
        parsed = json.loads(one)
        self.assertRegex(parsed["corpus_root"], r"^[0-9a-f]{64}$")


class ClaudeLifecycleCognitionTests(unittest.TestCase):
    """Agent context lifecycle must not launder missing state into authority."""

    def test_user_prompt_is_the_blocking_repository_admission_boundary(self) -> None:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        prompt_hook = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        self.assertNotEqual(prompt_hook.get("async"), True)

        script = USER_PROMPT_PATH.read_text(encoding="utf-8")
        self.assertIn("scripts/repo_cognition.py", script)
        self.assertIn("--check --receipt", script)
        self.assertIn("'decision': 'block'", script)
        self.assertIn("REPOSITORY_KNOWLEDGE_INCOMPLETE", script)
        self.assertIn(
            "CERT='{\"is_valid\":false",
            script,
            "metacognitive-unavailable must default invalid, never verified",
        )

    def test_session_start_orientation_is_not_backgrounded(self) -> None:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        session_hook = settings["hooks"]["SessionStart"][0]["hooks"][0]
        self.assertNotEqual(
            session_hook.get("async"),
            True,
            "repository orientation must complete before the session proceeds",
        )

        script = SESSION_START_PATH.read_text(encoding="utf-8")
        self.assertNotIn(
            "{\"async\": true",
            script,
            "the hook must not self-background repository ground truth",
        )
        self.assertIn("scripts/ground-truth.sh", script)

    def test_post_compact_reanchors_repository_cognition_without_false_restoration(self) -> None:
        script = POST_COMPACT_PATH.read_text(encoding="utf-8")
        self.assertIn("scripts/repo_cognition.py", script)
        self.assertIn("--check --receipt", script)
        self.assertIn("REPOSITORY_KNOWLEDGE_INCOMPLETE", script)
        self.assertIn("COGNITION_STATUS", script)
        self.assertNotIn(
            "constitutional law restored",
            script.lower(),
            "PostCompact cannot claim restored authority when a verifier failed",
        )
        self.assertNotIn(
            "Seven cognitive layers are now re-active",
            script,
            "context availability must be reported conditionally, not asserted",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
