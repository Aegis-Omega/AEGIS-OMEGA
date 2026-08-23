#!/usr/bin/env python3
"""Fail-closed semantic/evidence lineage preflight for AEGIS.

PR #290 owns repository-wide artifact existence discovery. This script is the
next gate: after existence discovery, it blocks implementation when a proposed
name collides with known semantic/epistemic lineages or required context is
missing.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRECHECK = ROOT / "docs" / "LINEAGE_PRECHECK.json"
CONFLICTS = ROOT / "docs" / "LINEAGE_CONFLICTS.json"
REQUIRED = (
    ROOT / "sovereign-omega-v2" / "ARTIFACT_REGISTRY.md",
    ROOT / "docs" / "TRACEABILITY.md",
    ROOT / "docs" / "CORPUS_MINDMAP.md",
    ROOT / "docs" / "ONTOLOGY.md",
    ROOT / "scripts" / "integration_ledger.py",
    ROOT / "INTEGRATION_LEDGER.md",
    ROOT / "docs" / "LINEAGE_MANIFEST.v1.json",
    ROOT / "docs" / "LINEAGE_TIMELINE_PHASE1.v1.json",
    ROOT / "docs" / "DRIVE_TRIAGE.v1.json",
)

def load(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"LINEAGE_CONTEXT_MISSING:{path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))

def norm(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--proposed-name", required=True)
    p.add_argument("--semantic-role", required=True)
    p.add_argument("--artifact-scan-verdict", choices=("IMPLEMENTATION_EVIDENCE_FOUND","NAMED_REFERENCE_FOUND","INCOMPLETE","NO_MATCHES_IN_COMPLETE_REPO_SCAN"))
    p.add_argument("--acknowledge-conflict", action="store_true")
    args = p.parse_args()

    load(PRECHECK)
    conflict_doc = load(CONFLICTS)
    missing = [x for x in REQUIRED if not x.is_file()]
    if missing:
        for x in missing:
            print(f"LINEAGE_CONTEXT_MISSING:{x.relative_to(ROOT)}", file=sys.stderr)
        return 2

    if args.artifact_scan_verdict == "INCOMPLETE":
        print("ARTIFACT_DISCOVERY_INCOMPLETE", file=sys.stderr)
        return 4

    proposed = norm(args.proposed_name)
    collisions = []
    for item in conflict_doc.get("conflicts", []):
        symbol = norm(str(item.get("symbol","")))
        if symbol and (symbol in proposed or proposed in symbol):
            collisions.append(item)

    p0_collisions = [
        item for item in collisions
        if str(item.get("severity", "")).upper() == "P0"
    ]
    if p0_collisions:
        print("P0_LINEAGE_CONFLICT_UNRESOLVED", file=sys.stderr)
        for item in p0_collisions:
            print(f"- {item.get('id')}: {item.get('classification')}", file=sys.stderr)
        return 5

    if collisions and not args.acknowledge_conflict:
        print("LINEAGE_CONFLICT_REVIEW_REQUIRED", file=sys.stderr)
        for item in collisions:
            print(f"- {item.get('id')}: {item.get('classification')}", file=sys.stderr)
        return 3

    print(json.dumps({
        "status":"PRECHECK_PASSED",
        "proposed_name":args.proposed_name,
        "semantic_role":args.semantic_role,
        "artifact_scan_verdict":args.artifact_scan_verdict or "NOT_SUPPLIED",
        "known_conflicts":len(collisions),
        "p0_conflicts":0,
        "conflicts_acknowledged":bool(args.acknowledge_conflict),
        "next_required_evidence":[
            "exact current implementation/ref",
            "active PR lineage",
            "Drive/corpus predecessor evidence",
            "explicit lineage edge: NEW_ROOT|REFINES|SUPERSEDES|FORKS|RENAMES|UNRELATED",
            "exact-head admission evidence"
        ]
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
