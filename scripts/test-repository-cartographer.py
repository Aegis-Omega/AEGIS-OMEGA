#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "harness" / "sdk" / "repository_knowledge.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def load_module():
    spec = importlib.util.spec_from_file_location("aegis_repository_knowledge", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


class RepositoryCartographerContract(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "aegis@example.invalid")
        git(self.repo, "config", "user.name", "AEGIS Test")

        write(self.repo, "WORKFLOW.md", "use what exists\n")
        write(self.repo, "REPO_MAP.md", "legacy map\n")
        write(
            self.repo,
            "reports/inventory.json",
            json.dumps({"generated_from": "1" * 40, "generated": "2026-07-12"}) + "\n",
        )
        write(self.repo, "harness/skill_tree.json", '{"skills":[{"skill_id":"existing_skill"}]}\n')
        write(self.repo, "agents/engineering.py", "CAPABILITY = 'engineering'\n")
        write(self.repo, ".github/workflows/ci.yml", "name: CI\n")
        write(self.repo, "supabase/migrations/001.sql", "select 1;\n")
        write(self.repo, "formal/theories/Foo.v", "Theorem foo : True. Proof. exact I. Qed.\n")
        write(self.repo, "docs/spec.md", "# Spec\n")
        write(self.repo, "scripts/run.sh", "#!/bin/sh\nexit 0\n")
        write(self.repo, "tests/test_x.py", "assert True\n")
        commit_all(self.repo, "initial")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_production_module_exists(self) -> None:
        self.assertTrue(MODULE_PATH.exists(), "repository knowledge module is not implemented")

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: cartographer module absent")
    def test_snapshot_is_exact_head_content_addressed_and_deterministic(self) -> None:
        mod = load_module()
        first = mod.build_snapshot(
            self.repo,
            repository_id=123,
            repository_full_name="Aegis-Omega/AEGIS-OMEGA",
        )
        second = mod.build_snapshot(
            self.repo,
            repository_id=123,
            repository_full_name="Aegis-Omega/AEGIS-OMEGA",
        )

        self.assertEqual(first, second)
        self.assertEqual(first["source_head_sha"], git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(first["source_tree_sha"], git(self.repo, "rev-parse", "HEAD^{tree}"))
        self.assertEqual(first["repository_id"], 123)
        self.assertEqual(first["repository_full_name"], "Aegis-Omega/AEGIS-OMEGA")
        self.assertEqual(first["knowledge_status"], "ESTABLISHED")
        self.assertRegex(first["artifacts_digest"], r"^[0-9a-f]{64}$")
        self.assertRegex(first["snapshot_digest"], r"^[0-9a-f]{64}$")

        paths = [item["path"] for item in first["artifacts"]]
        self.assertEqual(paths, sorted(paths))
        by_path = {item["path"]: item for item in first["artifacts"]}
        self.assertEqual(by_path[".github/workflows/ci.yml"]["category"], "workflow")
        self.assertEqual(by_path["agents/engineering.py"]["category"], "agent")
        self.assertEqual(by_path["supabase/migrations/001.sql"]["category"], "migration")
        self.assertEqual(by_path["formal/theories/Foo.v"]["category"], "formal")
        self.assertEqual(by_path["tests/test_x.py"]["category"], "test")
        self.assertEqual(by_path["docs/spec.md"]["category"], "documentation")
        self.assertEqual(first["legacy_inventory"]["state"], "STALE_DECLARED_HEAD")
        self.assertEqual(first["legacy_inventory"]["declared_head"], "1" * 40)

        verification = mod.verify_snapshot(self.repo, first, expected_repository_id=123)
        self.assertEqual(verification["status"], "ESTABLISHED")
        self.assertEqual(verification["reason_codes"], [])

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: cartographer module absent")
    def test_old_snapshot_is_denied_after_head_moves(self) -> None:
        mod = load_module()
        snapshot = mod.build_snapshot(self.repo, repository_id=123)
        write(self.repo, "agents/engineering.py", "CAPABILITY = 'engineering_v2'\n")
        commit_all(self.repo, "move head")

        verification = mod.verify_snapshot(self.repo, snapshot, expected_repository_id=123)
        self.assertEqual(verification["status"], "DENIED")
        self.assertIn("SOURCE_HEAD_MISMATCH", verification["reason_codes"])
        self.assertIn("SOURCE_TREE_MISMATCH", verification["reason_codes"])

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: cartographer module absent")
    def test_delta_is_path_and_blob_exact(self) -> None:
        mod = load_module()
        before = mod.build_snapshot(self.repo, repository_id=123)
        write(self.repo, "agents/engineering.py", "CAPABILITY = 'changed'\n")
        write(self.repo, "docs/new.md", "# New\n")
        (self.repo / "scripts" / "run.sh").unlink()
        commit_all(self.repo, "delta")
        after = mod.build_snapshot(self.repo, repository_id=123)

        delta = mod.compute_delta(before, after)
        self.assertEqual(delta["from_head_sha"], before["source_head_sha"])
        self.assertEqual(delta["to_head_sha"], after["source_head_sha"])
        self.assertEqual(delta["added"], ["docs/new.md"])
        self.assertEqual(delta["deleted"], ["scripts/run.sh"])
        self.assertEqual(delta["modified"], ["agents/engineering.py"])
        self.assertRegex(delta["delta_digest"], r"^[0-9a-f]{64}$")

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: cartographer module absent")
    def test_tampered_snapshot_document_is_denied(self) -> None:
        mod = load_module()
        snapshot = mod.build_snapshot(self.repo, repository_id=123)
        tampered = copy.deepcopy(snapshot)
        tampered["artifacts"][0]["path"] = "forged/path"

        verification = mod.verify_snapshot_document(tampered, expected_repository_id=123)
        self.assertEqual(verification["status"], "DENIED")
        self.assertIn("ARTIFACTS_DIGEST_MISMATCH", verification["reason_codes"])
        self.assertIn("SNAPSHOT_DIGEST_MISMATCH", verification["reason_codes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
