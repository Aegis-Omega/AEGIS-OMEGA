#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import tempfile
import unittest
from pathlib import Path

INSTALL = Path(__file__).with_name("install_optimus_docs.py")


def run(repo, *args):
    return subprocess.run(args, cwd=repo, capture_output=True, text=True)


class InstallDocsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        for args in [("git", "init", "-q"), ("git", "config", "user.name", "Test"),
                     ("git", "config", "user.email", "test@example.invalid")]:
            self.assertEqual(run(self.repo, *args).returncode, 0)
        self.repomap = self.repo / "REPO_MAP.md"
        self.original = "# Old repo map\nPrices $48, $498 are archival.\n"
        self.repomap.write_text(self.original)
        for p in ("ASSETS.md", "HANDOFF.md", "docs/PROOF.md", "reports/repositories.md"):
            f = self.repo / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(f"# {p} historical\n")
        for args in [("git", "add", "-A"), ("git", "commit", "-qm", "initial")]:
            self.assertEqual(run(self.repo, *args).returncode, 0)
        self.head = run(self.repo, "git", "rev-parse", "HEAD").stdout.strip()

    def test_preview_does_not_write(self):
        proc = run(self.repo, "python3", str(INSTALL))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PREVIEW_ONLY", proc.stdout)
        self.assertEqual(self.repomap.read_text(), self.original)
        self.assertFalse((self.repo / "docs/archive/REPO_MAP_2026-07.md").exists())

    def test_wrong_head_refused(self):
        proc = run(self.repo, "python3", str(INSTALL), "--apply", "--expected-head", "0"*40)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(self.repomap.read_text(), self.original)

    def test_dirty_tree_refused(self):
        (self.repo / "HANDOFF.md").write_text("dirty")
        proc = run(self.repo, "python3", str(INSTALL), "--apply", "--expected-head", self.head)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(self.repomap.read_text(), self.original)

    def test_historic_contents_preserved_and_idempotent(self):
        proc = run(self.repo, "python3", str(INSTALL), "--apply", "--expected-head", self.head)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.repo / "docs/archive/REPO_MAP_2026-07.md").read_text(), self.original)
        self.assertIn("Canonical repository map", self.repomap.read_text())
        before = self.repomap.read_text()
        proc = run(self.repo, "python3", str(INSTALL))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NO_CHANGE", proc.stdout)
        self.assertEqual(self.repomap.read_text(), before)

    def test_existing_archive_never_overwritten(self):
        old = self.repo / "docs/archive/REPO_MAP_2026-07.md"
        old.parent.mkdir(parents=True)
        old.write_text("prior archive")
        proc = run(self.repo, "python3", str(INSTALL))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(old.read_text(), "prior archive")


if __name__ == "__main__":
    unittest.main()
