#!/usr/bin/env python3
"""Offline contracts for the read-only topological audit."""
from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("aegis_topology.py")
spec = importlib.util.spec_from_file_location("aegis_topology", MODULE)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout.decode().strip()


class TopologyContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "tester@example.invalid")
        git(self.repo, "config", "user.name", "AEGIS Test")
        for paths in module.ANCHORS.values():
            for path in paths:
                f = self.repo / path
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("fixture\n")
        inventory = self.repo / "reports/inventory.json"
        inventory.parent.mkdir(parents=True, exist_ok=True)
        inventory.write_text(json.dumps({"generated_from": "a" * 40}))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "fixture")

    def test_aegis_specific_roots_have_explicit_owners(self):
        expected = {".aegis": "evidence", "kernel-one": "runtime", "schemas": "packages"}
        for root, owner in expected.items():
            self.assertEqual(module.OWNERS.get(root), owner)

    def test_exact_head_and_tree(self):
        a = module.audit(self.repo)
        self.assertEqual(a["head"], git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(a["tree"], git(self.repo, "rev-parse", "HEAD^{tree}"))
        self.assertEqual(a["status"], "PASS")
        self.assertTrue(all(v["exists_at_head"] for v in a["anchors"]))

    def test_deterministic_receipt(self):
        self.assertEqual(module.audit(self.repo), module.audit(self.repo))
        self.assertEqual(len(module.audit(self.repo)["snapshot_sha256"]), 64)

    def test_historical_inventory_not_promoted(self):
        a = module.audit(self.repo)
        self.assertEqual(a["historical_docs"][0]["head_freshness"], "HISTORICAL")
        self.assertNotEqual(a["historical_docs"][0]["declared_commit"], a["head"])

    def test_absent_anchor_fails_closed(self):
        path = self.repo / "agents/coordinator.py"
        path.unlink()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "remove anchor")
        a = module.audit(self.repo)
        self.assertEqual(a["status"], "FAILED")
        self.assertIn("MISSING_ANCHOR:agents/coordinator.py", a["errors"])

    def test_unknown_root_is_review_not_deleted(self):
        p = self.repo / "new-experiment/hello.py"
        p.parent.mkdir()
        p.write_text("print('hello')\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "new root")
        a = module.audit(self.repo)
        self.assertEqual(a["status"], "REVIEW_REQUIRED")
        self.assertIn("new-experiment", a["unclassified_roots"])
        self.assertTrue(p.exists())

    def test_worktree_modification_does_not_fake_head(self):
        a = module.audit(self.repo)
        (self.repo / "README.md").write_text("dirty uncommitted value")
        self.assertEqual(module.audit(self.repo), a)

    def test_sorted_and_integrity(self):
        x = module.audit(self.repo)
        self.assertEqual([r["root"] for r in x["roots"]], sorted(r["root"] for r in x["roots"]))
        self.assertEqual(sum(r["tracked_files"] for r in x["roots"]), x["tracked_files"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
