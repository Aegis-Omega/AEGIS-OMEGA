#!/usr/bin/env python3
"""AEGIS Holon v1: portable, deterministic, fail-closed task admission *advice*.

No network, external actions, credentials or runtime dependencies. Accepts JSON
from scripts/agent_context.py (or a conforming adapter), not an agent's prose.
Does NOT authenticate reporters, authorize writes, or verify mathematical truth.
The output is an advisory allocation decision, NOT admission to production.

Usage: python3 scripts/holon_contract.py TASK.json CONTEXT.json [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

VERSION = "aegis.holon.task/1"
SHA256 = re.compile(r"^[a-f0-9]{40}$")
ALLOWED_MODES = frozenset({"inspect", "contribute", "release"})
ALLOWED_FIELDS = frozenset({"schema", "id", "operator_goal", "domain", "mode", "issue", "acceptance", "dependencies"})
MAX_FILE_BYTES = 1024 * 1024


def canonical_hash(value: Any) -> str:
    """Hash canonical UTF-8 JSON for test replay, not for signer identity."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _as_dict(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _ident(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value):
        raise ValueError(f"{field} must be a nonempty portable identifier")
    return value


def _schema(task: dict) -> None:
    if any(key not in ALLOWED_FIELDS for key in task):
        raise ValueError("unexpected task fields; update the versioned contract")
    if task.get("schema") != VERSION:
        raise ValueError("unknown task schema")
    _ident(task.get("id"), "task.id")
    goal = task.get("operator_goal")
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 4000:
        raise ValueError("operator_goal must be meaningful and bounded")
    _ident(task.get("domain"), "task.domain")
    if task.get("mode") not in ALLOWED_MODES:
        raise ValueError("unsupported mode")
    acceptance = task.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance or len(acceptance) > 100:
        raise ValueError("at least one bounded acceptance criterion required")
    keys = set()
    for row in acceptance:
        _as_dict(row, "acceptance entry")
        key = _ident(row.get("id"), "acceptance.id")
        if key in keys:
            raise ValueError("duplicate acceptance identifier")
        keys.add(key)
        criterion = row.get("criterion")
        if not isinstance(criterion, str) or not criterion.strip() or len(criterion) > 2000:
            raise ValueError("acceptance criterion must be meaningful")
    issue = task.get("issue")
    if task["mode"] != "inspect":
        if type(issue) is not int or issue < 1:
            raise ValueError("shared mutations require an explicit positive issue number")
    elif issue is not None and (type(issue) is not int or issue < 1):
        raise ValueError("issue must be positive when present")
    if "dependencies" in task:
        dep = task["dependencies"]
        if not isinstance(dep, list) or len(dep) > 100:
            raise ValueError("dependencies must be a bounded list")
        seen = set()
        for d in dep:
            v = _ident(d, "dependency")
            if v == task["id"] or v in seen:
                raise ValueError("circular self-reference or duplicate dependency")
            seen.add(v)
    if "operator_approval" in task:
        # A string, flag, and claimed agent are NOT cryptographic authorization.
        raise ValueError("operator approval cannot be self-asserted in task manifest")


