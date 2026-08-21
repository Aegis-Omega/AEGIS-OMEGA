from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "reconcile-repository-universe.py"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_reconciler(tmp_path: Path, *, complete: bool = True) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    raw = {
        "schema_version": "AEGIS_REPO_UNIVERSE_V1",
        "authority": "REACHABILITY_EVIDENCE_ONLY",
        "repository_root": "/fixture/repo",
        "main_ref": "origin/main",
        "main_sha": "a" * 40,
        "history_complete": True,
        "branch_count": 3,
        "all_ref_commit_count": 9,
        "main_reachable_commit_count": 4,
        "commits_not_reachable_from_main": 5,
        "off_main_sample_truncated": False,
        "off_main_commit_sample": [],
        "branches": [
            {"branch": "main", "ref": "refs/remotes/origin/main", "tip": "a" * 40, "ahead_of_main": 0, "behind_main": 0, "contained_in_main": True},
            {"branch": "feat/alpha", "ref": "refs/remotes/origin/feat/alpha", "tip": "b" * 40, "ahead_of_main": 3, "behind_main": 0, "contained_in_main": False},
            {"branch": "feat/beta", "ref": "refs/remotes/origin/feat/beta", "tip": "c" * 40, "ahead_of_main": 2, "behind_main": 0, "contained_in_main": False},
        ],
        "epistemic_rule": "main is admitted state, not artifact existence",
    }
    prs = {
        "schema_version": "AEGIS_GITHUB_PR_CENSUS_V1",
        "complete": complete,
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "pull_requests": [
            {"number": 10, "state": "OPEN", "isDraft": False, "title": "alpha", "baseRefName": "main", "baseRefOid": "a" * 40, "headRefName": "feat/alpha", "headRefOid": "b" * 40, "mergeable": "MERGEABLE", "url": "https://example.invalid/pr/10"},
            {"number": 11, "state": "MERGED", "isDraft": False, "title": "historic beta", "baseRefName": "main", "baseRefOid": "1" * 40, "headRefName": "historic/beta", "headRefOid": "2" * 40, "mergeable": "UNKNOWN", "url": "https://example.invalid/pr/11"},
        ],
    }
    universe_path = tmp_path / "raw.json"
    prs_path = tmp_path / "prs.json"
    out_path = tmp_path / "out.json"
    write_json(universe_path, raw)
    write_json(prs_path, prs)
    subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-universe", str(universe_path), "--prs", str(prs_path), "--out", str(out_path)],
        check=True,
    )
    return json.loads(out_path.read_text(encoding="utf-8"))


class ReconciliationUniverseTests(unittest.TestCase):
    def with_tmp(self, name: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix=f"aegis-{name}-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        return root

    def test_main_is_admitted_anchor_not_knowledge_universe(self) -> None:
        doc = run_reconciler(self.with_tmp("main"))
        self.assertEqual(doc["schema_version"], "AEGIS_RECONCILIATION_UNIVERSE_V1")
        self.assertEqual(doc["canonical_main"]["sha"], "a" * 40)
        self.assertEqual(doc["knowledge_universe"]["commits_not_reachable_from_main"], 5)
        self.assertEqual(doc["knowledge_universe"]["all_ref_commit_count"], 9)
        self.assertEqual(doc["authority"], "DISCOVERY_EVIDENCE_ONLY")

    def test_open_and_closed_pr_lineage_is_preserved(self) -> None:
        doc = run_reconciler(self.with_tmp("prs"))
        prs = {item["number"]: item for item in doc["pull_requests"]}
        self.assertEqual(prs[10]["head_ref"], "feat/alpha")
        self.assertEqual(prs[10]["head_sha"], "b" * 40)
        self.assertEqual(prs[10]["base_ref"], "main")
        self.assertEqual(prs[11]["state"], "MERGED")
        self.assertEqual(prs[11]["head_sha"], "2" * 40)

    def test_branch_pr_same_head_is_linked_not_erased(self) -> None:
        doc = run_reconciler(self.with_tmp("link"))
        alpha = next(item for item in doc["branches"] if item["branch"] == "feat/alpha")
        self.assertEqual(alpha["tip"], "b" * 40)
        self.assertEqual(alpha["pr_numbers"], [10])
        self.assertTrue(any(item["number"] == 10 for item in doc["pull_requests"]))

    def test_incomplete_pr_discovery_fails_closed(self) -> None:
        doc = run_reconciler(self.with_tmp("incomplete"), complete=False)
        self.assertFalse(doc["discovery_complete"])
        self.assertIn("pull_requests", doc["incomplete_sources"])
        self.assertEqual(doc["deletion_authority"], "DENIED")
        self.assertEqual(doc["global_absence_claim_authority"], "DENIED")

    def test_output_is_deterministic_and_digest_bound(self) -> None:
        root = self.with_tmp("det")
        first = run_reconciler(root / "one")
        second = run_reconciler(root / "two")
        self.assertEqual(first, second)
        body = dict(first)
        digest = body.pop("manifest_sha256")
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        expected = hashlib.sha256(b"AEGIS_RECONCILIATION_UNIVERSE_V1\0" + encoded).hexdigest()
        self.assertEqual(digest, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
