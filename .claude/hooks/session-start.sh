#!/bin/bash
# Session-start dependency installer for Claude Code on the web.
# Idempotent — skips dirs where node_modules already exists.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

install_npm() {
  local dir="$REPO/$1"
  if [ -f "$dir/package.json" ] && [ ! -d "$dir/node_modules" ]; then
    echo "  installing $1..."
    npm install --prefix "$dir" --prefer-offline --no-audit --no-fund --silent
  fi
}

echo "SessionStart: installing npm deps..."

# Install in dependency order
install_npm packages/shared
install_npm sovereign-omega-v2
install_npm hub
install_npm platform-picker
install_npm hook-generator
install_npm content-calendar
install_npm cockpit
install_npm studio
install_npm enterprise
install_npm aegisomega-webgpu

echo "SessionStart: all deps ready."

# Python agent-layer deps (bridge + swarm). Idempotent: skip if already importable.
if [ -f "$REPO/sovereign-omega-v2/python/requirements.txt" ]; then
  if ! python -c "import anthropic" >/dev/null 2>&1; then
    echo "  installing python agent deps..."
    pip install -q -r "$REPO/sovereign-omega-v2/python/requirements.txt" 2>/dev/null || true
  fi
fi

# Complete orientation synchronously before SessionStart returns. SessionStart
# surfaces ground-truth failure as non-zero, but UserPromptSubmit is the actual
# fail-closed prompt admission boundary supported by Claude Code. This hook must
# never background repository state and then let the session assume it is known.
# Per WORKFLOW.md: no session starts blind; nothing is "done" until it is on main.
if ! bash "$REPO/scripts/ground-truth.sh"; then
  echo "SessionStart: REPOSITORY KNOWLEDGE / CONSTITUTIONAL GROUND TRUTH FAILED" >&2
  echo "SessionStart: refusing blind agent execution." >&2
  exit 1
fi
