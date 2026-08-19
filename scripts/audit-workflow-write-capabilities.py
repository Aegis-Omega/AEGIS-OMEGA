#!/usr/bin/env python3
"""Fail closed on undeclared or unreceipted GitHub Actions write capability."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ALLOWLIST = ROOT / ".github" / "write-capability-allowlist.yml"
PRIVILEGED = ("contents", "id-token")
REQUIRED_MARKERS = (
    "AEGIS_WRITER_LEASE",
    "AEGIS_FENCING_TOKEN",
    "AEGIS_WRITE_RECEIPT",
)


def permission_is_write(text: str, permission: str) -> bool:
    escaped = re.escape(permission)
    line_form = re.compile(rf"(?m)^\s*{escaped}\s*:\s*write\s*(?:#.*)?$")
    inline_form = re.compile(rf"[{{,]\s*{escaped}\s*:\s*write\s*[,}}]")
    return bool(line_form.search(text) or inline_form.search(text))


def load_allowlist() -> dict[str, object]:
    try:
        data = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"WRITE_CAPABILITY_ALLOWLIST_INVALID: {exc}") from exc
    if data.get("schema_version") != "1.0.0" or not isinstance(data.get("workflows"), dict):
        raise SystemExit("WRITE_CAPABILITY_ALLOWLIST_SCHEMA_INVALID")
    return data


def main() -> int:
    allowlist = load_allowlist()
    entries = allowlist["workflows"]
    assert isinstance(entries, dict)
    errors: list[str] = []
    observed_privileged: set[str] = set()

    for path in sorted((*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml"))):
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        permissions = {name for name in PRIVILEGED if permission_is_write(text, name)}
        pushes = bool(re.search(r"(?m)\bgit\s+push\b", text))

        if not permissions and not pushes:
            continue

        observed_privileged.add(relative)
        entry = entries.get(relative)
        if not isinstance(entry, dict):
            errors.append(f"UNALLOWLISTED_WRITE_CAPABILITY:{relative}")
            continue

        allowed_permissions = entry.get("allowed_permissions")
        if not isinstance(allowed_permissions, list) or any(item not in PRIVILEGED for item in allowed_permissions):
            errors.append(f"ALLOWLIST_PERMISSION_SCHEMA_INVALID:{relative}")
            continue
        unexpected = sorted(permissions - set(allowed_permissions))
        if unexpected:
            errors.append(f"UNAPPROVED_WRITE_PERMISSION:{relative}:{','.join(unexpected)}")

        may_push = entry.get("may_git_push") is True
        if pushes and not may_push:
            errors.append(f"UNAPPROVED_GIT_PUSH:{relative}")
        if may_push and not pushes:
            errors.append(f"STALE_GIT_PUSH_ALLOWLIST:{relative}")

        if pushes:
            if entry.get("lease_fencing_required") is not True:
                errors.append(f"PUSH_WITHOUT_LEASE_POLICY:{relative}")
            missing = [marker for marker in REQUIRED_MARKERS if marker not in text]
            if missing:
                errors.append(f"UNRECEIPTED_BRANCH_WRITER:{relative}:missing={','.join(missing)}")
            if not isinstance(entry.get("authority_domain"), str) or not entry.get("authority_domain"):
                errors.append(f"WRITER_AUTHORITY_DOMAIN_MISSING:{relative}")

    stale = sorted(set(entries) - observed_privileged)
    for relative in stale:
        errors.append(f"STALE_WRITE_CAPABILITY_ALLOWLIST:{relative}")

    if errors:
        print("WRITE_CAPABILITY_GATE=FAILED")
        for error in errors:
            print(error)
        return 1

    print("WRITE_CAPABILITY_GATE=PASSED")
    for relative in sorted(observed_privileged):
        print(f"ALLOWLISTED:{relative}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
