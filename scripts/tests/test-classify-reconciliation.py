from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "classify-reconciliation.py"


def work_item(work_id: str, head_char: str, *, active=False, historical=False, side=False, draft=False, superseded_by=None):
    return {
        "work_id": work_id,
        "identity_source": "GITHUB_PR_NUMBER",
        "identity_stability": "STABLE",
        "pr_number": int(work_id.split(":")[1]),
        "title": work_id,
        "objective_digest": "1" * 64,
        "current_ref": f"ref/{work_id}",
        "current_head": head_char * 40,
        "base_ref": "main",
        "base_sha": "a" * 40,
        "parent_work_ids": [],
        "lineage_root": "a" * 40,
        "state": "OPEN",
        "draft": draft,
        "verification_state": "NOT_REEVALUATED_BY_RECONCILIATION",
        "admission_state": "NOT_CLASSIFIED_FOR_ADMISSION",
        "classification": "ACTIVE_SPINE" if active else ("HISTORICAL_EVIDENCE_ONLY" if historical else "UNKNOWN_FAIL_CLOSED"),
        "declared_side_lineage": side,
        "superseded_by": superseded_by,
    }


def lineage() -> dict:
    items = [
        work_item("pr:1", "b", active=True),
        work_item("pr:2", "c", active=True),
        work_item("pr:3", "d", active=True),
        work_item("pr:4", "e", side=True),
        work_item("pr:5", "f"),
        work_item("pr:6", "6"),
        work_item("pr:7", "7"),
        work_item("pr:8", "8", historical=True, superseded_by="pr:2"),
        work_item("pr:9", "9", active=True, draft=True),
    ]
    return {
        "schema_version": "AEGIS_WORK_LINEAGE_V1",
        "authority": "LINEAGE_DISCOVERY_EVIDENCE_ONLY",
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "source_universe_manifest_sha256": "2" * 64,
        "canonical_main": {"ref": "origin/main", "sha": "a" * 40, "authority": "ADMITTED_RUNTIME_ANCHOR"},
        "discovery_complete": True,
        "active_spine": ["pr:1", "pr:2", "pr:3", "pr:9"],
        "historical_reconciled": {"pr:8": "pr:2"},
        "side_lineages": [["pr:4"]],
        "missing_declared_work_ids": [],
        "work_items": items,
        "branch_creation_authority": "LINEAGE_RESOLVER_REQUIRED",
        "rules": [],
        "manifest_sha256": "3" * 64,
    }


