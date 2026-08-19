#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = "scripts/aegis-provider-mcp.mjs"
FORBIDDEN = {
    "AEGIS_AUTHORITY_SIGNING_KEY_HEX",
    "AEGIS_AUTHORITY_ISSUER_KEY_ID",
    "AEGIS_TRUSTED_OPERATOR_KEYS_JSON",
    "AEGIS_AUTHORITY_VERIFY_KEYS_JSON",
    "AEGIS_APPROVAL_GRANT_JSON",
}


def fail(code: str) -> None:
    raise SystemExit(code)


def assert_relative_launcher(args: list[str], provider: str, model_ref: str) -> None:
    if args != [LAUNCHER, provider, model_ref]:
        fail(f"ENTRYPOINT_ARGS_MISMATCH:{provider}:{args!r}")
    first = Path(args[0])
    if first.is_absolute() or ".." in first.parts:
        fail(f"ENTRYPOINT_PATH_NOT_REPOSITORY_RELATIVE:{provider}")


def assert_no_embedded_authority_secrets(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for name in FORBIDDEN:
        if name in text:
            fail(f"AUTHORITY_SECRET_SURFACE_FORBIDDEN:{path}:{name}")
    if re.search(r"(?:/home/|[A-Za-z]:\\|/Users/)", text):
        fail(f"HOST_ABSOLUTE_PATH_FORBIDDEN:{path}")


def validate_claude() -> None:
    path = ROOT / ".mcp.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    server = data["mcpServers"]["aegis"]
    if server.get("command") != "node":
        fail("CLAUDE_MCP_COMMAND_MISMATCH")
    assert_relative_launcher(server.get("args", []), "anthropic", "@AEGIS_CLAUDE_MODEL")
    assert_no_embedded_authority_secrets(path)


def validate_gemini() -> None:
    path = ROOT / ".gemini" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("mcp", {}).get("allowed") != ["aegis"]:
        fail("GEMINI_MCP_ALLOWLIST_MISMATCH")
    server = data["mcpServers"]["aegis"]
    if server.get("command") != "node" or server.get("cwd") != ".":
        fail("GEMINI_MCP_COMMAND_OR_CWD_MISMATCH")
    assert_relative_launcher(server.get("args", []), "google", "@AEGIS_GEMINI_MODEL")
    assert_no_embedded_authority_secrets(path)


def validate_codex() -> None:
    path = ROOT / ".codex" / "config.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    server = data["mcp_servers"]["aegis"]
    if server.get("command") != "node" or server.get("required") is not True:
        fail("CODEX_MCP_COMMAND_OR_REQUIRED_MISMATCH")
    if server.get("default_tools_approval_mode") != "prompt":
        fail("CODEX_MCP_APPROVAL_MODE_MISMATCH")
    expected_tools = {
        "aegis_organism_status",
        "aegis_next_work",
        "aegis_contribute",
        "aegis_contribute_text",
    }
    if set(server.get("enabled_tools", [])) != expected_tools:
        fail("CODEX_MCP_TOOL_ALLOWLIST_MISMATCH")
    assert_relative_launcher(server.get("args", []), "openai", "@AEGIS_CODEX_MODEL")
    assert_no_embedded_authority_secrets(path)


def main() -> None:
    validate_claude()
    validate_gemini()
    validate_codex()
    print("CROSS_PROVIDER_ENTRYPOINTS=PASS")
    print("SHARED_LAUNCHER=PASS")
    print("PROVIDER_CONFIG_AUTHORITY_SIGNER_SECRET=ABSENT")
    print("HOST_ABSOLUTE_PATH=ABSENT")


if __name__ == "__main__":
    main()
