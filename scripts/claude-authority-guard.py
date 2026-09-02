#!/usr/bin/env python3
"""Fail-closed PreToolUse guard for Claude repository mutation authority.

The model may inspect, edit, commit, and mutate explicit non-main branches, but it
must not be able to turn an ordinary tool call into a direct write to canonical
``main``. Canonical cognitive anchors are additionally protected by settings-level
Write/Edit denies; this guard covers shell pushes and GitHub content-write MCPs.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

TARGET_REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
GITHUB_CONTENT_WRITERS = {
    "mcp__github__push_files",
    "mcp__github__create_or_update_file",
    "mcp__github__delete_file",
}
MAIN_REFS = {
    "main",
    "refs/heads/main",
    "origin/main",
    "refs/remotes/origin/main",
}

# Matches ordinary shell forms such as `git push`, chained `&& git push`, and
# `git -C <path> push`. False negatives are more dangerous than false positives
# here, so the guard deliberately treats any recognizable git-push invocation as
# privileged and requires the MCP branch-bound path instead.
GIT_PUSH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])git(?:\s+(?:-C|--git-dir|--work-tree|--namespace)\s+\S+|\s+-c\s+\S+|\s+--?[^\s]+)*\s+push(?:\s|$)",
    re.IGNORECASE,
)


def _decision(value: str, reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": value,
            "permissionDecisionReason": reason,
        }
    }


def _first_string(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _repository_name(tool_input: dict[str, Any]) -> str:
    value = _first_string(
        tool_input,
        "repository",
        "repository_full_name",
        "repo_full_name",
    )
    if value:
        return value

    owner = _first_string(tool_input, "owner", "repository_owner")
    repo = _first_string(tool_input, "repo", "repository_name")
    if owner and repo:
        return f"{owner}/{repo}"
    return ""


def _branch_name(tool_input: dict[str, Any]) -> str:
    return _first_string(tool_input, "branch", "branch_name", "ref")


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    tool_name = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        return _decision("deny", "AEGIS authority guard: malformed tool_input")

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if not isinstance(command, str):
            return _decision("deny", "AEGIS authority guard: malformed Bash command")
        if GIT_PUSH_RE.search(command):
            return _decision(
                "deny",
                "AEGIS authority guard: shell git push is forbidden; use a GitHub content writer with an explicit non-main branch",
            )
        return _decision("allow", "AEGIS authority guard: non-push Bash command")

    if tool_name in GITHUB_CONTENT_WRITERS:
        repository = _repository_name(tool_input)
        branch = _branch_name(tool_input)

        # A content writer without an explicit destination is not attributable
        # enough to authorize. This is intentionally fail-closed even if a tool
        # would otherwise default to the repository's default branch.
        if not repository:
            return _decision(
                "deny",
                "AEGIS authority guard: GitHub content write requires an explicit repository",
            )

        if repository.casefold() != TARGET_REPOSITORY.casefold():
            return _decision("allow", "AEGIS authority guard: repository is outside the AEGIS main boundary")

        if not branch:
            return _decision(
                "deny",
                "AEGIS authority guard: AEGIS content write requires an explicit non-main branch",
            )

        normalized = branch.strip().casefold()
        if normalized in MAIN_REFS:
            return _decision(
                "deny",
                "AEGIS authority guard: direct content mutation of canonical main is forbidden",
            )

        return _decision(
            "allow",
            f"AEGIS authority guard: explicit non-main branch accepted ({branch.strip()})",
        )

    return _decision("allow", "AEGIS authority guard: tool is outside this mutation boundary")


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            result = _decision("deny", "AEGIS authority guard: malformed hook payload")
        else:
            result = evaluate(payload)
    except Exception as exc:  # fail closed on parser/runtime faults
        result = _decision("deny", f"AEGIS authority guard failure: {type(exc).__name__}")

    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