def evidence(*, complete=True) -> dict:
    return {
        "schema_version": "AEGIS_RECONCILIATION_EVIDENCE_V1",
        "authority": "CLASSIFICATION_EVIDENCE_ONLY",
        "complete": complete,
        "source_lineage_manifest_sha256": "3" * 64,
        "work": {
            "pr:1": {
                "observed_head": "b" * 40,
                "mergeable": True,
                "exact_head_verified": True,
                "expected_parent_sha": "a" * 40,
                "current_parent_sha": "a" * 40,
                "blockers": [],
                "verification_roots": ["a1" * 32],
                "unique_capability_evidence_roots": [],
                "recovery_required": False,
                "containment_proof": None
            },
            "pr:2": {
                "observed_head": "c" * 40,
                "mergeable": True,
                "exact_head_verified": True,
                "expected_parent_sha": "b" * 40,
                "current_parent_sha": "0" * 40,
                "blockers": [],
                "verification_roots": ["a2" * 32],
                "unique_capability_evidence_roots": [],
                "recovery_required": False,
                "containment_proof": None
            },
            "pr:3": {
                "observed_head": "d" * 40,
                "mergeable": True,
                "exact_head_verified": False,
                "expected_parent_sha": "a" * 40,
                "current_parent_sha": "a" * 40,
                "blockers": [],
                "verification_roots": [],
                "unique_capability_evidence_roots": [],
                "recovery_required": False,
                "containment_proof": None
            },
            "pr:4": {
                "observed_head": "e" * 40,
                "mergeable": True,
                "exact_head_verified": False,
                "expected_parent_sha": "a" * 40,
                "current_parent_sha": "a" * 40,
                "blockers": [],
                "verification_roots": [],
                "unique_capability_evidence_roots": ["b4" * 32],
                "recovery_required": False,
                "containment_proof": None
            },
            "pr:5": {
                "observed_head": "f" * 40,
                "mergeable": True,
                "exact_head_verified": False,
                "expected_parent_sha": "a" * 40,
                "current_parent_sha": "a" * 40,
                "blockers": ["SECURITY_REVIEW_PENDING"],
                "verification_roots": [],
                "unique_capability_evidence_roots": [],
                "recovery_required": False,
                "containment_proof": None
            },
            "pr:6": {
                "observed_head": "6" * 40,
                "mergeable": True,
                "exact_head_verified": False,
                "expected_parent_sha": "a" * 40,
                "current_parent_sha": "a" * 40,
                "blockers": [],
                "verification_roots": [],
                "unique_capability_evidence_roots": [],
                "recovery_required": False,
                "containment_proof": {
                    "method": "GIT_MERGE_BASE_IS_ANCESTOR",
                    "verified": True,
                    "candidate_head": "6" * 40,
                    "container_ref": "main",
                    "container_head": "a" * 40
                }
            },
            "pr:7": {
                "observed_head": "7" * 40,
                "mergeable": True,
                "exact_head_verified": False,
                "expected_parent_sha": "a" * 40,
                "current_parent_sha": "a" * 40,
                "blockers": [],
                "verification_roots": [],
                "unique_capability_evidence_roots": [],
                "recovery_required": True,
                "containment_proof": None
            },
            "pr:8": {
                "observed_head": "8" * 40,
                "mergeable": True,
                "exact_head_verified": True,
                "expected_parent_sha": "a" * 40,
                "current_parent_sha": "a" * 40,
                "blockers": [],
                "verification_roots": ["a8" * 32],
                "unique_capability_evidence_roots": [],
                "recovery_required": False,
                "containment_proof": None
            },
            "pr:9": {
                "observed_head": "9" * 40,
                "mergeable": True,
                "exact_head_verified": True,
                "expected_parent_sha": "a" * 40,
                "current_parent_sha": "a" * 40,
                "blockers": [],
                "verification_roots": ["a9" * 32],
                "unique_capability_evidence_roots": [],
                "recovery_required": False,
                "containment_proof": None
            }
        }
    }


