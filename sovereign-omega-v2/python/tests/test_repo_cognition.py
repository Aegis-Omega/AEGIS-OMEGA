#!/usr/bin/env python3
"""RED-first contract for repository cognition.

The production implementation lives at scripts/repo_cognition.py. These tests
intentionally specify behavior before that implementation exists.
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
