"""Negative and positive falsifiers for the bounded read-only Git census."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from asset_inventory import ANCHORS, SCHEMA, classify, inventory


def cmd(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, timeout=10)


class AssetInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        cmd(self.root, "init", "-q")
        cmd(self.root, "config", "user.name", "AEGIS test")
        cmd(self.root, "config", "user.email", "test@example.invalid")
        for name, data in {
            "ASSETS.md": "# inventory\n", "agents/agent_registry.json": json.dumps({"research": "a1", "finance": "a2"}),
            "research/graph.jsonl": "{}\n", "genomics/sequence.py": "print(1)\n",
            "studio/mockup.svg": "<svg/>\n", "supabase/migrations/001.sql": "select 1;\n",
            "harness/skill_tree.json": "{}\n", "FormalConjectures/Proof.lean": "theorem t : True := trivial\n",
            "hub/sales.csv": "a,b\n", "security/threat.md": "safety\n",
            "agents/tests/test_agent.py": "pass\n", "sovereign-omega-v2/AGENTS.md": "docs\n",
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        cmd(self.root, "add", ".")
        cmd(self.root, "commit", "-qm", "fixture")

    def test_schema_and_identity(self):
        out = inventory(self.root, "agent finance")
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(len(out["source"]["head"]), 40)
        self.assertEqual(out["source"]["tracked_files"], 12)

    def test_registry_declaration_not_execution(self):
        reg = inventory(self.root, "agent")["agent_registry"]
        self.assertEqual(reg["declared_roles"], 2)
        self.assertFalse(reg["runtime_tested"])

    def test_anchors_present_absent_explicit(self):
        anchors = inventory(self.root, "research")["anchors"]
        self.assertEqual(anchors["ASSETS.md"]["state"], "PRESENT_IN_GIT_HEAD")
        self.assertEqual(anchors["AGENTS.md"]["state"], "ABSENT_FROM_GIT_HEAD")
        self.assertEqual(set(anchors), set(ANCHORS))

    def test_sha_matches_committed_not_worktree(self):
        before = inventory(self.root, "assets")
        original_sha = before["anchors"]["ASSETS.md"]["sha256"]
        (self.root / "ASSETS.md").write_text("modified\n")
        after = inventory(self.root, "assets")
        self.assertEqual(after["anchors"]["ASSETS.md"]["sha256"], original_sha)
        self.assertTrue(after["source"]["dirty_worktree_excluded"])

    def test_untracked_file_not_in_inventory(self):
        (self.root / "research" / "secret.csv").write_text("private")
        result = inventory(self.root, "secret")
        self.assertEqual(result["candidate_paths"], [])
        self.assertEqual(result["source"]["tracked_files"], 12)

    def test_cross_domain_categories(self):
        out = inventory(self.root, "system")
        for name in ("code", "proofs", "datasets", "media_design", "science",
                     "business", "security", "agents", "operations", "tests", "documentation"):
            self.assertGreater(out["modalities"].get(name, 0), 0, name)

    def test_finance_candidates(self):
        out = inventory(self.root, "hub sales")
        self.assertEqual(out["candidate_paths"][0]["path"], "hub/sales.csv")
        self.assertEqual(out["candidate_paths"][0]["state"], "NAME_MATCH_NOT_CONTENT_REVIEWED")

    def test_ambiguous_task_is_not_semantic_validation(self):
        out = inventory(self.root, "unknown enterprise")
        self.assertEqual(out["candidate_search"], "PATH_TOKENS_ONLY_NOT_SEMANTIC_RECALL")
        self.assertEqual(out["reuse_status"], "NOT_VERIFIED")

    def test_external_unchecked(self):
        out = inventory(self.root, "all resources")
        self.assertTrue(all(v == "NOT_INSPECTED" for v in out["external_coverage"].values()))
        self.assertEqual(out["world_best"], "NOT_ESTABLISHED")
        self.assertEqual(out["external_benchmark"], "NOT_RUN")
        self.assertEqual(out["authority_effect"], "NONE")

    def test_deterministic(self):
        a = inventory(self.root, "research")
        b = inventory(self.root, "research")
        self.assertEqual(a, b)

    def test_invalid_task(self):
        for task in ("", "  ", "x" * 1001):
            with self.subTest(task=task[:10]):
                with self.assertRaises(ValueError):
                    inventory(self.root, task)

    def test_bad_limit(self):
        for n in (-1, 0, 101):
            with self.assertRaises(ValueError):
                inventory(self.root, "test", n)

    def test_no_git_repo_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                inventory(Path(d), "test")

    def test_corrupt_agent_registry_reports_invalid(self):
        p = self.root / "agents/agent_registry.json"
        p.write_text("{invalid")
        cmd(self.root, "add", ".")
        cmd(self.root, "commit", "-qm", "corrupt registry")
        self.assertEqual(inventory(self.root, "agents")["agent_registry"]["state"], "INVALID_REGISTRY_JSON")

    def test_absent_roles_are_not_zero(self):
        p = self.root / "agents/agent_registry.json"
        p.unlink()
        cmd(self.root, "add", "-u")
        cmd(self.root, "commit", "-qm", "remove registry")
        self.assertIsNone(inventory(self.root, "agents")["agent_registry"]["declared_roles"])

    def test_classification_does_not_overwrite_modalities(self):
        self.assertIn("media_design", classify("studio/picture.svg"))
        self.assertIn("user_experience", classify("studio/picture.svg"))
        self.assertIn("proofs", classify("FormalConjectures/Proof.lean"))

    def test_cli_failure_is_json_and_nonzero(self):
        script = str(Path(__file__).with_name("asset_inventory.py"))
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run([sys.executable, script, "--root", d, "foo"],
                                  capture_output=True, text=True, timeout=10)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stdout)["disposition"], "INVENTORY_FAILED")

    def test_cli_success(self):
        script = str(Path(__file__).with_name("asset_inventory.py"))
        proc = subprocess.run([sys.executable, script, "--root", str(self.root), "research"],
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["disposition"], "LOCAL_GIT_HEAD_ONLY")


if __name__ == "__main__":
    unittest.main()
