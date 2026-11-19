#!/usr/bin/env python3
"""Fail-closed PreToolUse guard for Claude repository mutation authority.

The model may inspect, edit, commit, and mutate explicit non-main branches, but it
must not be able to turn an ordinary tool call into a direct write to canonical
``main``. Canonical cognitive anchors are additionally protected by settings-level
Write/Edit denies; this guard covers shell pushes and GitHub content-write MCPs.
"""
from __future__ import annotations

import json
import posixpath
import re
import sys
from typing import Any

TARGET_REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
# The plugin name is case-insensitive, while accepted tool verbs are explicit.
# A content mutation through MCP must obey the SAME frozen-file rule as Write/Edit.
GITHUB_CONTENT_WRITERS = {
    "mcp__github__push_files",
    "mcp__github__create_or_update_file",
    "mcp__github__delete_file",
    "mcp__github__update_file",
    "mcp__github__create_file",
}
GITHUB_REF_WRITERS = {"mcp__github__update_ref"}
GITHUB_PR_MERGERS = {"mcp__github__merge_pull_request"}
FROZEN_REPO_PATHS = frozenset({
    "sovereign-omega-v2/python/gate.py",
    "sovereign-omega-v2/python/dna.py",
    "sovereign-omega-v2/python/router.py",
    "sovereign-omega-v2/docs/sovereign_omega_integrated_spec_v2.md",
    "sovereign-omega-v2/artifact_registry.md",
    ".claude.json",
    "skill-hashes.sha256",
})
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


def _canonical_repo_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        return None
    path = value.strip().replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:/", path):
        return None
    canonical = posixpath.normpath(path)
    if canonical in (".", "..") or canonical.startswith("../"):
        return None
    return canonical.casefold()


def _written_paths(tool_name: str, args: dict[str, Any]) -> list[str] | None:
    if tool_name.endswith("__push_files"):
        files = args.get("files")
        if not isinstance(files, list) or not files:
            return None
        raw_paths = [file.get("path") if isinstance(file, dict) else None for file in files]
    else:
        raw_paths = [args.get("path", args.get("file_path"))]
    paths = [_canonical_repo_path(path) for path in raw_paths]
    return paths if all(path is not None for path in paths) else None


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _decision("deny", "AEGIS authority guard: malformed hook payload")
    tool_name = payload.get("tool_name") or payload.get("toolName") or ""
    if not isinstance(tool_name, str):
        return _decision("deny", "AEGIS authority guard: malformed tool_name")
    normalized_tool = tool_name.casefold()
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

    if normalized_tool in GITHUB_PR_MERGERS:
        repository = _repository_name(tool_input)
        if not repository:
            return _decision("deny", "AEGIS authority guard: PR merge requires explicit repository")
        if repository.casefold() != TARGET_REPOSITORY.casefold():
            return _decision("allow", "AEGIS authority guard: merge outside AEGIS target boundary")
        number = tool_input.get("pr_number")
        if type(number) is not int or number < 1:
            return _decision("deny", "AEGIS authority guard: PR merge requires a valid PR number")
        expected = tool_input.get("expected_head_sha")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", expected):
            return _decision("deny", "AEGIS authority guard: PR merge requires exact candidate head SHA")
        method = tool_input.get("merge_method")
        if method not in (None, "merge", "squash", "rebase"):
            return _decision("deny", "AEGIS authority guard: invalid PR merge method")
        return _decision("allow", "AEGIS authority guard: exact-head PR merge candidate; GitHub protections and operator approval remain mandatory")

    if normalized_tool in GITHUB_REF_WRITERS:
        repository = _repository_name(tool_input)
        if not repository:
            return _decision("deny", "AEGIS authority guard: branch ref mutation requires an explicit repository")
        if repository.casefold() != TARGET_REPOSITORY.casefold():
            return _decision("allow", "AEGIS authority guard: repository outside AEGIS boundary")
        branch = _branch_name(tool_input).strip()
        normalized = branch.casefold()
        if not normalized or normalized in MAIN_REFS:
            return _decision("deny", "AEGIS authority guard: cannot directly mutate canonical main or an unspecified ref")
        target_sha = tool_input.get("sha")
        if not isinstance(target_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", target_sha):
            return _decision("deny", "AEGIS authority guard: non-main ref update needs an exact target SHA")
        expected_sha = tool_input.get("expected_sha")
        if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", expected_sha):
            return _decision("deny", "AEGIS authority guard: non-main ref update needs an exact 40-hex head lease")
        if tool_input.get("force", False) is not False:
            return _decision("deny", "AEGIS authority guard: force updates need a separate, explicit authority path")
        return _decision("allow", "AEGIS authority guard: leased non-main branch ref update")

    if normalized_tool in GITHUB_CONTENT_WRITERS:
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

        paths = _written_paths(normalized_tool, tool_input)
        if paths is None:
            return _decision("deny", "AEGIS authority guard: missing or unsafe destination path")
        for path in paths:
            if path in FROZEN_REPO_PATHS:
                return _decision("deny", f"AEGIS authority guard: protected source path cannot be mutated via GitHub content writer ({path})")

        return _decision(
            "allow",
            f"AEGIS authority guard: explicit non-main branch accepted ({branch.strip()}); {len(paths)} non-frozen path(s) checked",
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
