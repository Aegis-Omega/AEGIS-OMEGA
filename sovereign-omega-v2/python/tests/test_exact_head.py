#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate-exact-head.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_exact_head", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exact-head validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExactHeadTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        (self.root / "tracked.txt").write_text("v1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "base"], check=True)
        self.head = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()

    def test_clean_exact_head_is_admitted(self):
        receipt = load_validator().evaluate(self.root, self.head)
        self.assertEqual(receipt["outcome"], "ADMITTED")
        self.assertEqual(receipt["candidate_sha"], self.head)
        self.assertEqual(receipt["violations"], [])

    def test_short_sha_is_denied(self):
        receipt = load_validator().evaluate(self.root, self.head[:12])
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertIn("CANDIDATE_SHA_INVALID", receipt["violations"])

    def test_mismatched_head_is_denied(self):
        receipt = load_validator().evaluate(self.root, "0" * 40)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertIn("CANDIDATE_SHA_MISMATCH", receipt["violations"])

    def test_dirty_or_untracked_content_is_denied(self):
        (self.root / "untracked.txt").write_text("x\n", encoding="utf-8")
        receipt = load_validator().evaluate(self.root, self.head)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertIn("WORKTREE_NOT_EXACT_HEAD", receipt["violations"])


if __name__ == "__main__":
    main()
