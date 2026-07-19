#!/usr/bin/env python3
"""Static startup validator for the pinned AEGIS OSV reusable workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

RECEIPT_KIND = "AEGIS_OSV_WORKFLOW_STARTUP_RECEIPT_V1"
EXPECTED_REFS = {
    "scan-scheduled": "google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@v2.3.8",
    "scan-pr": "google/osv-scanner-action/.github/workflows/osv-scanner-reusable-pr.yml@v2.3.8",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def validate(path: Path) -> dict[str, Any]:
    violations: list[str] = []
    try:
        parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        if not isinstance(parsed, dict):
            raise ValueError("workflow root is not a mapping")
        if parsed.get("name") != "OSV-Scanner":
            violations.append("workflow name must be OSV-Scanner")
        triggers = parsed.get("on")
        if not isinstance(triggers, dict):
            violations.append("on must be a mapping")
        else:
            for event in ("pull_request", "merge_group", "push", "schedule"):
                if event not in triggers:
                    violations.append(f"missing trigger: {event}")
        permissions = parsed.get("permissions")
        if not isinstance(permissions, dict):
            violations.append("top-level permissions missing")
        else:
            required_permissions = {
                "actions": "read",
                "security-events": "write",
                "contents": "read",
            }
            for name, expected in required_permissions.items():
                if permissions.get(name) != expected:
                    violations.append(f"permission {name} must be {expected}")
        jobs = parsed.get("jobs")
        if not isinstance(jobs, dict):
            violations.append("jobs must be a mapping")
            jobs = {}
        for job_name, expected_ref in EXPECTED_REFS.items():
            job = jobs.get(job_name)
            if not isinstance(job, dict):
                violations.append(f"missing job: {job_name}")
                continue
            actual_ref = job.get("uses")
            if actual_ref != expected_ref:
                violations.append(
                    f"{job_name} reusable workflow ref mismatch: expected {expected_ref}, got {actual_ref}"
                )
            if not isinstance(actual_ref, str) or not re.search(r"@v\d+\.\d+\.\d+$", actual_ref):
                violations.append(f"{job_name} reusable workflow must use an exact semantic version")
            scan_args = job.get("with", {}).get("scan-args") if isinstance(job.get("with"), dict) else None
            if not isinstance(scan_args, str) or "-r" not in scan_args or "--skip-git" not in scan_args:
                violations.append(f"{job_name} scan-args must include -r and --skip-git")
    except Exception as exc:
        violations.append(f"workflow parse failure: {type(exc).__name__}: {exc}")

    body: dict[str, Any] = {
        "schema_version": "1.0.0",
        "receipt_kind": RECEIPT_KIND,
        "outcome": "ADMITTED" if not violations else "DENIED",
        "workflow_path": path.as_posix(),
        "workflow_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        "pinned_refs": EXPECTED_REFS,
        "violation_count": len(set(violations)),
        "violations": sorted(set(violations)),
    }
    body["receipt_hash"] = hashlib.sha256(
        canonical_bytes({"domain": RECEIPT_KIND, "receipt": body})
    ).hexdigest()
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", default=".github/workflows/osv-scanner.yml")
    parser.add_argument("--output", default="OSV_STARTUP_RECEIPT.json")
    args = parser.parse_args()

    receipt = validate(Path(args.workflow))
    Path(args.output).write_bytes(canonical_bytes(receipt))
    print(f"{receipt['outcome']} {receipt['receipt_hash']}")
    for violation in receipt["violations"]:
        print(f"DENIAL: {violation}", file=sys.stderr)
    return 0 if receipt["outcome"] == "ADMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
