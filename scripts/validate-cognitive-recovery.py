#!/usr/bin/env python3
"""Fail-closed verifier for bounded recovery from a denied cognitive base.

This verifier does not replace or weaken Automaton-2. It proves only that a
recovery candidate is bound to an explicitly identified denied base, the last
independently valid predecessor, and exact recovery artifacts. A successful
receipt is RECOVERY_VERIFIED with production_admission=NONE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

RECEIPT_KIND = "AEGIS_COGNITIVE_RECOVERY_RECEIPT_V1"
SCHEMA_VERSION = "1.0.0"
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GOVERNED_ANCHORS = frozenset({".claude.json", "skill-hashes.sha256"})


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def git_text(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


def load_json_at(repo: Path, ref: str, path: str) -> dict[str, Any]:
    raw = git_text(repo, "show", f"{ref}:{path}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} at {ref} is not a JSON object")
    return value


def first_parent(repo: Path, commit: str) -> str:
    line = git_text(repo, "rev-list", "--parents", "-n", "1", commit)
    parts = line.split()
    if len(parts) < 2:
        raise ValueError(f"denied base has no parent: {commit}")
    return parts[1]


def changed_paths(repo: Path, base: str, head: str) -> set[str]:
    output = git_text(repo, "diff", "--name-only", base, head)
    return {line for line in output.splitlines() if line}


def blob_sha(repo: Path, commit: str, path: str) -> str:
    return git_text(repo, "rev-parse", f"{commit}:{path}")


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = git(repo, "merge-base", "--is-ancestor", ancestor, descendant, check=False)
    return result.returncode == 0


def valid_sha1(value: str) -> bool:
    return bool(SHA1_RE.fullmatch(value))


def valid_sha256(value: str) -> bool:
    return bool(SHA256_RE.fullmatch(value))


def build_receipt(
    *,
    outcome: str,
    candidate_sha: str,
    denied_base_sha: str,
    recovery_parent_sha: str,
    expected_parent_state_hash: str,
    expected_recovery_state_hash: str,
    expected_manifest_blob: str,
    expected_skill_hashes_blob: str,
    denied_receipt_hash: str,
    recovery_validation_receipt_hash: str,
    violations: list[str],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "outcome": outcome,
        "production_admission": "NONE",
        "authority": "NONE",
        "candidate_sha": candidate_sha,
        "denied_base_sha": denied_base_sha,
        "recovery_parent_sha": recovery_parent_sha,
        "expected_parent_state_hash": expected_parent_state_hash,
        "expected_recovery_state_hash": expected_recovery_state_hash,
        "expected_manifest_blob": expected_manifest_blob,
        "expected_skill_hashes_blob": expected_skill_hashes_blob,
        "denied_receipt_hash": denied_receipt_hash,
        "recovery_validation_receipt_hash": recovery_validation_receipt_hash,
        "violation_count": len(violations),
        "violations": violations,
    }
    body["receipt_hash"] = sha256_hex(
        canonical_bytes({"domain": RECEIPT_KIND, "receipt": body})
    )
    return body


def evaluate(
    *,
    repo: Path,
    candidate_sha: str,
    denied_base_sha: str,
    recovery_parent_sha: str,
    expected_parent_state_hash: str,
    expected_manifest_blob: str,
    expected_skill_hashes_blob: str,
    expected_recovery_state_hash: str,
    denied_receipt_hash: str,
    recovery_validation_receipt_hash: str,
    allowed_candidate_paths: Iterable[str] | None = None,
    expected_source_ref: str = "main",
) -> dict[str, Any]:
    repo = Path(repo).resolve()
    violations: list[str] = []

    for label, value in (
        ("candidate_sha", candidate_sha),
        ("denied_base_sha", denied_base_sha),
        ("recovery_parent_sha", recovery_parent_sha),
        ("expected_manifest_blob", expected_manifest_blob),
        ("expected_skill_hashes_blob", expected_skill_hashes_blob),
    ):
        if not valid_sha1(value):
            violations.append(f"invalid SHA-1 {label}: {value}")

    for label, value in (
        ("expected_parent_state_hash", expected_parent_state_hash),
        ("expected_recovery_state_hash", expected_recovery_state_hash),
        ("denied_receipt_hash", denied_receipt_hash),
        ("recovery_validation_receipt_hash", recovery_validation_receipt_hash),
    ):
        if not valid_sha256(value):
            violations.append(f"invalid SHA-256 {label}: {value}")

    if violations:
        violations = sorted(set(violations))
        return build_receipt(
            outcome="DENIED",
            candidate_sha=candidate_sha,
            denied_base_sha=denied_base_sha,
            recovery_parent_sha=recovery_parent_sha,
            expected_parent_state_hash=expected_parent_state_hash,
            expected_recovery_state_hash=expected_recovery_state_hash,
            expected_manifest_blob=expected_manifest_blob,
            expected_skill_hashes_blob=expected_skill_hashes_blob,
            denied_receipt_hash=denied_receipt_hash,
            recovery_validation_receipt_hash=recovery_validation_receipt_hash,
            violations=violations,
        )

    try:
        observed_parent = first_parent(repo, denied_base_sha)
        if observed_parent != recovery_parent_sha:
            violations.append(
                "denied base is not a direct child of recovery parent: "
                f"expected {recovery_parent_sha}, got {observed_parent}"
            )

        denied_paths = changed_paths(repo, recovery_parent_sha, denied_base_sha)
        if denied_paths != set(GOVERNED_ANCHORS):
            violations.append(
                "denied-base changed paths are not exactly governed anchors: "
                + ",".join(sorted(denied_paths))
            )

        if not is_ancestor(repo, denied_base_sha, candidate_sha):
            violations.append("recovery candidate does not preserve denied-base ancestry")

        if allowed_candidate_paths is not None:
            allowed = set(allowed_candidate_paths)
            candidate_paths = changed_paths(repo, denied_base_sha, candidate_sha)
            unexpected = sorted(candidate_paths - allowed)
            if unexpected:
                violations.append(
                    "recovery candidate changed non-allowlisted paths: " + ",".join(unexpected)
                )

        parent_manifest = load_json_at(repo, recovery_parent_sha, ".claude.json")
        actual_parent_state = parent_manifest.get("state_hash")
        if actual_parent_state != expected_parent_state_hash:
            violations.append(
                "recovery parent state_hash mismatch: "
                f"expected {expected_parent_state_hash}, got {actual_parent_state}"
            )

        manifest = load_json_at(repo, candidate_sha, ".claude.json")
        provenance = manifest.get("provenance")
        if not isinstance(provenance, dict):
            violations.append("recovery manifest provenance is missing")
            provenance = {}

        actual_source_ref = provenance.get("source_ref")
        if actual_source_ref != expected_source_ref:
            violations.append(
                f"recovery source_ref mismatch: expected {expected_source_ref}, got {actual_source_ref}"
            )

        actual_parent = provenance.get("parent_state_hash")
        if actual_parent != expected_parent_state_hash:
            violations.append(
                "recovery parent_state_hash mismatch: "
                f"expected {expected_parent_state_hash}, got {actual_parent}"
            )

        actual_state = manifest.get("state_hash")
        if actual_state != expected_recovery_state_hash:
            violations.append(
                "recovery state_hash mismatch: "
                f"expected {expected_recovery_state_hash}, got {actual_state}"
            )

        actual_manifest_blob = blob_sha(repo, candidate_sha, ".claude.json")
        if actual_manifest_blob != expected_manifest_blob:
            violations.append(
                "manifest blob mismatch: "
                f"expected {expected_manifest_blob}, got {actual_manifest_blob}"
            )

        actual_hashes_blob = blob_sha(repo, candidate_sha, "skill-hashes.sha256")
        if actual_hashes_blob != expected_skill_hashes_blob:
            violations.append(
                "skill-hashes blob mismatch: "
                f"expected {expected_skill_hashes_blob}, got {actual_hashes_blob}"
            )
    except Exception as exc:
        violations.append(f"recovery verifier exception: {type(exc).__name__}: {exc}")

    violations = sorted(set(violations))
    return build_receipt(
        outcome="RECOVERY_VERIFIED" if not violations else "DENIED",
        candidate_sha=candidate_sha,
        denied_base_sha=denied_base_sha,
        recovery_parent_sha=recovery_parent_sha,
        expected_parent_state_hash=expected_parent_state_hash,
        expected_recovery_state_hash=expected_recovery_state_hash,
        expected_manifest_blob=expected_manifest_blob,
        expected_skill_hashes_blob=expected_skill_hashes_blob,
        denied_receipt_hash=denied_receipt_hash,
        recovery_validation_receipt_hash=recovery_validation_receipt_hash,
        violations=violations,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--denied-base-sha", required=True)
    parser.add_argument("--recovery-parent-sha", required=True)
    parser.add_argument("--expected-parent-state-hash", required=True)
    parser.add_argument("--expected-manifest-blob", required=True)
    parser.add_argument("--expected-skill-hashes-blob", required=True)
    parser.add_argument("--expected-recovery-state-hash", required=True)
    parser.add_argument("--denied-receipt-hash", required=True)
    parser.add_argument("--recovery-validation-receipt-hash", required=True)
    parser.add_argument("--expected-source-ref", default="main")
    parser.add_argument("--allow-candidate-path", action="append", default=[])
    parser.add_argument("--output", default="COGNITIVE_RECOVERY_RECEIPT.json")
    args = parser.parse_args()

    receipt = evaluate(
        repo=Path(args.repo),
        candidate_sha=args.candidate_sha,
        denied_base_sha=args.denied_base_sha,
        recovery_parent_sha=args.recovery_parent_sha,
        expected_parent_state_hash=args.expected_parent_state_hash,
        expected_manifest_blob=args.expected_manifest_blob,
        expected_skill_hashes_blob=args.expected_skill_hashes_blob,
        expected_recovery_state_hash=args.expected_recovery_state_hash,
        denied_receipt_hash=args.denied_receipt_hash,
        recovery_validation_receipt_hash=args.recovery_validation_receipt_hash,
        allowed_candidate_paths=args.allow_candidate_path or None,
        expected_source_ref=args.expected_source_ref,
    )
    Path(args.output).write_bytes(canonical_bytes(receipt))
    print(f"{receipt['outcome']} {receipt['receipt_hash']}")
    for violation in receipt["violations"]:
        print(f"DENIAL: {violation}", file=sys.stderr)
    return 0 if receipt["outcome"] == "RECOVERY_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
