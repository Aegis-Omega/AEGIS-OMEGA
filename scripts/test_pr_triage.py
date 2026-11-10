"""Isolated native Git fixtures; no GitHub/network/billing operations."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import importlib.util
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pr_triage_safe", HERE / "pr-triage.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

DAY = dt.date(2026, 11, 3)

def run(*args, cwd=None):
    return subprocess.check_output(["git", *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()

class TriageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        run("init", "-q", "-b", "main", cwd=self.root)
        run("config", "user.email", "test@example.invalid", cwd=self.root)
        run("config", "user.name", "AEGIS Test", cwd=self.root)
        (self.root/"core.txt").write_text("original\n")
        run("add", ".", cwd=self.root)
        run("commit", "-qm", "base", cwd=self.root)
        self.base = run("rev-parse", "HEAD", cwd=self.root)
        run("branch", "-f", "origin/main", cwd=self.root)
        # A unique old candidate (closed-but-unmerged analogue).
        run("switch", "-qc", "candidate", cwd=self.root)
        (self.root/"valuable_test.py").write_text("assert 1 + 1 == 2\n")
        run("add", ".", cwd=self.root)
        run("commit", "-qm", "unique candidate", cwd=self.root)
        self.candidate = run("rev-parse", "HEAD", cwd=self.root)
        run("switch", "-q", "main", cwd=self.root)
        self.previous = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(lambda: os.chdir(self.previous))

    def pr(self, **kw):
        return dict(number=761, headRefOid=self.candidate,
                    headRefName="feat/issue-748-public-workpack", baseRefName="main",
                    updatedAt="2026-10-11T00:00:00Z", **kw)

    def test_stale_unique_candidate_must_not_close(self):
        self.assertEqual(mod.classify(self.pr(), main_sha=self.base, today=DAY),
                         ("REVIEW", "UNINTEGRATED_OR_UNRESOLVED_FILE_BYTES"))

    def test_missing_commit_must_not_close(self):
        p=self.pr();p["headRefOid"]="f"*40
        self.assertEqual(mod.classify(p,main_sha=self.base,today=DAY)[0],"REVIEW")

    def test_old_original_bug_no_merge_base_is_not_no_changes(self):
        p=self.pr();p["headRefOid"]="a"*40
        self.assertEqual(mod.classify(p,main_sha=self.base,today=DAY)[0],"REVIEW")

    def test_main_contains_head_is_only_candidate_close(self):
        p=self.pr();p["headRefOid"]=self.base
        self.assertEqual(mod.classify(p,main_sha=self.base,today=DAY)[0],"CANDIDATE_CLOSE")

    def test_stack_dependency_cannot_auto_close(self):
        p=self.pr();p["baseRefName"]="missing/branch"
        self.assertEqual(mod.classify(p,main_sha=self.base,today=DAY)[0],"REVIEW")

    def test_proof_lane_requires_review_even_if_integrated(self):
        p=self.pr();p["headRefName"]="proof/long-lived"
        p["headRefOid"]=self.base
        self.assertEqual(mod.classify(p,main_sha=self.base,today=DAY)[0],"REVIEW")

    def test_operator_preserve_698(self):
        p=self.pr();p["number"]=698
        self.assertEqual(mod.classify(p,main_sha=self.base,today=DAY)[0],"KEEP")

    def test_future_timestamp_denied(self):
        p=self.pr();p["updatedAt"]="2027-01-01T00:00:00Z"
        self.assertEqual(mod.classify(p,main_sha=self.base,today=DAY)[0],"REVIEW")

    def test_duplicate_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            mod.render([self.pr(), self.pr()], DAY)

    def test_all_file_equal_state_candidate_only(self):
        # Candidate change is independently recreated in main.
        (self.root/"valuable_test.py").write_text("assert 1 + 1 == 2\n")
        run("add", ".", cwd=self.root)
        run("commit", "-qm", "main independent equivalent", cwd=self.root)
        head=run("rev-parse", "HEAD", cwd=self.root)
        self.assertEqual(mod.classify(self.pr(),main_sha=head,today=DAY),
                         ("CANDIDATE_CLOSE", "ALL_CHANGED_FILE_BLOBS_EQUAL_MAIN"))

    def test_invalid_sha(self):
        p=self.pr();p["headRefOid"]="invalid"
        self.assertEqual(mod.classify(p,main_sha=self.base,today=DAY)[0],"REVIEW")

    def test_render_has_no_close_verdict(self):
        txt=mod.render([self.pr()], DAY)
        self.assertIn("REVIEW",txt)
        self.assertNotIn("\tclose\t",txt.lower())

if __name__ == "__main__":
    unittest.main(verbosity=2)
