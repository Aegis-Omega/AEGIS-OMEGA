#!/usr/bin/env python3
"""Fail-closed Claude PreToolUse guard for frozen Sovereign Omega files.

Receives the actual JSON hook payload on stdin; never trusts an ambient
CLAUDE_TOOL_INPUT_PATH variable. Applies equally to Write and Edit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN = (
    "python/gate.py",
    "python/dna.py",
    "python/router.py",
    "docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md",
    "ARTIFACT_REGISTRY.md",
)


def response(decision: str, reason: str) -> dict:
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}


def evaluate(payload: object) -> dict:
    if not isinstance(payload, dict):
        return response("deny", "AEGIS frozen guard: malformed hook payload")
    tool = payload.get("tool_name") or payload.get("toolName")
    if tool not in ("Write", "Edit"):
        return response("deny", "AEGIS frozen guard: unexpected tool invocation")
    args = payload.get("tool_input") or payload.get("toolInput")
    if not isinstance(args, dict):
        return response("deny", "AEGIS frozen guard: malformed tool input")
    target = args.get("file_path") or args.get("path")
    if not isinstance(target, str) or not target.strip():
        return response("deny", "AEGIS frozen guard: missing target path")
    try:
        path = Path(target)
        # Root agent file paths begin with sovereign-omega-v2/, while nested
        # project agents use paths relative to ROOT. Resolve both explicitly.
        if path.is_absolute():
            resolved = path.resolve()
        elif path.parts and path.parts[0] == ROOT.name:
            resolved = (ROOT.parent / path).resolve()
        else:
            resolved = (ROOT / path).resolve()
        protected = {(ROOT / relative).resolve() for relative in FROZEN}
        protected.update({
            (ROOT.parent / ".claude.json").resolve(),
            (ROOT.parent / "skill-hashes.sha256").resolve(),
        })
    except (OSError, ValueError, RuntimeError):
        return response("deny", "AEGIS frozen guard: cannot resolve target path")
    if resolved in protected:
        return response("deny", "AEGIS frozen constitutional file: modification requires Guardian approval and an authorized controlled path")
    return response("allow", "AEGIS frozen guard: target is not a named frozen file; other authorization rules still apply")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        verdict = evaluate(payload)
    except Exception:
        verdict = response("deny", "AEGIS frozen guard: invalid JSON or runtime failure")
    print(json.dumps(verdict, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
