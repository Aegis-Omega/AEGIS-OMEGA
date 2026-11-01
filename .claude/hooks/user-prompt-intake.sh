#!/bin/bash
# UserPromptSubmit: L1-L7 metacognitive intake — state snapshot injected before each prompt.
# Lightweight: git status only (no npm/cargo). Runs on every user message.

set -euo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

BRANCH=$(git -C "$REPO" branch --show-current 2>/dev/null || echo "?")
SRC_CHANGED=$(git -C "$REPO" diff --name-only 2>/dev/null | grep -cE "\.(ts|rs|py)$" | tr -d ' \n' || true)
STAGED=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
SRC_CHANGED="${SRC_CHANGED:-0}"

# ── Enact metacognition: append a real SENSATION observation, then certify ──
# This is the live MetacognitiveLoop (loop.ts algorithm) running on disk, not a
# decorative string. The certificate is recomputed from the chain every prompt.
CHAIN_MJS="$REPO/.claude/metacog/chain.mjs"
if [ ! -f "$CHAIN_MJS" ]; then
  echo 'AEGIS_HOLD_NO_ADMISSION: metacognitive chain engine missing' >&2
  exit 2
fi
if ! node "$CHAIN_MJS" observe SENSATION T1 "prompt received | branch:$BRANCH | src-changed:$SRC_CHANGED" >/dev/null; then
  echo 'AEGIS_HOLD_NO_ADMISSION: metacognitive observation failed' >&2
  exit 2
fi
if ! CERT=$(node "$CHAIN_MJS" certify); then
  echo 'AEGIS_HOLD_NO_ADMISSION: metacognitive certification could not execute' >&2
  exit 2
fi

BRANCH="$BRANCH" SRC_CHANGED="$SRC_CHANGED" STAGED="$STAGED" CERT="$CERT" python3 <<'PYEOF'
import json, os, re, sys

branch      = os.environ['BRANCH']
src_changed = os.environ['SRC_CHANGED']
staged      = os.environ['STAGED']
try:
    cert = json.loads(os.environ['CERT'])
except (ValueError, TypeError):
    print('AEGIS_HOLD_NO_ADMISSION: malformed chain certificate', file=sys.stderr)
    sys.exit(2)

valid = cert.get('is_valid') is True if isinstance(cert, dict) else False
count = cert.get('entry_count') if isinstance(cert, dict) else None
terminal = cert.get('terminal_hash') if isinstance(cert, dict) else None
if (not valid or type(count) is not int or count < 1 or
    not isinstance(terminal, str) or not re.fullmatch(r'[a-f0-9]{64}', terminal) or
    cert.get('broken_at') is not None):
    print('AEGIS_HOLD_NO_ADMISSION: invalid or missing chain integrity', file=sys.stderr)
    sys.exit(2)
term = terminal[:12]
breach = '' 
ctx = (
    f'L1-L7 OBSERVATION VERIFIED | branch:{branch} | src-changed:{src_changed} | staged:{staged}\n'
    f'MetacognitiveLoop(live): is_valid={str(valid).lower()} | temporal-mass={count} obs | '
    f'terminal:{term}{breach}\n'
    'L7:verify-hashes | L6:ASSESS→LOCK | L5:gate-seq | L4:lineage | L3:active-file | '
    'L2:test-pass≠correctness | L1:full-signal\n'
    'Non-equiv: test-pass≠correctness | auditability≠safety | metacognition≠safety | governance≠alignment'
)
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': ctx
    }
}))
PYEOF
exit 0
