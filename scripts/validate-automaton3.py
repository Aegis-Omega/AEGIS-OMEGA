#!/usr/bin/env python3
"""Validate an exact Automaton-3 candidate and emit deterministic evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")

KEY_FILES = (
    "harness/sdk/sovereign_execution.py",
    "harness/sdk/authority_client.py",
    "harness/policies/consequence-policy.v1.json",
    "harness/policies/capability-map.v1.json",
    "scripts/automaton3-authority.py",
    "scripts/run-automaton3-tests.py",
    "scripts/validate-automaton3.py",
    "agents/coordinator.py",
    "sovereign-omega-v2/mcp-server/src/index.ts",
    "sovereign-omega-v2/mcp-server/test/automaton3-authority.mjs",
    "sovereign-omega-v2/python/tests/test_automaton3.py",
    "schemas/execution-identity-envelope.v1.schema.json",
    "schemas/mutation-receipt.v1.schema.json",
    "schemas/event-envelope.v1.schema.json",
    "schemas/writer-lease.v1.schema.json",
    "docs/adr/ADR-0021-automaton-3-sovereign-execution.md",
    "docs/security/AUTOMATON3_THREAT_MODEL.md",
    "docs/operations/LAW_OF_SILENCE_V2.md",
    "docs/operations/BRANCH_RULESET_AUTOMATON3.md",
    ".github/workflows/automaton-3.yml",
)

REQUIRED_REPOSITORY_CONTROLS = (
    ".github/workflows/automaton-2.yml",
    ".github/workflows/experiment-admission.yml",
    ".github/workflows/osv-scanner.yml",
    ".github/workflows/integration-ledger.yml",
    ".github/workflows/ci.yml",
    "scripts/validate-claims.mjs",
    "scripts/integration_ledger.py",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data), "size_bytes": len(data)}


def evaluate(*, candidate_sha: str, expected_parent_sha: str, test_summary_path: Path, mcp_log_path: Path, require_oidc: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    violations: list[str] = []
    if not SHA_RE.fullmatch(candidate_sha): violations.append("candidate_sha invalid")
    if not SHA_RE.fullmatch(expected_parent_sha): violations.append("expected_parent_sha invalid")

    files: list[dict[str, Any]] = []
    for rel in KEY_FILES:
        path = ROOT / rel
        if not path.is_file(): violations.append(f"required file missing: {rel}")
        else: files.append(file_record(path))
    for rel in REQUIRED_REPOSITORY_CONTROLS:
        if not (ROOT / rel).is_file(): violations.append(f"repository control missing: {rel}")

    try:
        policy_raw = json.loads((ROOT / "harness/policies/consequence-policy.v1.json").read_text(encoding="utf-8"))
        classes = policy_raw["classes"]
        if sorted(classes) != ["D0", "D1", "D2", "D3", "D4"]: violations.append("consequence classes incomplete")
        for level in ("D2", "D3", "D4"):
            if classes[level].get("approval") != "EXPLICIT": violations.append(f"{level} does not require explicit approval")
        policy_root = sha256(canonical_bytes({"domain": "AEGIS_CONSEQUENCE_POLICY_V1", "value": classes}))
    except Exception as exc:
        violations.append(f"policy invalid: {type(exc).__name__}")
        policy_root = "0" * 64

    try:
        summary = json.loads(test_summary_path.read_text(encoding="utf-8"))
        if summary.get("return_code") != 0: violations.append("Automaton-3 tests failed")
        if summary.get("bypasses") != 0: violations.append("authority bypass detected")
        if summary.get("adaptive_attempts") != [1, 10, 100]: violations.append("adaptive attempt matrix incomplete")
        test_summary_root = summary.get("summary_root", "0" * 64)
    except Exception as exc:
        violations.append(f"test summary unavailable: {type(exc).__name__}")
        test_summary_root = "0" * 64

    try:
        mcp_log = mcp_log_path.read_text(encoding="utf-8")
        if "AUTOMATON3_MCP_PASS" not in mcp_log: violations.append("MCP fail-closed integration not proven")
        mcp_log_root = sha256(mcp_log.encode("utf-8"))
    except Exception as exc:
        violations.append(f"MCP log unavailable: {type(exc).__name__}")
        mcp_log_root = "0" * 64

    integration_expectations = {
        "agents/coordinator.py": "authorize_from_environment",
        "sovereign-omega-v2/mcp-server/src/index.ts": "automaton3-authority.py",
        ".github/workflows/automaton-3.yml": "aegis / automaton-3",
    }
    for rel, needle in integration_expectations.items():
        path = ROOT / rel
        if path.is_file() and needle not in path.read_text(encoding="utf-8"):
            violations.append(f"integration missing: {rel}:{needle}")

    prohibited = re.compile(r"fail[- ]open|temporary bypass|silent fallback", re.IGNORECASE)
    for rel in ("harness/sdk/sovereign_execution.py", "harness/sdk/authority_client.py", "agents/coordinator.py", "sovereign-omega-v2/mcp-server/src/index.ts"):
        path = ROOT / rel
        if path.is_file() and prohibited.search(path.read_text(encoding="utf-8")):
            violations.append(f"prohibited bypass language in executable path: {rel}")

    if require_oidc and not (os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL") and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")):
        violations.append("OIDC execution identity unavailable")

    files.sort(key=lambda item: item["path"])
    candidate_manifest = {
        "schema_version": "1.0.0",
        "manifest_kind": "AEGIS_AUTOMATON3_CANDIDATE_MANIFEST_V1",
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "candidate_sha": candidate_sha,
        "expected_parent_sha": expected_parent_sha,
        "policy_root": policy_root,
        "test_summary_root": test_summary_root,
        "mcp_log_root": mcp_log_root,
        "files": files,
    }
    candidate_manifest["candidate_manifest_root"] = sha256(canonical_bytes(candidate_manifest))

    violations = sorted(set(violations))
    body = {
        "schema_version": "1.0.0",
        "receipt_kind": "AEGIS_AUTOMATON3_ADMISSION_RECEIPT_V1",
        "candidate_sha": candidate_sha,
        "expected_parent_sha": expected_parent_sha,
        "candidate_manifest_root": candidate_manifest["candidate_manifest_root"],
        "policy_root": policy_root,
        "test_summary_root": test_summary_root,
        "mcp_log_root": mcp_log_root,
        "signature_mode": "GITHUB_OIDC_ATTESTATION",
        "outcome": "ADMITTED" if not violations else "DENIED",
        "violation_count": len(violations),
        "violations": violations,
    }
    receipt = dict(body)
    receipt["receipt_hash"] = sha256(canonical_bytes({"domain": "AEGIS_AUTOMATON3_ADMISSION_RECEIPT_V1", "receipt": body}))
    return receipt, candidate_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--expected-parent-sha", required=True)
    parser.add_argument("--test-summary", required=True)
    parser.add_argument("--mcp-log", required=True)
    parser.add_argument("--receipt-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--require-oidc", action="store_true")
    args = parser.parse_args()
    receipt, manifest = evaluate(candidate_sha=args.candidate_sha, expected_parent_sha=args.expected_parent_sha, test_summary_path=Path(args.test_summary), mcp_log_path=Path(args.mcp_log), require_oidc=args.require_oidc)
    Path(args.receipt_output).write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    Path(args.manifest_output).write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["outcome"] == "ADMITTED" else 3

if __name__ == "__main__": raise SystemExit(main())
