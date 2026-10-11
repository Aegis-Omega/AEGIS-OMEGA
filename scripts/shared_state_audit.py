#!/usr/bin/env python3
"""Read-only comparison of the dated agent handoff against the complete PR board.

Advisory only. Full SHA comparison is byte-identity of a PR head, never a
signature, correctness, admission, or permission to perform external actions.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA = "aegis.agent.shared-state.snapshot/1"
REPO = "Aegis-Omega/AEGIS-OMEGA"
SNAPSHOT = Path(__file__).resolve().parent.parent / "docs/coordination/AEGIS_AGENT_SHARED_STATE_20261011.json"
MAX_BYTES = 1_048_576
SHA = re.compile(r"[a-f0-9]{40}\Z")


def _reject_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate snapshot key")
        result[key] = value
    return result


def inspect(prs, pr_source, main_receipt, *, snapshot_path=SNAPSHOT):
    """Only a fresh, complete GitHub PR list can establish exact-head parity.

    Any parse/shape/source error is UNKNOWN, never a synthetic empty board or
    an inferred permission. Other repositories remain explicitly unverified.
    """
    output = {"schema": "aegis.agent.shared-state.audit/1",
              "authority_effect": "NONE", "admission": "NOT_VERIFIED",
              "disposition": "HOLD_SHARED_STATE_UNVERIFIED",
              "snapshot_file": str(snapshot_path), "observations": [],
              "verified_primary_lanes": 0, "stale_primary_lanes": 0,
              "out_of_scope_lanes": 0, "reason": None}
    try:
        file = Path(snapshot_path)
        size = file.stat().st_size
        if not 0 < size <= MAX_BYTES:
            raise ValueError("Snapshot size outside bound")
        data = json.loads(file.read_text(encoding="utf-8"),
                          object_pairs_hook=_reject_duplicate_keys,
                          parse_constant=_reject_constant)
        if (not isinstance(data, dict) or data.get("schema") != SCHEMA
                or data.get("advisory_only") is not True
                or data.get("authority_effect") != "NONE"
                or data.get("completeness") != "SELECTED_ACTIVE_LANES_ONLY"
                or not isinstance(data.get("lanes"), list)
                or not data["lanes"] or len(data["lanes"]) > 1000):
            raise ValueError("Unknown or unsafe snapshot schema")
        seen = set()
        expected = []
        for row in data["lanes"]:
            if not isinstance(row, dict):
                raise ValueError("Invalid lane")
            repo, pr = row.get("repo"), row.get("pr")
            head = row.get("observed_head_before_coordination_commit")
            if (not isinstance(repo, str) or not repo
                    or type(pr) is not int or pr < 1
                    or not isinstance(head, str) or not SHA.fullmatch(head)
                    or (repo, pr) in seen):
                raise ValueError("Invalid or duplicate PR identity")
            seen.add((repo, pr))
            expected.append((repo, pr, head))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        output["reason"] = "SNAPSHOT_MISSING_OR_INVALID: " + type(exc).__name__
        return output

    # A 'cache' inventory can be up to ten minutes old; a branch fallback,
    # incomplete page or unknown main is never fresh authoritative evidence.
    if (pr_source != "github" or not isinstance(main_receipt, dict)
            or main_receipt.get("state") != "FRESH"):
        output["reason"] = "FRESH_MAIN_AND_COMPLETE_GITHUB_PR_LIST_REQUIRED"
        return output
    if not isinstance(prs, list):
        output["reason"] = "MALFORMED_LIVE_PR_LIST"
        return output
    live = {}
    for row in prs:
        if (not isinstance(row, dict) or type(row.get("n")) is not int
                or row["n"] < 1 or not isinstance(row.get("s"), str)
                or not SHA.fullmatch(row["s"]) or row["n"] in live):
            output["reason"] = "MALFORMED_OR_DUPLICATED_LIVE_PR"
            return output
        live[row["n"]] = row["s"]

    for repo, pr, old in expected:
        status = ("OTHER_REPOSITORY_NOT_CHECKED" if repo != REPO
                  else "OPEN_PR_NOT_IN_SNAPSHOT_BOARD" if pr not in live
                  else "EXACT_HEAD_MATCH" if live[pr] == old
                  else "STALE_HEAD")
        item = {"repo": repo, "pr": pr, "recorded_head": old,
                "current_head": live.get(pr) if repo == REPO else None,
                "status": status}
        output["observations"].append(item)
        if status == "EXACT_HEAD_MATCH":
            output["verified_primary_lanes"] += 1
        elif repo == REPO:
            output["stale_primary_lanes"] += 1
        else:
            output["out_of_scope_lanes"] += 1
    # Snapshot may be accurate for some branch heads, but it contains only
    # selected lanes, no signed authority, and no cross-repo confirmation.
    output["disposition"] = "REVIEW_CURRENT_SHARED_STATE"
    output["reason"] = ("STALE_OR_MISSING_PR_HEADS" if output["stale_primary_lanes"]
                        else "PRIMARY_SHA_MATCH_ONLY_NOT_GLOBAL_COMPLETENESS")
    return output
