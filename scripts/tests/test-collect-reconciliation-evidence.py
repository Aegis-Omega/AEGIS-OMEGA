from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "collect-reconciliation-evidence.py"


def run_collector(tmp: Path) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    lineage = {
        "schema_version": "AEGIS_WORK_LINEAGE_V1",
        "authority": "LINEAGE_DISCOVERY_EVIDENCE_ONLY",
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "source_universe_manifest_sha256": "1" * 64,
        "canonical_main": {"ref": "origin/main", "sha": "a" * 40, "authority": "ADMITTED_RUNTIME_ANCHOR"},
        "discovery_complete": True,
        "active_spine": ["pr:10"],
        "historical_reconciled": {},
        "side_lineages": [],
        "missing_declared_work_ids": [],
        "work_items": [
            {"work_id": "pr:10", "pr_number": 10, "current_ref": "feat/a", "current_head": "b" * 40, "base_ref": "main", "base_sha": "a" * 40, "classification": "ACTIVE_SPINE", "draft": False},
            {"work_id": "pr:11", "pr_number": 11, "current_ref": "feat/b", "current_head": "c" * 40, "base_ref": "main", "base_sha": "a" * 40, "classification": "UNKNOWN_FAIL_CLOSED", "draft": True},
            {"work_id": "legacy-tip:" + "d" * 64, "pr_number": None, "current_ref": "legacy", "current_head": "d" * 40, "base_ref": None, "base_sha": None, "classification": "UNKNOWN_FAIL_CLOSED", "draft": None},
        ],
        "branch_creation_authority": "LINEAGE_RESOLVER_REQUIRED",
        "rules": [],
        "manifest_sha256": "e" * 64,
    }
    prs = {
        "schema_version": "AEGIS_GITHUB_PR_CENSUS_V1",
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "complete": True,
        "pull_requests": [
            {"number": 10, "state": "OPEN", "isDraft": False, "title": "A", "baseRefName": "main", "baseRefOid": "a" * 40, "headRefName": "feat/a", "headRefOid": "b" * 40, "mergeable": "MERGEABLE", "url": "https://example.invalid/10"},
            {"number": 11, "state": "OPEN", "isDraft": True, "title": "B", "baseRefName": "main", "baseRefOid": "0" * 40, "headRefName": "feat/b", "headRefOid": "c" * 40, "mergeable": "CONFLICTING", "url": "https://example.invalid/11"},
        ],
    }
    lp, pp, op = tmp / "lineage.json", tmp / "prs.json", tmp / "evidence.json"
    lp.write_text(json.dumps(lineage, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    pp.write_text(json.dumps(prs, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(SCRIPT), "--lineage", str(lp), "--prs", str(pp), "--out", str(op)], check=True)
    return json.loads(op.read_text(encoding="utf-8"))


class ConservativeEvidenceCollectorTests(unittest.TestCase):
    def tmp(self, label: str) -> Path:
        p = Path(tempfile.mkdtemp(prefix=f"aegis-evidence-{label}-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(p, ignore_errors=True))
        return p

    def test_pr_structural_metadata_is_bound_to_workid(self) -> None:
        doc = run_collector(self.tmp("bind"))
        a = doc["work"]["pr:10"]
        self.assertEqual(a["observed_head"], "b" * 40)
        self.assertTrue(a["mergeable"])
        self.assertEqual(a["expected_parent_sha"], "a" * 40)
        self.assertEqual(a["current_parent_sha"], "a" * 40)

    def test_conflicting_pr_maps_mergeable_false_and_preserves_parent_drift(self) -> None:
        doc = run_collector(self.tmp("conflict"))
        b = doc["work"]["pr:11"]
        self.assertFalse(b["mergeable"])
        self.assertEqual(b["expected_parent_sha"], "a" * 40)
        self.assertEqual(b["current_parent_sha"], "0" * 40)

    def test_collector_never_fabricates_exact_head_verification_or_completeness(self) -> None:
        doc = run_collector(self.tmp("conservative"))
        self.assertFalse(doc["complete"])
        self.assertEqual(doc["coverage"], "STRUCTURAL_PR_METADATA_ONLY")
        self.assertFalse(doc["work"]["pr:10"]["exact_head_verified"])
        self.assertEqual(doc["work"]["pr:10"]["verification_roots"], [])

    def test_branch_only_legacy_work_gets_no_fabricated_pr_evidence(self) -> None:
        doc = run_collector(self.tmp("legacy"))
        self.assertNotIn("legacy-tip:" + "d" * 64, doc["work"])

    def test_output_is_deterministic(self) -> None:
        root = self.tmp("det")
        self.assertEqual(run_collector(root / "a"), run_collector(root / "b"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
