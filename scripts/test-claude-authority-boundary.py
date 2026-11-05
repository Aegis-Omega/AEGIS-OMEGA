#!/usr/bin/env python3
"""Regression tests for Claude Code mutation authority around canonical main."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_SETTINGS = REPO_ROOT / ".claude" / "settings.json"
SOVEREIGN_SETTINGS = REPO_ROOT / "sovereign-omega-v2" / ".claude" / "settings.json"
AUTHORITY_GUARD = REPO_ROOT / "scripts" / "claude-authority-guard.py"
TARGET_REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
GITHUB_CONTENT_WRITERS = (
    "mcp__github__push_files",
    "mcp__github__create_or_update_file",
    "mcp__github__delete_file",
)


def load_settings(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pretool_matchers(settings: dict) -> str:
    return "\n".join(
        str(entry.get("matcher", ""))
        for entry in settings.get("hooks", {}).get("PreToolUse", [])
    )


class ClaudeAuthorityConfigurationTests(TestCase):
    def test_root_and_nested_configs_register_authority_guard(self) -> None:
        for path in (ROOT_SETTINGS, SOVEREIGN_SETTINGS):
            with self.subTest(settings=str(path.relative_to(REPO_ROOT))):
                settings = load_settings(path)
                matchers = pretool_matchers(settings)
                self.assertIn("Bash", matchers)
                for tool in GITHUB_CONTENT_WRITERS:
                    self.assertIn(tool, matchers)
                commands = "\n".join(
                    str(hook.get("command", ""))
                    for entry in settings.get("hooks", {}).get("PreToolUse", [])
                    for hook in entry.get("hooks", [])
                )
                self.assertIn("claude-authority-guard.py", commands)

    def test_canonical_anchors_are_denied_to_direct_write_edit(self) -> None:
        root_deny = set(load_settings(ROOT_SETTINGS).get("permissions", {}).get("deny", []))
        sovereign_deny = set(load_settings(SOVEREIGN_SETTINGS).get("permissions", {}).get("deny", []))
        for operation in ("Write", "Edit"):
            self.assertIn(f"{operation}(.claude.json)", root_deny)
            self.assertIn(f"{operation}(skill-hashes.sha256)", root_deny)
            self.assertIn(f"{operation}(../.claude.json)", sovereign_deny)
            self.assertIn(f"{operation}(../skill-hashes.sha256)", sovereign_deny)


class ClaudeAuthorityGuardBehaviorTests(TestCase):
    def run_guard(self, tool_name: str, tool_input: dict) -> dict:
        self.assertTrue(AUTHORITY_GUARD.is_file(), "Claude authority guard is missing")
        proc = subprocess.run(
            ["python3", str(AUTHORITY_GUARD)],
            input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip(), "guard emitted no decision")
        return json.loads(proc.stdout)

    def decision(self, tool_name: str, tool_input: dict) -> str:
        result = self.run_guard(tool_name, tool_input)
        return result["hookSpecificOutput"]["permissionDecision"]

    def test_every_bash_git_push_is_denied(self) -> None:
        for command in (
            "git push",
            "git push origin feature/x",
            "npm test && git push origin main",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.decision("Bash", {"command": command}), "deny")

    def test_non_push_bash_is_allowed(self) -> None:
        self.assertEqual(self.decision("Bash", {"command": "git status --short"}), "allow")

    def test_github_content_writes_require_explicit_non_main_branch(self) -> None:
        for tool in GITHUB_CONTENT_WRITERS:
            with self.subTest(tool=tool, case="missing"):
                self.assertEqual(
                    self.decision(tool, {"repository": TARGET_REPOSITORY}),
                    "deny",
                )
            for branch in ("main", "refs/heads/main", "origin/main", "  main  "):
                with self.subTest(tool=tool, branch=branch):
                    self.assertEqual(
                        self.decision(
                            tool,
                            {"repository": TARGET_REPOSITORY, "branch": branch},
                        ),
                        "deny",
                    )

    def test_github_content_writes_allow_explicit_non_main_branch(self) -> None:
        for tool in GITHUB_CONTENT_WRITERS:
            with self.subTest(tool=tool):
                self.assertEqual(
                    self.decision(
                        tool,
                        {
                            "repository": TARGET_REPOSITORY,
                            "branch": "repair/example-v1",
                        },
                    ),
                    "allow",
                )


if __name__ == "__main__":
    main()
