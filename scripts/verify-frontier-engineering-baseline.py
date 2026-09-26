#!/usr/bin/env python3
"""Evidence-bounded engineering baseline verifier.

This verifier checks repository controls that can be established from source
alone. It deliberately does not claim settings that require GitHub admin/API
state unless a separate repository-enforcement verifier provides that evidence.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    "SECURITY.md",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/workflows/osv-scanner.yml",
    ".github/workflows/automaton-2.yml",
    "scripts/check_repository_enforcement.py",
    "docs/rfcs/0001-operator-sovereign-control-plane.md",
)

CRITICAL_WORKFLOWS = (
    ".github/workflows/automaton-2.yml",
    ".github/workflows/automaton-3.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/osv-scanner.yml",
)

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def action_refs(path: Path) -> list[dict[str, str | bool]]:
    rows: list[dict[str, str | bool]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("uses:"):
            continue
        value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        if "@" not in value:
            rows.append({"ref": value, "pinned_full_sha": False})
            continue
        ref = value.rsplit("@", 1)[1]
        rows.append({"ref": value, "pinned_full_sha": bool(FULL_SHA.fullmatch(ref))})
    return rows


def main() -> int:
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]

    automaton = (ROOT / ".github/workflows/automaton-2.yml").read_text(encoding="utf-8")
    provenance_controls = {
        "oidc": "id-token: write" in automaton,
        "attestations": "attestations: write" in automaton and "actions/attest@" in automaton,
        "artifact_metadata": "artifact-metadata: write" in automaton,
        "exact_candidate_binding": "CANDIDATE_SHA" in automaton,
    }

    mutable_refs: list[dict[str, str]] = []
    for rel in CRITICAL_WORKFLOWS:
        for row in action_refs(ROOT / rel):
            if not row["pinned_full_sha"]:
                mutable_refs.append({"workflow": rel, "ref": str(row["ref"])})

    report = {
        "schema": "aegis.frontier-engineering-baseline.v1",
        "authority_effect": "NONE",
        "required_source_controls_present": not missing,
        "missing_source_controls": missing,
        "provenance_controls": provenance_controls,
        "critical_workflow_mutable_action_refs": mutable_refs,
        "workflow_pin_status": "PASS" if not mutable_refs else "PARTIAL",
        "overall": "PASS_WITH_REMEDIATION" if not missing and all(provenance_controls.values()) else "FAIL",
        "limitations": [
            "Source inspection cannot prove live GitHub ruleset state.",
            "Source inspection cannot prove secret-scanning or push-protection settings.",
            "PASS_WITH_REMEDIATION is not a release or authority promotion.",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall"] == "PASS_WITH_REMEDIATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
