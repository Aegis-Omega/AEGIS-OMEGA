#!/bin/bash
# Pre-commit Gate 8 auto-block.
# Gate sequence: Gate 1 (jcs.test.ts) → typecheck → build.
# Reads git commit command from stdin — exits 0 for non-commit Bash calls.

set -uo pipefail

# Self-locate the repo: hooks live at $REPO/.claude/hooks/. Never hardcode the
# container path — a moved/recloned repo silently no-ops every gate below.
REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

INPUT=$(cat)
# PreToolUse carries Bash arguments inside tool_input, not at the top level.
# Malformed hook input must never silently bypass a mutation gate.
if ! MODE=$(printf '%s' "$INPUT" | python3 -c '
import json, re, sys
try:
    event = json.load(sys.stdin)
    command = event["tool_input"]["command"]
    if not isinstance(command, str):
        raise ValueError("missing Bash command")
except (ValueError, TypeError, KeyError, AttributeError):
    sys.exit(2)
git_commit = re.search(
    r"(?<![A-Za-z0-9_.-])git(?:\s+(?:-C|--git-dir|--work-tree|--namespace|-c)\s+\S+|\s+--(?:git-dir|work-tree|namespace)=\S+)*\s+commit(?=\s|$|[;&|])",
    command,
    re.IGNORECASE,
)
print("COMMIT" if git_commit else "OTHER")
' 2>/dev/null); then
  echo "BLOCKED: missing or malformed PreToolUse Bash command" >&2
  exit 2
fi

if [[ "$MODE" != "COMMIT" ]]; then
  exit 0
fi

# ── Martingale suspension gate (constitutional) ────────────────────────────
# Mutation authority is withdrawn if the metacog/ratification chains are tampered
# (!is_anchored) or adaptation outran 1/φ of self-observation (entropy unbounded).
# A suspended automaton may not commit — AdaptivePower(T) ≤ ReplayVerifiability(T).
MART="$REPO/.claude/metacog/martingale.mjs"
if [ -f "$MART" ]; then
  if ! MART_OUT=$(node "$MART" gate 2>&1); then
    echo "BLOCKED: martingale suspended — mutation authority withdrawn."
    echo "$MART_OUT"
    echo "Restore: re-anchor the chains (fix tamper) or dilute adaptation with verified observation."
    exit 2
  fi
  echo "  martingale: anchored"
fi

# ── Replay-verification gate (constitutional) ──────────────────────────────
# REPLAY SOVEREIGNTY: replay(genesis, events) must reproduce the chain's topology
# hash, byte-identical across runs. A chain that does not replay deterministically
# may not commit — topology non-determinism is a T0_ABORT condition.
REPLAY="$REPO/.claude/metacog/replay.mjs"
if [ -f "$REPLAY" ]; then
  if ! REPLAY_OUT=$(node "$REPLAY" gate 2>&1); then
    echo "BLOCKED: replay divergence — the chain does not replay from genesis."
    echo "$REPLAY_OUT"
    exit 2
  fi
  echo "  replay: verified"
fi

# ── Agent-mesh verdict ledger integrity gate ───────────────────────────────
# The Guardian→Verifier→Implementer triad records every verdict in a hash-
# chained ledger. A broken ledger means a verdict was retroactively altered —
# a constitutional breach. The automaton may not commit with a tampered
# verdict record.
MESH="$REPO/.claude/metacog/agent-mesh.mjs"
if [ -f "$MESH" ]; then
  if ! MESH_OUT=$(node "$MESH" gate 2>&1); then
    echo "BLOCKED: agent-mesh verdict ledger tampered — constitutional breach."
    echo "$MESH_OUT"
    exit 2
  fi
  echo "  agent-mesh: $MESH_OUT"
fi

echo "GATE 8 pre-commit: Gate1 → typecheck → build..."
cd "$REPO/sovereign-omega-v2" || { echo "BLOCKED: $REPO/sovereign-omega-v2 not found — Gate 8 cannot run."; exit 2; }

# Gate 1: T0 canonicalization foundation
if ! GATE1=$(npm run test -- test/unit/jcs.test.ts 2>&1); then
  echo "BLOCKED: Gate 1 (jcs.test.ts) failed (nonzero process exit)." >&2
  printf '%s\n' "$GATE1" | tail -6 >&2
  exit 2
fi
echo "  Gate 1 (jcs): OK"

# Typecheck: trust the command exit status, not matching log text.
if ! TYPECHECK=$(npm run typecheck 2>&1); then
  echo "BLOCKED: typecheck failed (nonzero process exit)." >&2
  printf '%s\n' "$TYPECHECK" | tail -8 >&2
  exit 2
fi
echo "  typecheck: OK"

# Build: fail closed even when the last log lines contain no word "error".
if ! BUILD=$(npm run build 2>&1); then
  echo "BLOCKED: build failed (nonzero process exit)." >&2
  printf '%s\n' "$BUILD" | tail -8 >&2
  exit 2
fi
echo "  build: OK"

# ── Python platform-contract gate ──────────────────────────────────────────
# The /platform/* API is the surface external callers (SDK, CLI, Sheets) hit.
# Its contract suite (test_platform.py, ~64ms) lives outside Gate 8's TS scope,
# so a regression here once committed silently (649b6138 → 450/3). Block on it:
# a red platform contract may not enter the branch. Exit 1 from the suite = fail.
PLAT="python/tests/test_platform.py"
if [[ ! -f "$PLAT" ]]; then
  echo "BLOCKED: required platform contract test missing: $PLAT" >&2
  exit 2
fi
if [ -f "$PLAT" ]; then
  if ! PLAT_OUT=$(python python/tests/test_platform.py 2>&1); then
    echo "BLOCKED: platform contract regression — test_platform.py failed."
    echo "$PLAT_OUT" | tail -8
    exit 2
  fi
  echo "  platform contract: $(echo "$PLAT_OUT" | grep -oE 'PASS: [0-9]+  FAIL: [0-9]+' | tail -1)"
fi

echo "Gate 8 passed — commit proceeding."
exit 0