def assess(task: dict, state: dict) -> dict:
    """Produce a monotonic, conservative coordination receipt.

    This never grants permission for consequential action, and an empty blockers
    list is never equivalent to authorization. 'READY_FOR_ASSIGNMENT_REVIEW' is
    still a *candidate*, requiring external governance and evidence checks.
    """
    _as_dict(task, "task")
    _schema(task)
    _as_dict(state, "state")

    blockers: list[str] = []
    observations: list[str] = []
    if task["mode"] != "inspect":
        freshness = state.get("main_freshness")
        sha = freshness.get("sha") if isinstance(freshness, dict) else None
        if (not isinstance(freshness, dict) or freshness.get("state") != "FRESH"
                or not isinstance(sha, str) or not SHA256.fullmatch(sha)):
            blockers.append("MAIN_EXACT_HEAD_NOT_VERIFIED")
        if state.get("source") != "github":
            blockers.append("PR_INVENTORY_NOT_VERIFIED")
        if state.get("issue_source") != "github":
            blockers.append("ISSUE_BOARD_NOT_VERIFIED")
        if state.get("ci_billing_locked") is True:
            blockers.append("CI_BILLING_LOCK_REPORTED")
        if state.get("ci_billing_locked") is None:
            blockers.append("CI_HEALTH_NOT_VERIFIED")

    matches = state.get("issue_matches")
    if not isinstance(matches, list):
        matches = []
        if task["mode"] != "inspect":
            blockers.append("ISSUE_MATCHES_UNAVAILABLE")
    matching_issue = []
    for item in matches:
        if isinstance(item, dict) and item.get("number") == task.get("issue"):
            matching_issue.append(item)
    if task["mode"] != "inspect":
        if len(matching_issue) != 1:
            blockers.append("TASK_ISSUE_NOT_RESOLVED")
        else:
            labels = matching_issue[0].get("labels")
            if not isinstance(labels, list) or any(not isinstance(x, str) for x in labels):
                blockers.append("ISSUE_LABELS_NOT_VERIFIED")
            else:
                if "needs-operator" in labels:
                    blockers.append("OPERATOR_ACTION_REQUIRED")
                if "claimed" in labels:
                    blockers.append("EXISTING_CLAIM_REQUIRES_COORDINATION")

    overlaps = state.get("overlaps")
    if task["mode"] != "inspect":
        if not isinstance(overlaps, list):
            blockers.append("PR_OVERLAPS_UNAVAILABLE")
        elif overlaps:
            blockers.append("EXISTING_PR_REQUIRES_REVIEW")
    if task.get("dependencies"):
        blockers.append("DEPENDENCY_EVIDENCE_NOT_VERIFIED")
    if task["mode"] == "release":
        blockers.append("RELEASE_REQUIRES_EXTERNAL_OPERATOR_ADMISSION")
    if task["mode"] == "inspect":
        observations.append("READ_ONLY_INSPECTION_DOES_NOT_REQUIRE_REMOTE_STATE")
    else:
        observations.append("WORK_ALLOCATION_ONLY_NOT_AUTHORIZATION")
    observations.append("MODEL_IDENTITY_AND_APPROVAL_NOT_AUTHENTICATED")
    observations.append("ACCEPTANCE_RESULTS_REQUIRE_INDEPENDENT_EVIDENCE")

    blockers = list(dict.fromkeys(blockers))
    disposition = ("READ_ONLY_INSPECTION" if task["mode"] == "inspect"
                   else "HOLD" if blockers else "READY_FOR_ASSIGNMENT_REVIEW")
    return {
        "protocol": VERSION,
        "task_id": task["id"],
        "task_sha256": canonical_hash(task),
        "basis_head": state.get("main_freshness", {}).get("sha") if isinstance(state.get("main_freshness"), dict) else None,
        "mode": task["mode"],
        "domain": task["domain"],
        "disposition": disposition,
        "blockers": blockers,
        "observations": observations,
        "admission": "NOT_ADMITTED",
        "authorization": "NOT_VERIFIED",
        "claim_truth": "NOT_VERIFIED",
        "acceptance_criteria_count": len(task["acceptance"]),
        "accepted_evidence_count": 0,
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"input file missing or exceeds {MAX_FILE_BYTES} bytes")
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f, object_pairs_hook=_unique_object,
                          parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f"invalid {c}")))
    return _as_dict(value, "input")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable AEGIS holon allocation preflight (never an authority grant)")
    parser.add_argument("task", type=Path)
    parser.add_argument("context", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = assess(_load(args.task), _load(args.context))
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError, OverflowError) as exc:
        result = {"protocol": VERSION, "disposition": "HOLD",
                  "blockers": ["INVALID_OR_UNVERIFIED_INPUT"], "error": str(exc),
                  "admission": "NOT_ADMITTED", "authorization": "NOT_VERIFIED"}
    if args.json:
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    else:
        print(f"AEGIS HOLON: {result['disposition']} | admission: {result['admission']}")
        for b in result["blockers"]:
            print(f"  HOLD: {b}")
    return 0 if result["disposition"] in ("READ_ONLY_INSPECTION", "READY_FOR_ASSIGNMENT_REVIEW") else 2


if __name__ == "__main__":
    sys.exit(main())