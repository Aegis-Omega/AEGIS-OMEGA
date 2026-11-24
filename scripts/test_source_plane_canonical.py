#!/usr/bin/env python3
"""Real AEGIS repository-knowledge bridge tests, no mocks of canonical logic.

The source file under test is the existing (and unchanged)
`harness/sdk/repository_knowledge.py`. This must execute in an AEGIS checkout,
not inside a standalone bundle missing the real module.
"""
from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "harness" / "sdk"
SOURCE = SDK / "source_plane.py"
CANONICAL = SDK / "repository_knowledge.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class CanonicalRepositoryKnowledgeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fail rather than silently replacing actual integration with a stub.
        if not CANONICAL.is_file():
            raise RuntimeError("real harness/sdk/repository_knowledge.py required; test in canonical checkout")
        cls.plane = load(SOURCE, "aegis_source_plane_real_binding")
        cls.knowledge = load(CANONICAL, "aegis_repository_knowledge_real_binding")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo_a, self.repo_b = base / "ae", base / "rh"
        self.names = ("Aegis-Omega/AEGIS-OMEGA", "Aegis-Omega/formal-conjectures")
        for path in (self.repo_a, self.repo_b):
            path.mkdir()
            self.git(path, "init", "-q")
            self.git(path, "config", "user.name", "AEGIS Test")
            self.git(path, "config", "user.email", "aegis@example.invalid")
        (self.repo_a / "harness" / "sdk").mkdir(parents=True)
        (self.repo_a / "harness" / "sdk" / "example.py").write_text("AEGIS = 1\n")
        (self.repo_b / "lean-toolchain").write_text("leanprover/lean4:v4.33.1\n")
        for path in (self.repo_a, self.repo_b):
            self.git(path, "add", "-A")
            self.git(path, "commit", "-qm", "first")
        self.mapping = dict(zip(self.names, (self.repo_a, self.repo_b)))
        self.requests = [
            self.plane.ArtifactRequest(self.names[0], self.git(self.repo_a, "rev-parse", "HEAD"), "harness/sdk/example.py"),
            self.plane.ArtifactRequest(self.names[1], self.git(self.repo_b, "rev-parse", "HEAD"), "lean-toolchain"),
        ]
        self.manifest = self.plane.SourcePlane(
            transport=self.plane.LocalGitTransport(self.mapping)
        ).manifest(self.requests)

    @staticmethod
    def git(root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()

    def test_canonical_sha256_encoding_matches_exactly(self):
        payload = {"Ω": "aegis", "nested": [1, None, {"flag": True}]}
        self.assertEqual(self.plane.canonical_bytes(payload), self.knowledge._canonical_json(payload))
        self.assertEqual(self.plane.canonical_sha256(payload), self.knowledge._digest(payload))

    def test_real_canonical_snapshot_and_verify_per_repo(self):
        for name, root in self.mapping.items():
            snap = self.knowledge.build_snapshot(root, repository_id=0, repository_full_name=name)
            self.assertEqual(snap["repository_full_name"], name)
            self.assertEqual(snap["source_head_sha"], self.git(root, "rev-parse", "HEAD"))
            self.assertEqual(snap["source_tree_sha"], self.git(root, "rev-parse", "HEAD^{tree}"))
            self.assertEqual(self.knowledge.verify_snapshot(root, snap, expected_repository_id=0)["status"], "ESTABLISHED")

    def test_source_plane_manifest_admitted_as_readonly_evidence(self):
        receipt = self.plane.verify_local_repository_binding(self.manifest, self.mapping)
        self.assertEqual(receipt, {"status": "ESTABLISHED", "reason_codes": [], "authority": "NONE"})

    def test_unchanged_worktree_and_no_new_branch(self):
        before = {name: (self.git(root, "status", "--porcelain"),
                         self.git(root, "branch", "--show-current"),
                         self.git(root, "rev-parse", "HEAD"))
                  for name, root in self.mapping.items()}
        self.plane.verify_local_repository_binding(self.manifest, self.mapping)
        after = {name: (self.git(root, "status", "--porcelain"),
                        self.git(root, "branch", "--show-current"),
                        self.git(root, "rev-parse", "HEAD"))
                 for name, root in self.mapping.items()}
        self.assertEqual(before, after)

    def test_stale_head_denied_by_real_canonical(self):
        (self.repo_b / "new.md").write_text("changed\n")
        self.git(self.repo_b, "add", "-A")
        self.git(self.repo_b, "commit", "-qm", "second")
        receipt = self.plane.verify_local_repository_binding(self.manifest, self.mapping)
        self.assertEqual(receipt["status"], "DENIED")
        self.assertIn("SOURCE_HEAD_MISMATCH:" + self.names[1], receipt["reason_codes"])

    def test_worktree_modification_does_not_lie_about_committed_head(self):
        (self.repo_a / "harness/sdk/example.py").write_text("UNCOMMITTED = True\n")
        receipt = self.plane.verify_local_repository_binding(self.manifest, self.mapping)
        self.assertEqual(receipt["status"], "ESTABLISHED")
        # Only Git HEAD is attested. Uncommitted working-tree changes are explicitly
        # out of scope and must never be claimed as verified by this receipt.
        self.assertEqual(receipt["authority"], "NONE")

    def test_tampered_blob_with_recomputed_manifest_digest_denied(self):
        bad = copy.deepcopy(self.manifest)
        bad["artifacts"][0]["content_sha256"] = "0" * 64
        unsigned = {k: v for k, v in bad.items() if k != "manifest_sha256"}
        bad["manifest_sha256"] = self.plane.canonical_sha256({"domain": self.plane.SCHEMA_VERSION, "payload": unsigned})
        receipt = self.plane.verify_local_repository_binding(bad, self.mapping)
        self.assertEqual(receipt["status"], "DENIED")
        self.assertTrue(any(x.startswith("ARTIFACT_CONTENT_MISMATCH:") for x in receipt["reason_codes"]))

    def test_missing_repo_mapping_fails_closed(self):
        with self.assertRaises(self.plane.SourcePlaneError):
            self.plane.verify_local_repository_binding(self.manifest, {self.names[0]: self.repo_a})


if __name__ == "__main__":
    unittest.main(verbosity=2)
