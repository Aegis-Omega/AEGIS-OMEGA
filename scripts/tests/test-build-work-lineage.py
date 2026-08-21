from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-work-lineage.py"
SPINES = ROOT / ".aegis" / "reconciliation" / "spines.v1.json"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def fixture_universe() -> dict[str, object]:
    prs = []

    def add(number: int, title: str, base_ref: str, base_sha: str, head_ref: str, head_sha: str, state: str = "OPEN") -> None:
        prs.append({
            "number": number,
            "state": state,
            "draft": False,
            "title": title,
            "base_ref": base_ref,
            "base_sha": base_sha,
            "head_ref": head_ref,
            "head_sha": head_sha,
            "mergeable": "MERGEABLE",
            "url": f"https://example.invalid/pr/{number}",
        })

    main = "a" * 40
    heads = {n: f"{n:040x}"[-40:] for n in [268, 270, 272, 273, 275, 276, 277, 278, 279, 280, 282, 283, 284, 285, 286, 289, 290, 291, 292, 999]}
    add(275, "UCI integration spine", "main", main, "feat/uci-1", heads[275])
    add(276, "effect chain integration", "feat/uci-1", heads[275], "feat/uci-4", heads[276])
    add(277, "atomic admission", "feat/uci-4", heads[276], "feat/uci-5", heads[277])
    add(278, "collective memory", "feat/uci-5", heads[277], "feat/uci-6", heads[278])
    add(279, "AGI evidence protocol", "feat/uci-6", heads[278], "feat/uci-7", heads[279])
    add(280, "evaluation campaign", "feat/uci-7", heads[279], "feat/uci-8", heads[280])
    add(282, "daybreak hardening", "feat/uci-8", heads[280], "security/daybreak", heads[282])
    add(283, "boundary falsifiers", "security/daybreak", heads[282], "research/boundary", heads[283])
    add(284, "Proof Trace SDK", "research/boundary", heads[283], "trace/proof-trace", heads[284])
    add(285, "metacognitive executive", "trace/proof-trace", heads[284], "feat/metacog", heads[285])
    add(290, "artifact discovery", "feat/metacog", heads[285], "fix/discovery", heads[290])
    add(291, "company brain", "fix/discovery", heads[290], "feat/company-brain", heads[291])

    add(268, "receipt separation", "main", main, "pr1", heads[268])
    add(270, "effect observation", "pr1", heads[268], "pr2", heads[270])
    add(272, "verify effect", "pr2", heads[270], "pr3", heads[272])
    add(273, "complete verification", "pr3", heads[272], "pr4", heads[273])

    add(286, "formal CCT", "trace/proof-trace", heads[284], "proof/kg3", heads[286])
    add(289, "trace refinement", "proof/kg3", heads[286], "proof/kg4", heads[289])
    add(292, "proof producing checker", "proof/kg4", heads[289], "proof/kg5", heads[292])

    add(999, "unknown isolated experiment", "main", main, "experiment/unknown", heads[999])

    branches = [
        {"branch": pr["head_ref"], "ref": f"refs/remotes/origin/{pr['head_ref']}", "tip": pr["head_sha"], "ahead_of_main": 1, "behind_main": 0, "contained_in_main": False, "pr_numbers": [pr["number"]}
        for pr in prs
    ]
    branches.append({"branch": "main", "ref": "refs/remotes/origin/main", "tip": main, "ahead_of_main": 0, "behind_main": 0, "contained_in_main": True, "pr_numbers": []})

    return {
        "schema_version": "AEGIS_RECONCILIATION_UNIVERSE_V1",
        "authority": "DISCOVERY_EVIDENCE_ONLY",
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "canonical_main": {"ref": "origin/main", "sha": main, "authority": "ADMITTED_RUNTIME_ANCHOR"},
        "knowledge_universe": {"history_complete": True, "branch_count": len(branches), "all_ref_commit_count": 50, "main_reachable_commit_count": 5, "commits_not_reachable_from_main": 45},
        "pull_request_census_complete": True,
        "discovery_complete": True,
        "incomplete_sources": [],
        "deletion_authority": "CLASSIFICATION_REQUIRED",
        "global_absence_claim_authority": "SCOPED_ONLY",
        "branches": branches,
        "pull_requests": prs,
        "epistemic_rules": [],
        "manifest_sha256": "f" * 64,
    }


def run_builder(tmp: Path) -> dict[str, object]:
    universe = tmp / "universe.json"
    out = tmp / "lineage.json"
    write_json(universe, fixture_universe())
    subprocess.run([
        sys.executable,
        str(SCRIPT),
        "--universe", str(universe),
        "--spines", str(SPINES),
        "--out", str(out),
    ], check=True)
    return json.loads(out.read_text(encoding="utf-8"))


class WorkLineageTests(unittest.TestCase):
    def tmp(self, label: str) -> Path:
        path = Path(tempfile.mkdtemp(prefix=f"aegis-lineage-{label}-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(path, ignore_errors=True))
        return path

    def test_pr_work_id_is_stable_and_not_branch_name(self) -> None:
        doc = run_builder(self.tmp("id"))
        by_pr = {item["pr_number"]: item for item in doc["work_items"] if item["pr_number"] is not None}
        self.assertEqual(by_pr[275]["work_id"], "pr:275")
        self.assertNotEqual(by_pr[275]["work_id"], by_pr[275]["current_ref"])

    def test_pr_base_head_relationship_becomes_parent_edge(self) -> None:
        doc = run_builder(self.tmp("edge"))
        by_pr = {item["pr_number"]: item for item in doc["work_items"] if item["pr_number"] is not None}
        self.assertEqual(by_pr[276]["parent_work_ids"], ["pr:275"])
        self.assertEqual(by_pr[291]["parent_work_ids"], ["pr:290"])
        self.assertEqual(by_pr[292]["parent_work_ids"], ["pr:289"])

    def test_operator_approved_spine_is_explicit_and_ordered(self) -> None:
        doc = run_builder(self.tmp("spine"))
        self.assertEqual(doc["active_spine"], ["pr:275", "pr:276", "pr:277", "pr:278", "pr:279", "pr:280", "pr:282", "pr:283", "pr:284", "pr:285", "pr:290", "pr:291"])
        by_id = {item["work_id"]: item for item in doc["work_items"]}
        for work_id in doc["active_spine"]:
            self.assertEqual(by_id[work_id]["classification"], "ACTIVE_SPINE")

    def test_historical_effect_proofline_is_preserved_but_not_competing_spine(self) -> None:
        doc = run_builder(self.tmp("history"))
        by_id = {item["work_id"]: item for item in doc["work_items"]}
        for work_id in ["pr:268", "pr:270", "pr:272", "pr:273"]:
            self.assertEqual(by_id[work_id]["classification"], "HISTORICAL_EVIDENCE_ONLY")
            self.assertEqual(by_id[work_id]["superseded_by"], "pr:276")
            self.assertNotIn(work_id, doc["active_spine"])

    def test_unknown_work_defaults_fail_closed(self) -> None:
        doc = run_builder(self.tmp("unknown"))
        by_id = {item["work_id"]: item for item in doc["work_items"]}
        self.assertEqual(by_id["pr:999"]["classification"], "UNKNOWN_FAIL_CLOSED")
        self.assertEqual(by_id["pr:999"]["admission_state"], "NOT_CLASSIFIED_FOR_ADMISSION")

    def test_output_is_deterministic(self) -> None:
        root = self.tmp("det")
        first = run_builder(root / "a")
        second = run_builder(root / "b")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
