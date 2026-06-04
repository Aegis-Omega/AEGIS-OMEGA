#!/bin/bash
# Session-start dependency installer for Claude Code on the web.
# Idempotent — skips dirs where node_modules already exists.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

REPO="${CLAUDE_PROJECT_DIR:-/home/user/AEGIS--}"

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
