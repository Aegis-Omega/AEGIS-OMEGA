from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "resolve-work-lineage.py"


def objective(text: str) -> str:
    normalized = " ".join(text.split()).strip().casefold()
    payload = json.dumps({"normalized_title": normalized}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(b"AEGIS_WORK_OBJECTIVE_V1\0" + payload).hexdigest()


def item(work_id: str, title: str, ref: str, head: str, *, classification: str = "ACTIVE_SPINE", state: str = "OPEN", capabilities=(), paths=(), artifacts=(), superseded_by=None):
    return {
        "work_id": work_id,
        "identity_source": "GITHUB_PR_NUMBER",
        "identity_stability": "STABLE",
        "pr_number": int(work_id.split(":")[1]),
        "title": title,
        "objective_digest": objective(title),
        "capability_set": list(capabilities),
        "path_evidence": list(paths),
        "artifact_refs": list(artifacts),
        "current_ref": ref,
        "current_head": head,
        "base_ref": "main",
        "base_sha": "a" * 40,
        "parent_work_ids": [],
        "lineage_root": "a" * 40,
        "state": state,
        "draft": False,
        "verification_state": "NOT_REEVALUATED_BY_RECONCILIATION",
        "admission_state": "NOT_CLASSIFIED_FOR_ADMISSION",
        "classification": classification,
        "declared_side_lineage": False,
        "superseded_by": superseded_by,
    }


def lineage(*, complete: bool = True, duplicate: bool = False) -> dict:
    items = [
        item("pr:10", "Proof trace SDK", "trace/proof-trace", "1" * 40, capabilities=("trace",), paths=("harness/sdk/proof_trace.py",), artifacts=("proof-trace",)),
        item("pr:20", "Company brain", "feat/company-brain", "2" * 40, capabilities=("company-brain", "planning"), paths=("harness/sdk/company_brain.py",), artifacts=("company-brain",)),
        item("pr:30", "Old connector broker", "old/connectors", "3" * 40, classification="UNKNOWN_FAIL_CLOSED", state="CLOSED", capabilities=("connectors",), paths=("mcp/connectors.py",), artifacts=("connector-broker",)),
    ]
    if duplicate:
        items.append(item("pr:40", "Company brain", "feat/company-brain-copy", "4" * 40, capabilities=("company-brain",), paths=("harness/sdk/company_brain.py",)))
    return {
        "schema_version": "AEGIS_WORK_LINEAGE_V1",
        "authority": "LINEAGE_DISCOVERY_EVIDENCE_ONLY",
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "source_universe_manifest_sha256": "f" * 64,
        "canonical_main": {"ref": "origin/main", "sha": "a" * 40, "authority": "ADMITTED_RUNTIME_ANCHOR"},
        "discovery_complete": complete,
        "active_spine": ["pr:10", "pr:20"],
        "historical_reconciled": {},
        "side_lineages": [],
        "missing_declared_work_ids": [],
        "work_items": items,
        "branch_creation_authority": "LINEAGE_RESOLVER_REQUIRED",
        "rules": [],
        "manifest_sha256": "e" * 64,
    }


def request(objective_text: str, **overrides) -> dict:
    base = {
        "schema_version": "AEGIS_WORK_REQUEST_V1",
        "objective_digest": objective(objective_text),
        "capability_set": [],
        "paths": [],
        "explicit_parent_work_ids": [],
        "referenced_artifacts": [],
        "branch_name_hint": None,
    }
    base.update(overrides)
    return base


def run_resolver(tmp: Path, line: dict, req: dict) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    lp = tmp / "lineage.json"
    rp = tmp / "request.json"
    op = tmp / "out.json"
    lp.write_text(json.dumps(line, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    rp.write_text(json.dumps(req, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(SCRIPT), "--lineage", str(lp), "--request", str(rp), "--out", str(op)], check=True)
    return json.loads(op.read_text(encoding="utf-8"))


class ResolveWorkLineageTests(unittest.TestCase):
    def tmp(self, label: str) -> Path:
        path = Path(tempfile.mkdtemp(prefix=f"aegis-resolve-{label}-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(path, ignore_errors=True))
        return path

    def test_exact_active_objective_continues_existing(self) -> None:
        out = run_resolver(self.tmp("continue"), lineage(), request("Company brain"))
        self.assertEqual(out["resolution"], "CONTINUE_EXISTING")
        self.assertEqual(out["work_id"], "pr:20")
        self.assertEqual(out["continuation_ref"], "feat/company-brain")
        self.assertEqual(out["expected_head"], "2" * 40)
        self.assertFalse(out["branch_creation_allowed"])

    def test_explicit_parent_stacks_on_existing(self) -> None:
        out = run_resolver(self.tmp("stack"), lineage(), request("Connector capability plane", explicit_parent_work_ids=["pr:20"]))
        self.assertEqual(out["resolution"], "STACK_ON_EXISTING")
        self.assertEqual(out["parent_work_ids"], ["pr:20"])
        self.assertFalse(out["branch_creation_allowed"])

    def test_compatible_closed_work_resumes_abandoned(self) -> None:
        out = run_resolver(self.tmp("resume"), lineage(), request("Different wording", capability_set=["connectors"], paths=["mcp/connectors.py"]))
        self.assertEqual(out["resolution"], "RESUME_ABANDONED")
        self.assertEqual(out["work_id"], "pr:30")
        self.assertFalse(out["branch_creation_allowed"])

    def test_no_compatible_work_allows_create_only_when_discovery_complete(self) -> None:
        out = run_resolver(self.tmp("new"), lineage(), request("Brand new isolated objective", capability_set=["new-cap"], paths=["new/path.py"]))
        self.assertEqual(out["resolution"], "CREATE_NEW")
        self.assertTrue(out["branch_creation_allowed"])
        self.assertIsNone(out["work_id"])

    def test_multiple_equally_compatible_active_lineages_halt(self) -> None:
        out = run_resolver(self.tmp("ambiguous"), lineage(duplicate=True), request("Company brain"))
        self.assertEqual(out["resolution"], "AMBIGUOUS_HALT")
        self.assertFalse(out["branch_creation_allowed"])
        self.assertEqual(out["candidate_work_ids"], ["pr:20", "pr:40"])

    def test_incomplete_discovery_can_never_authorize_create(self) -> None:
        out = run_resolver(self.tmp("incomplete"), lineage(complete=False), request("Brand new isolated objective"))
        self.assertEqual(out["resolution"], "AMBIGUOUS_HALT")
        self.assertFalse(out["branch_creation_allowed"])
        self.assertIn("DISCOVERY_INCOMPLETE", out["evidence_basis"])

    def test_branch_name_hint_alone_is_not_compatibility_evidence(self) -> None:
        out = run_resolver(self.tmp("name"), lineage(), request("Unrelated objective", branch_name_hint="feat/company-brain"))
        self.assertEqual(out["resolution"], "CREATE_NEW")
        self.assertTrue(out["branch_creation_allowed"])
        self.assertNotIn("BRANCH_NAME_MATCH", out["evidence_basis"])

    def test_compatible_work_denies_new_branch_even_if_hint_requests_new_name(self) -> None:
        out = run_resolver(self.tmp("deny"), lineage(), request("Company brain", branch_name_hint="feat/company-brain-v2"))
        self.assertEqual(out["resolution"], "CONTINUE_EXISTING")
        self.assertFalse(out["branch_creation_allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
