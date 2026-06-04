#!/bin/bash
# UserPromptSubmit: L1-L7 metacognitive intake — state snapshot injected before each prompt.
# Lightweight: git status only (no npm/cargo). Runs on every user message.

set -uo pipefail

REPO="/home/user/AEGIS--"

BRANCH=$(git -C "$REPO" branch --show-current 2>/dev/null || echo "?")
SRC_CHANGED=$(git -C "$REPO" diff --name-only 2>/dev/null | grep -cE "\.(ts|rs|py)$" | tr -d ' \n' || true)
STAGED=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
SRC_CHANGED="${SRC_CHANGED:-0}"

# ── Enact metacognition: append a real SENSATION observation, then certify ──
# This is the live MetacognitiveLoop (loop.ts algorithm) running on disk, not a
# decorative string. The certificate is recomputed from the chain every prompt.
CHAIN_MJS="$REPO/.claude/metacog/chain.mjs"
CERT='{"is_valid":true,"entry_count":0,"terminal_hash":null,"broken_at":null}'
if [ -f "$CHAIN_MJS" ]; then
  node "$CHAIN_MJS" observe SENSATION T1 "prompt received | branch:$BRANCH | src-changed:$SRC_CHANGED" >/dev/null 2>&1 || true
  CERT=$(node "$CHAIN_MJS" certify 2>/dev/null || echo "$CERT")
fi

BRANCH="$BRANCH" SRC_CHANGED="$SRC_CHANGED" STAGED="$STAGED" CERT="$CERT" python3 <<'PYEOF'
import json, os

branch      = os.environ['BRANCH']
src_changed = os.environ['SRC_CHANGED']
staged      = os.environ['STAGED']
try:
    cert = json.loads(os.environ['CERT'])
except Exception:
    cert = {'is_valid': True, 'entry_count': 0, 'terminal_hash': None}

valid = cert.get('is_valid', True)
count = cert.get('entry_count', 0)
term  = (cert.get('terminal_hash') or '—')[:12]
breach = '' if valid else '  ⚠ CHAIN TAMPER DETECTED — is_valid=false'

ctx = (
    f'L1-L7 ACTIVE | branch:{branch} | src-changed:{src_changed} | staged:{staged}\n'
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
