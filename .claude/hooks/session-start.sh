#!/bin/bash
# Session-start dependency installer + repository-universe hydration for Claude Code on the web.
# Idempotent where possible; universe hydration is evidence-critical and refreshes refs/history.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo '{"async": true, "asyncTimeout": 300000}'

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Hydrate complete Git history and every reachable branch/tag before Claude forms
# repository-wide beliefs. main is canonical admission state, not the universe.
UNIVERSE="$REPO/.aegis/runtime/repo-universe.json"
if [ -x "$REPO/scripts/repo-universe.sh" ] || [ -f "$REPO/scripts/repo-universe.sh" ]; then
  echo "SessionStart: hydrating complete repository universe..."
  if bash "$REPO/scripts/repo-universe.sh" \
      --repo "$REPO" \
      --main origin/main \
      --refresh \
      --json "$UNIVERSE"; then
    python3 - "$UNIVERSE" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding='utf-8'))
print(
    "REPOSITORY_UNIVERSE_ACTIVE | "
    f"history_complete={str(p['history_complete']).lower()} | "
    f"branches={p['branch_count']} | "
    f"all_ref_commits={p['all_ref_commit_count']} | "
    f"main_commits={p['main_reachable_commit_count']} | "
    f"off_main_unique_commits={p['commits_not_reachable_from_main']} | "
    f"main={p['main_sha']}"
)
print(
    "EPISTEMIC_RULE: canonical main = admitted state; all fetched refs = searchable artifact universe. "
    "Never infer global absence from the current checkout or main alone."
)
PY
  else
    echo "REPOSITORY_UNIVERSE_INCOMPLETE: full-history/ref hydration failed; global absence claims are forbidden."
  fi
fi

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

# Ground truth — open every session knowing branch / main-drift / unpushed / membrane / live.
# Per WORKFLOW.md: no session starts blind; nothing is "done" until it is on main.
bash "$REPO/scripts/ground-truth.sh" 2>/dev/null || true
