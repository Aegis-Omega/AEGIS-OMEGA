#!/usr/bin/env python3
"""Offline contract tests for direct-Anthropic Claude 5.5 runtime defaults."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]


def _module(path: str) -> ast.Module:
    return ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"), filename=path)


def _env_default(path: str, variable: str, env_key: str) -> str:
    tree = _module(path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == variable for t in node.targets):
            continue
        call = node.value
        if not isinstance(call, ast.Call) or len(call.args) < 2:
            break
        if not (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "get"
            and isinstance(call.func.value, ast.Attribute)
            and call.func.value.attr == "environ"
        ):
            break
        key, default = call.args[:2]
        if not (
            isinstance(key, ast.Constant) and key.value == env_key
            and isinstance(default, ast.Constant) and isinstance(default.value, str)
        ):
            break
        return default.value
    raise AssertionError(f"{path}:{variable} env default not found")


def _literal_assignment(path: str, variable: str):
    tree = _module(path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(t, ast.Name) and t.id == variable for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path}:{variable} assignment not found")


class Anthropic55RuntimeDefaultsTests(TestCase):
    def test_direct_runtime_defaults_use_opus_55(self) -> None:
        self.assertEqual(
            _env_default(
                "sovereign-omega-v2/python/platform_helpers.py",
                "SWARM_MODEL",
                "AEGIS_SWARM_MODEL",
            ),
            "claude-opus-5-5",
        )
        self.assertEqual(
            _env_default("agents/tool_runner.py", "DEFAULT_MODEL", "AEGIS_DEFAULT_MODEL"),
            "claude-opus-5-5",
        )
        self.assertEqual(
            _env_default("agents/batch_bridge.py", "MODEL", "AEGIS_SWARM_MODEL"),
            "claude-opus-5-5",
        )

    def test_batch_price_guard_uses_current_55_rates(self) -> None:
        prices = _literal_assignment("agents/batch_bridge.py", "_PRICE")
        self.assertEqual(prices["claude-opus-5-5"], (4.0, 20.0))
        self.assertEqual(prices["claude-sonnet-5-5"], (2.0, 10.0))

    def test_mythos_pipeline_uses_opus_55_adaptive_thinking(self) -> None:
        source = (REPO_ROOT / "sovereign-omega-v2/scripts/mythos-pipeline.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("model: 'claude-opus-5-5'", source)
        self.assertIn("thinking: { type: 'adaptive' }", source)


if __name__ == "__main__":
    main()
