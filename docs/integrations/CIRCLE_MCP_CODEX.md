# Circle MCP / Codex — bounded operator setup (Issue #756)

This is a small, opt-in MCP configuration slice, **not** completion of the portable
MCP + A2A connector protocol in #756. It does not modify the repository's
`.mcp.json`, authority enforcement, `main`, production credentials or cloud services.

The exact endpoint is `https://api.circle.com/v1/codegen/mcp` (Circle Codegen,
not CircleCI). Codex CLI stores remote servers in its own `config.toml`, not the
Claude-compatible root `.mcp.json`.

## Inspect without changing anything

```bash
python3 scripts/circle_mcp_preflight.py --codex-home "$HOME/.codex"
```

## Register into an isolated, explicitly chosen Codex profile

Requires Python 3.11+ and a separately installed Codex CLI. Network access is
needed by the CLI. Installation is **not** attempted by this script.

```bash
export CODEX_HOME="$HOME/.local/share/aegis-circle-codex"
python3 scripts/circle_mcp_preflight.py --codex-home "$CODEX_HOME" --register
codex mcp get circle
codex mcp list
```

To register into your regular profile, explicitly pass `--codex-home "$HOME/.codex"`.
Existing mismatched/disabled/invalid registrations are left untouched. No
API key is required to store the server URL. If Circle later requires
interactive OAuth, perform that authorization yourself with the official CLI.

`CONFIGURED_ONLY` confirms **only** that the correct URL is stored and enabled.
It is not proof of successful network initialization, authenticated access,
remote tool discovery, or permission to create wallets, move funds, deploy
contracts or perform other consequential actions. All such actions require
separate operator approval and trusted verification.

## Verify source-level fail-closed behavior offline

```bash
python3 -m unittest discover -s scripts -p 'test_circle_mcp_preflight.py' -v
```

The tests cover missing/malformed/disabled/mismatched/symlink config, CLI
failure, no-binary condition, simulated successful CLI registration, and a
success response with absent persisted config. They do **not** contact Circle.

## Code ownership / acceptance

This addition deliberately does not introduce another agent dispatcher, policy
authority, admission mechanism or worker runtime. For the rest of #756,
version negotiation, authenticated resource audiences, interoperability with
independent clients, auth denial fixtures and protocol conformance remain open.
