#!/usr/bin/env python3
"""Read-only OPTIMUS specialist pilot: reuse the existing Apple OSS Watch contract.

Executes one bounded PUBLIC GitHub-source observation for an existing selected
issue. Does not execute model inference, grant authority, update latest_known,
write GitHub comments, send messages, or mark work complete.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request
from typing import Any, Callable

from scripts.optimus_company_tick import REPO, SHA, stable_hash

SCHEMA = "AEGIS_OPTIMUS_APPLE_OSS_OBSERVATION_V1"
TARGET_ISSUE = REPO + "#249"
WORKFLOW = ".github/workflows/apple-oss-watch.yml"
STATE = "reports/apple-oss-state.json"
ALLOW = {
    "apple-oss-distributions/distribution-macOS": "tag",
    "apple-oss-distributions/xnu": "tag",
    "apple/swift": "release",
    "apple/swift-syntax": "release",
}
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,119}\Z")


def _selection(receipt: Any, source_head: str) -> None:
    if (not isinstance(receipt, dict) or
            receipt.get("schema") != "AEGIS_OPTIMUS_TICK_V1" or
            receipt.get("selected_issue") != TARGET_ISSUE or
            receipt.get("source_head") != source_head or
            receipt.get("disposition") != "REVIEW_READY" or
            receipt.get("proposed_role") != "engineering" or
            receipt.get("topic") != "engineering" or
            receipt.get("selection_is_not_execution") is not True or
            receipt.get("authority_effect") != "NONE" or
            receipt.get("execution_effect") != "NONE" or
            receipt.get("spend_usd") != 0 or
            not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("receipt_hash", ""))) or
            receipt["receipt_hash"] != stable_hash({k: v for k, v in receipt.items()
                                                    if k != "receipt_hash"})):
        raise ValueError("SELECTION_RECEIPT_INVALID_OR_NOT_ALLOWLISTED")


def _contract(workflow: str, state: dict[str, Any]) -> dict[str, str | None]:
    # Never invent new targets from task prose, the API or downstream agents.
    names = re.findall(r'^\s+check\s+"([^"]+)"\s+(tag|release)\s*$',
                       workflow, re.M)
    if (len(names) != 4 or dict(names) != ALLOW or
            not isinstance(state, dict) or
            not isinstance(state.get("repos"), dict) or
            set(state["repos"]) != set(ALLOW)):
        raise ValueError("EXISTING_WATCHER_CONTRACT_DRIFT")
    recorded: dict[str, str | None] = {}
    for repo, kind in names:
        cfg = state["repos"][repo]
        if (not isinstance(cfg, dict) or set(cfg) != {"kind", "latest_known"} or
                cfg["kind"] != kind or
                (cfg["latest_known"] is not None and
                 (not isinstance(cfg["latest_known"], str) or
                  VERSION.fullmatch(cfg["latest_known"]) is None))):
            raise ValueError("RECORDED_STATE_INVALID")
        recorded[repo] = cfg["latest_known"]
    return recorded


def fetch_public_release(repo: str, kind: str) -> str:
    if ALLOW.get(repo) != kind:
        raise ValueError("UNAPPROVED_PUBLIC_UPSTREAM")
    path = f"/repos/{repo}/releases/latest" if kind == "release" else f"/repos/{repo}/tags?per_page=1"
    request = urllib.request.Request("https://api.github.com" + path, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "AEGIS-OPTIMUS-readonly-oss/1",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=8) as response:
        data = response.read(131073)
        if len(data) > 131072:
            raise ValueError("UPSTREAM_BODY_TOO_LARGE")
    obj = json.loads(data)
    version = obj.get("tag_name") if kind == "release" and isinstance(obj, dict) else (
        obj[0].get("name") if kind == "tag" and isinstance(obj, list)
        and obj and isinstance(obj[0], dict) else None)
    if not isinstance(version, str) or VERSION.fullmatch(version) is None:
        raise ValueError("UPSTREAM_VERSION_UNKNOWN")
    return version


def inspect(*, selection: dict[str, Any], source_head: str, workflow: str,
            state: dict[str, Any], observed_at: str,
            fetcher: Callable[[str, str], str] = fetch_public_release) -> dict[str, Any]:
    if not isinstance(source_head, str) or not SHA.fullmatch(source_head):
        raise ValueError("EXACT_HEAD_REQUIRED")
    _selection(selection, source_head)
    # Only metadata of a historical point-in-time observation is asserted.
    if not isinstance(observed_at, str) or not observed_at.endswith("Z"):
        raise ValueError("OBSERVATION_TIME_INVALID")
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("OBSERVATION_TIME_INVALID") from exc
    recorded = _contract(workflow, state)
    rows = []
    for repo, kind in ALLOW.items():
        try:
            value = fetcher(repo, kind)
            if not isinstance(value, str) or VERSION.fullmatch(value) is None:
                raise ValueError("UPSTREAM_VERSION_UNKNOWN")
            status = "NO_CHANGE" if value == recorded[repo] else "UNACKNOWLEDGED_CHANGE"
            rows.append({"repository": repo, "kind": kind, "recorded": recorded[repo],
                         "current": value, "status": status})
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            rows.append({"repository": repo, "kind": kind, "recorded": recorded[repo],
                         "current": None, "status": "UNKNOWN",
                         "failure_class": type(exc).__name__})
    unresolved = any(row["status"] == "UNKNOWN" for row in rows)
    body = {
        "schema": SCHEMA, "source_head": source_head, "selected_issue": TARGET_ISSUE,
        "selection_receipt_hash": selection["receipt_hash"], "observed_at": observed_at,
        "watcher_sha256": hashlib.sha256(workflow.encode()).hexdigest(),
        "recorded_sha256": hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "upstreams": rows,
        "disposition": "HOLD_UPSTREAM_UNKNOWN" if unresolved else "OBSERVED_REQUIRES_OPERATOR_ACK",
        "source_kind": "PUBLIC_GITHUB_API_READ_ONLY",
        "work_performed": "UPSTREAM_RELEASE_COMPARISON_ONLY",
        "task_completed": False, "auto_acknowledged": False,
        "authority_effect": "NONE", "external_write_effect": "NONE",
        "paid_model_calls": 0, "claim_native_github_admission": False,
    }
    return {**body, "receipt_hash": stable_hash(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        if actual != args.source_head:
            raise ValueError("EXACT_HEAD_MISMATCH")
        if args.selection.is_symlink() or args.selection.stat().st_size > 32768:
            raise ValueError("SELECTION_PATH_INVALID")
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        paths = (WORKFLOW, STATE)
        content = []
        for p in paths:
            path = Path(p)
            if path.is_symlink() or not path.is_file():
                raise ValueError("SOURCE_FILE_MISSING_OR_SYMLINK")
            if subprocess.check_output(["git", "hash-object", p], text=True).strip() != \
                    subprocess.check_output(["git", "rev-parse", "HEAD:" + p], text=True).strip():
                raise ValueError("SOURCE_FILE_NOT_EXACT_HEAD")
            content.append(path.read_text(encoding="utf-8"))
        result = inspect(selection=selection, source_head=actual, workflow=content[0],
                         state=json.loads(content[1]),
                         observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema": SCHEMA, "disposition": "HOLD", "reason_class": type(exc).__name__,
                          "authority_effect": "NONE", "external_write_effect": "NONE"}))
        return 2
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 2 if result["disposition"] == "HOLD_UPSTREAM_UNKNOWN" else 0


if __name__ == "__main__":
    raise SystemExit(main())
