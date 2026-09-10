#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RECEIPT_KIND = "AEGIS_EXACT_HEAD_RECEIPT_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def evaluate(root: Path, candidate_sha: str) -> dict[str, Any]:
    root = Path(root).resolve()
    violations: list[str] = []
    actual_head: str | None = None
    dirty = None

    if SHA_RE.fullmatch(candidate_sha) is None:
        violations.append("CANDIDATE_SHA_INVALID")
    try:
        actual_head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=normal"],
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        violations.append("GIT_STATE_UNAVAILABLE")

    if actual_head is not None and SHA_RE.fullmatch(candidate_sha) is not None and actual_head != candidate_sha:
        violations.append("CANDIDATE_SHA_MISMATCH")
    if dirty:
        violations.append("WORKTREE_NOT_EXACT_HEAD")

    body: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "outcome": "ADMITTED" if not violations else "DENIED",
        "candidate_sha": candidate_sha,
        "actual_head": actual_head,
        "violation_count": len(set(violations)),
        "violations": sorted(set(violations)),
        "authority_effect": "NONE",
    }
    body["receipt_hash"] = hashlib.sha256(canonical_bytes({"domain": RECEIPT_KIND, "receipt": body})).hexdigest()
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    receipt = evaluate(Path(args.root), args.candidate_sha)
    if args.output:
        Path(args.output).write_bytes(canonical_bytes(receipt))
    print(f"{receipt['outcome']} {receipt['receipt_hash']}")
    for violation in receipt["violations"]:
        print(f"DENIAL: {violation}")
    return 0 if receipt["outcome"] == "ADMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
