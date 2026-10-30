#!/usr/bin/env bash
# Shared MCP entry point from either repository scope. stdout is MCP only.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/sovereign-omega-v2/mcp-server"
if [[ ! -f node_modules/.package-lock.json ]] || [[ package-lock.json -nt node_modules/.package-lock.json ]]; then
  npm ci --silent >&2
fi
if [[ ! -f dist/index.js ]] || [[ tsconfig.json -nt dist/index.js ]] || [[ package-lock.json -nt dist/index.js ]] || [[ -n "$(find src -type f -newer dist/index.js -print -quit 2>/dev/null)" ]]; then
  npm run build >&2
fi
# Node's env-file loader preserves caller environment overrides; no shell eval.
# Empty client interpolation placeholders leave room for the root env-file.
for key in AEGIS_BASE_URL AEGIS_BRIDGE_URL AEGIS_API_KEY; do
  if [[ -z "${!key:-}" ]]; then unset "$key"; fi
done
if [[ -f "$REPO_ROOT/.env" ]]; then
  exec node --env-file="$REPO_ROOT/.env" dist/index.js
fi
exec node dist/index.js
