#!/usr/bin/env python3
"""Fail-closed source verifier for the AEGIS frontier engineering baseline.

V2 security changes:
- parses both `uses:` and canonical YAML list form `- uses:`;
- treats mutable third-party action/workflow refs as a hard failure;
- separates source/provenance/action-pin verdicts;
- binds candidate SHA, verifier SHA-256, and policy version into the receipt;
- writes a receipt even when the verifier fails (when --json-output is supplied).

This verifier is source-only. It does not claim live GitHub settings, hosted
execution, secret-scanning, or production admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "aegis.frontier-engineering-baseline.v2"
POLICY_VERSION = "FRONTIER_ENGINEERING_BASELINE_POLICY_V2"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
USE_LINE = re.compile(
    r"""^\s*(?:-\s*)?uses:\s*["']?(?P<value>[^"'\s#]+)["']?\s*(?:#.*)?$"""
)

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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_sha(root: Path, explicit: str | None) -> str:
    value = explicit or os.environ.get("CANDIDATE_SHA")
    if not value:
        try:
            value = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            value = ""
    if FULL_SHA.fullmatch(value or "") is None:
        raise ValueError("CANDIDATE_SHA_MUST_BE_LOWERCASE_HEX40")
    return value


def action_refs(path: Path) -> list[dict[str, str | bool]]:
    """Return every `uses:` ref, including YAML list form `- uses:`."""
    rows: list[dict[str, str | bool]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        match = USE_LINE.match(line)
        if match is None:
            continue
        value = match.group("value")

        # Repository-local actions are content-bound by the candidate checkout.
        if value.startswith("./"):
            rows.append(
                {
                    "ref": value,
                    "pinned_full_sha": True,
                    "kind": "repository_local",
                    "line": str(line_number),
                }
            )
            continue

        # Docker references are a distinct supply-chain surface and must use a
        # digest if they appear in a critical workflow.
        if value.startswith("docker://"):
            pinned = "@sha256:" in value
            rows.append(
                {
                    "ref": value,
                    "pinned_full_sha": pinned,
                    "kind": "docker",
                    "line": str(line_number),
                }
            )
            continue

        if "@" not in value:
            pinned = False
        else:
            ref = value.rsplit("@", 1)[1]
            pinned = FULL_SHA.fullmatch(ref) is not None
        rows.append(
            {
                "ref": value,
                "pinned_full_sha": pinned,
                "kind": "github_action_or_reusable_workflow",
                "line": str(line_number),
            }
        )
    return rows


def evaluate(root: Path, *, candidate_sha: str, verifier_sha256: str) -> dict[str, object]:
    missing = [p for p in REQUIRED if not (root / p).exists()]

    automaton_path = root / ".github/workflows/automaton-2.yml"
    automaton = (
        automaton_path.read_text(encoding="utf-8")
        if automaton_path.exists()
        else ""
    )
    provenance_controls = {
        "oidc": "id-token: write" in automaton,
        "attestations": (
            "attestations: write" in automaton
            and "actions/attest@" in automaton
        ),
        "artifact_metadata": "artifact-metadata: write" in automaton,
        "exact_candidate_binding": "CANDIDATE_SHA" in automaton,
    }

    mutable_refs: list[dict[str, str]] = []
    all_refs: list[dict[str, str | bool]] = []
    for rel in CRITICAL_WORKFLOWS:
        for row in action_refs(root / rel):
            enriched = {"workflow": rel, **row}
            all_refs.append(enriched)
            if not bool(row["pinned_full_sha"]):
                mutable_refs.append(
                    {
                        "workflow": rel,
                        "ref": str(row["ref"]),
                        "line": str(row["line"]),
                    }
                )

    source_controls_complete = not missing
    provenance_controls_complete = all(provenance_controls.values())
    immutable_action_refs_complete = not mutable_refs
    overall_ok = all(
        (
            source_controls_complete,
            provenance_controls_complete,
            immutable_action_refs_complete,
        )
    )

    return {
        "schema": SCHEMA,
        "policy_version": POLICY_VERSION,
        "authority_effect": "NONE",
        "candidate_sha": candidate_sha,
        "verifier_sha256": verifier_sha256,
        "source_controls_complete": source_controls_complete,
        "provenance_controls_complete": provenance_controls_complete,
        "immutable_action_refs_complete": immutable_action_refs_complete,
        "required_source_controls_present": source_controls_complete,
        "missing_source_controls": missing,
        "provenance_controls": provenance_controls,
        "critical_workflow_action_refs": all_refs,
        "critical_workflow_mutable_action_refs": mutable_refs,
        "workflow_pin_status": "PASS" if immutable_action_refs_complete else "FAIL",
        "overall": "PASS" if overall_ok else "FAIL",
        "limitations": [
            "Source inspection cannot prove live GitHub ruleset state.",
            "Source inspection cannot prove secret-scanning or push-protection settings.",
            "Source PASS is not hosted execution, release, merge, deploy, or authority promotion.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--candidate-sha")
    parser.add_argument("--json-output")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        candidate_sha = _candidate_sha(root, args.candidate_sha)
        verifier_sha256 = sha256_file(Path(__file__).resolve())
        report = evaluate(
            root,
            candidate_sha=candidate_sha,
            verifier_sha256=verifier_sha256,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {
            "schema": SCHEMA,
            "policy_version": POLICY_VERSION,
            "authority_effect": "NONE",
            "overall": "FAIL",
            "error": str(exc),
        }

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_output:
        Path(args.json_output).write_text(rendered, encoding="utf-8")

    return 0 if report.get("overall") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())