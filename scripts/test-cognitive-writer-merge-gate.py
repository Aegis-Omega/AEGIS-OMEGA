#!/usr/bin/env python3
"""Exercise the merge gate against real Git objects, never candidate code."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/check-cognitive-writer-merge.py"
WORKFLOW = ".github/workflows/cognitive-manifest-refresh.yml"
APPROVED = (ROOT / WORKFLOW).read_bytes()
OLD = b"on: [push]\npermissions:\n  contents: write\n"


class MergeGateTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        self.writer = self.repo / WORKFLOW
        self.writer.parent.mkdir(parents=True)
        self.writer.write_bytes(OLD)
        self.commit("old writer")
        self.ancestor = self.git("rev-parse", "HEAD")
        self.writer.write_bytes(APPROVED)
        self.commit("harden writer")
        self.base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-b", "feature", self.ancestor)
        (self.repo / "feature.txt").write_text("unrelated change\n")
        self.commit("feature inherited old writer")
        self.head = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        self.git("merge", "--no-ff", "-m", "merge feature", self.head)
        self.merge = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-c", "user.name=Gate Test", "-c", "user.email=gate@example.invalid", *args],
            cwd=self.repo, text=True, stderr=subprocess.PIPE,
        ).strip()

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "-q", "-m", message)

    def check(self, *, base=None, head=None, merge=None):
        result = subprocess.run(
            [sys.executable, str(GATE), "--repo", str(self.repo),
             "--base-sha", base or self.base, "--head-sha", head or self.head,
             "--merge-sha", merge or self.merge], text=True, capture_output=True,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_unchanged_old_head_preserves_hardened_merge(self):
        # Checking the PR head instead of the merge must fail this test.
        code, receipt = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(receipt["outcome"], "PASS")
        self.assertEqual(receipt["merge_sha"], self.merge)
        self.assertEqual(receipt["parents"], [self.base, self.head])
        self.assertEqual(receipt["writer_sha256"],
                         "99f4c39ad780a77511347f7ac039557f428a0983f990f3304953dd2f636dd356")

    def test_resolved_merge_restoring_old_writer_is_denied(self):
        self.writer.write_bytes(OLD)
        self.git("add", WORKFLOW)
        self.git("commit", "--amend", "--no-edit", "-q")
        code, receipt = self.check(merge=self.git("rev-parse", "HEAD"))
        self.assertEqual((code, receipt["reason"]), (1, "WRITER_POLICY_MISMATCH"))

    def test_missing_or_symlink_writer_is_denied(self):
        self.writer.unlink()
        self.git("add", "--all")
        self.git("commit", "--amend", "--no-edit", "-q")
        code, receipt = self.check(merge=self.git("rev-parse", "HEAD"))
        self.assertEqual((code, receipt["reason"]), (1, "WRITER_NOT_REGULAR_FILE"))
        self.writer.symlink_to("elsewhere.yml")
        self.git("add", "--all")
        self.git("commit", "--amend", "--no-edit", "-q")
        code, receipt = self.check(merge=self.git("rev-parse", "HEAD"))
        self.assertEqual((code, receipt["reason"]), (1, "WRITER_NOT_REGULAR_FILE"))

    def test_stale_base_wrong_head_and_nonmerge_are_denied(self):
        for kwargs in ({"base": self.ancestor}, {"head": self.ancestor}, {"merge": self.head}):
            with self.subTest(kwargs=kwargs):
                code, receipt = self.check(**kwargs)
                self.assertEqual((code, receipt["reason"]), (1, "MERGE_PARENT_MISMATCH"))

    def test_refs_and_missing_objects_cannot_substitute_exact_commits(self):
        for value, reason in (("main", "INVALID_COMMIT_ID"), ("f" * 40, "GIT_OBJECT_UNAVAILABLE")):
            with self.subTest(value=value):
                code, receipt = self.check(merge=value)
                self.assertEqual((code, receipt["reason"]), (1, reason))

    def test_git_replace_cannot_disguise_the_candidate(self):
        good = self.merge
        self.writer.write_bytes(OLD)
        self.git("add", "--all")
        self.git("commit", "--amend", "--no-edit", "-q")
        bad = self.git("rev-parse", "HEAD")
        self.git("replace", bad, good)
        code, receipt = self.check(merge=bad)
        self.assertEqual((code, receipt["reason"]), (1, "WRITER_POLICY_MISMATCH"))


if __name__ == "__main__":
    main()
