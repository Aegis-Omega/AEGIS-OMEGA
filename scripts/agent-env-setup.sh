#!/usr/bin/env bash
# Portable environment setup for any agent host (Claude Code cloud, Codex, local).
#
# Finds the repository itself instead of trusting a hard-coded path: the
# Claude Code cloud checks out to /home/user/AEGIS-OMEGA, Codex to
# /workspace/AEGIS-OMEGA, a laptop anywhere. Idempotent, and it never fails
# the session: a missing tool or a failed install is reported and skipped.
#
# Paste this one line as the setup script of every environment (Claude Code
# environment settings -> Setup script, Codex environment -> Setup script):
#
#   for d in "${CLAUDE_PROJECT_DIR:-}" "$PWD" /home/user/AEGIS-OMEGA /workspace/AEGIS-OMEGA "$HOME/AEGIS-OMEGA"; do [ -f "$d/scripts/agent-env-setup.sh" ] && exec bash "$d/scripts/agent-env-setup.sh" "$d"; done; echo "agent-env-setup: repository not found, skipping"; exit 0
#
# Usage: bash scripts/agent-env-setup.sh [repo-root]
# No secrets here: API keys belong in the environment's own variables.
set -u

log() { echo "agent-env-setup: $*"; }

REPO="${1:-}"
if [ -z "$REPO" ] || [ ! -d "$REPO/.git" ]; then
  REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)"
fi
if [ ! -d "$REPO/.git" ]; then
  log "no git repository at $REPO, skipping"
  exit 0
fi
log "repository: $REPO"

if command -v npm >/dev/null 2>&1; then
  # Same order as .claude/hooks/session-start.sh (shared package first).
  for dir in packages/shared sovereign-omega-v2 hub platform-picker hook-generator \
             content-calendar cockpit studio enterprise aegisomega-webgpu; do
    if [ -f "$REPO/$dir/package.json" ] && [ ! -d "$REPO/$dir/node_modules" ]; then
      log "npm install $dir"
      npm install --prefix "$REPO/$dir" --prefer-offline --no-audit --no-fund --silent \
        || log "npm install failed in $dir (continuing)"
    fi
  done
else
  log "npm not found, skipping JavaScript dependencies"
fi

PY="$(command -v python3 || command -v python || true)"
REQ="$REPO/sovereign-omega-v2/python/requirements.txt"
if [ -n "$PY" ] && [ -f "$REQ" ]; then
  if ! "$PY" -c "import anthropic" >/dev/null 2>&1; then
    log "pip install sovereign-omega-v2/python/requirements.txt"
    "$PY" -m pip install --quiet -r "$REQ" || log "pip install failed (continuing)"
  fi
  if [ -f "$REPO/packages/aegis-py/pyproject.toml" ] && ! "$PY" -c "import aegis" >/dev/null 2>&1; then
    "$PY" -m pip install --quiet -e "$REPO/packages/aegis-py" || log "aegis-py install failed (continuing)"
  fi
else
  log "python or requirements.txt not found, skipping Python dependencies"
fi

log "done"
exit 0
