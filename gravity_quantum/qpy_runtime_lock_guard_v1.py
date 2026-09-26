#!/usr/bin/env python3
"""Fail-closed verifier for the proof-carrying QPY Python runtime lock.

This verifier does not resolve dependencies.  It proves that a committed input
lock is fully pinned and hash-bound before the workflow is allowed to install it.
A post-run `pip freeze` remains observational evidence only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "AEGIS_QPY_RUNTIME_LOCK_GUARD_V1"
HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})(?:\s|$)")
REQ = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)(?:\s|\\|$)")

EXPECTED_TOP_LEVEL = {
    "cudaq": "0.15.1",
    "pennylane": "0.45.1",
    "qiskit": "2.5.2",
}


class LockError(ValueError):
    pass


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def logical_entries(text: str) -> list[str]:
    entries: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-e ", "--editable", "git+", "http://", "https://")):
            raise LockError("UNSUPPORTED_NON_INDEX_REQUIREMENT")
        buf = f"{buf} {line}".strip() if buf else line
        if line.endswith("\\"):
            buf = buf[:-1].rstrip()
            continue
        entries.append(buf)
        buf = ""
    if buf:
        raise LockError("UNTERMINATED_REQUIREMENT_CONTINUATION")
    return entries


def verify_lock(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise LockError("LOCKFILE_MISSING")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    entries = logical_entries(text)
    if not entries:
        raise LockError("LOCKFILE_EMPTY")

    resolved: dict[str, str] = {}
    hashes_by_name: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        match = REQ.match(entry)
        if match is None:
            raise LockError(f"REQUIREMENT_NOT_EXACTLY_PINNED:{entry}")
        name = normalize_name(match.group(1))
        version = match.group(2)
        hashes = tuple(sorted(set(HASH.findall(entry))))
        if not hashes:
            raise LockError(f"REQUIREMENT_HASH_MISSING:{name}")
        if name in resolved:
            raise LockError(f"DUPLICATE_REQUIREMENT:{name}")
        resolved[name] = version
        hashes_by_name[name] = hashes

    missing = {
        name: version for name, version in EXPECTED_TOP_LEVEL.items()
        if resolved.get(name) != version
    }
    if missing:
        raise LockError("TOP_LEVEL_VERSION_MISMATCH:" + json.dumps(missing, sort_keys=True))

    report: dict[str, object] = {
        "schema": SCHEMA,
        "lock_path": str(path),
        "lock_sha256": hashlib.sha256(raw).hexdigest(),
        "requirement_count": len(entries),
        "all_requirements_exactly_pinned": True,
        "all_requirements_hash_bound": True,
        "expected_top_level": EXPECTED_TOP_LEVEL,
        "authority_effect": "NONE",
    }
    receipt_payload = {
        key: value for key, value in report.items() if key != "lock_path"
    }
    report["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    try:
        report = verify_lock(Path(args.lock))
    except (OSError, UnicodeError, LockError) as exc:
        report = {
            "schema": SCHEMA,
            "lock_path": args.lock,
            "verification_status": "FAIL_CLOSED",
            "error": str(exc),
            "authority_effect": "NONE",
        }
        rc = 1
    else:
        report["verification_status"] = "VERIFIED"
        rc = 0
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    print(rendered, end="")
    if args.json_output:
        Path(args.json_output).write_text(rendered, encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())