def run_classifier(tmp: Path, *, evidence_doc=None) -> tuple[dict, Path]:
    tmp.mkdir(parents=True, exist_ok=True)
    lp = tmp / "lineage.json"
    ep = tmp / "evidence.json"
    op = tmp / "classification.json"
    dp = tmp / "decisions.jsonl"
    lp.write_text(json.dumps(lineage(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    ep.write_text(json.dumps(evidence_doc if evidence_doc is not None else evidence(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    subprocess.run([
        sys.executable, str(SCRIPT),
        "--lineage", str(lp), "--evidence", str(ep),
        "--out", str(op), "--decisions", str(dp)
    ], check=True)
    return json.loads(op.read_text(encoding="utf-8")), dp


class ClassificationTests(unittest.TestCase):
    def tmp(self, label: str) -> Path:
        p = Path(tempfile.mkdtemp(prefix=f"aegis-classify-{label}-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(p, ignore_errors=True))
        return p

    def test_exact_head_verified_active_work_can_be_ready_to_admit(self) -> None:
        doc, _ = run_classifier(self.tmp("ready"))
        by_id = {x["work_id"]: x for x in doc["classifications"]}
        self.assertEqual(by_id["pr:1"]["classification"], "READY_TO_ADMIT")

    def test_parent_movement_requires_reverify(self) -> None:
        doc, _ = run_classifier(self.tmp("parent"))
        by_id = {x["work_id"]: x for x in doc["classifications"]}
        self.assertEqual(by_id["pr:2"]["classification"], "NEEDS_REVERIFY")
        self.assertIn("PARENT_SHA_CHANGED", by_id["pr:2"]["reasons"])

    def test_mergeable_alone_never_means_ready(self) -> None:
        doc, _ = run_classifier(self.tmp("mergeable"))
        by_id = {x["work_id"]: x for x in doc["classifications"]}
        self.assertEqual(by_id["pr:3"]["classification"], "ACTIVE_SPINE")
        self.assertNotEqual(by_id["pr:3"]["classification"], "READY_TO_ADMIT")

    def test_blocker_and_unique_side_capability_are_preserved(self) -> None:
        doc, _ = run_classifier(self.tmp("blockunique"))
        by_id = {x["work_id"]: x for x in doc["classifications"]}
        self.assertEqual(by_id["pr:4"]["classification"], "UNIQUE_SIDE_CAPABILITY")
        self.assertEqual(by_id["pr:5"]["classification"], "BLOCKED")

    def test_redundant_requires_exact_mechanical_containment(self) -> None:
        doc, _ = run_classifier(self.tmp("redundant"))
        by_id = {x["work_id"]: x for x in doc["classifications"]}
        self.assertEqual(by_id["pr:6"]["classification"], "REDUNDANT_PROVEN")

        bad = evidence()
        bad["work"]["pr:6"]["containment_proof"]["candidate_head"] = "0" * 40
        bad_doc, _ = run_classifier(self.tmp("badcontainment"), evidence_doc=bad)
        bad_by_id = {x["work_id"]: x for x in bad_doc["classifications"]}
        self.assertEqual(bad_by_id["pr:6"]["classification"], "UNKNOWN_FAIL_CLOSED")

    def test_recovery_and_historical_work_are_never_deleted_by_classification(self) -> None:
        doc, _ = run_classifier(self.tmp("recovery"))
        by_id = {x["work_id"]: x for x in doc["classifications"]}
        self.assertEqual(by_id["pr:7"]["classification"], "RECOVERY_REQUIRED")
        self.assertEqual(by_id["pr:8"]["classification"], "HISTORICAL_EVIDENCE_ONLY")
        self.assertFalse(by_id["pr:7"]["destructive_action_allowed"])
        self.assertFalse(by_id["pr:8"]["destructive_action_allowed"])

    def test_draft_cannot_be_ready_even_with_green_evidence(self) -> None:
        doc, _ = run_classifier(self.tmp("draft"))
        by_id = {x["work_id"]: x for x in doc["classifications"]}
        self.assertEqual(by_id["pr:9"]["classification"], "ACTIVE_SPINE")

    def test_incomplete_evidence_defaults_unknown_fail_closed_for_unclassified_work(self) -> None:
        ev = evidence(complete=False)
        del ev["work"]["pr:5"]
        doc, _ = run_classifier(self.tmp("incomplete"), evidence_doc=ev)
        by_id = {x["work_id"]: x for x in doc["classifications"]}
        self.assertEqual(by_id["pr:5"]["classification"], "UNKNOWN_FAIL_CLOSED")
        self.assertFalse(by_id["pr:5"]["destructive_action_allowed"])

    def test_decision_chain_verifies_and_tamper_fails(self) -> None:
        _, decisions = run_classifier(self.tmp("chain"))
        subprocess.run([sys.executable, str(SCRIPT), "--verify-decisions", str(decisions)], check=True)
        lines = decisions.read_text(encoding="utf-8").splitlines()
        mutated = json.loads(lines[2])
        mutated["classification"] = "BLOCKED"
        lines[2] = json.dumps(mutated, sort_keys=True, separators=(",", ":"))
        decisions.write_text("\n".join(lines) + "\n", encoding="utf-8")
        failed = subprocess.run([sys.executable, str(SCRIPT), "--verify-decisions", str(decisions)], check=False)
        self.assertNotEqual(failed.returncode, 0)

    def test_output_and_decisions_are_deterministic(self) -> None:
        root = self.tmp("det")
        first, first_decisions = run_classifier(root / "a")
        second, second_decisions = run_classifier(root / "b")
        self.assertEqual(first, second)
        self.assertEqual(first_decisions.read_bytes(), second_decisions.read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
