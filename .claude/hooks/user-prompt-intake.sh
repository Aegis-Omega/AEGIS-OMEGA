#!/bin/bash
# UserPromptSubmit: L1-L7 state snapshot + epistemic bootstrap before each prompt.
# Lightweight: git status + observation-chain integrity only (no npm/cargo).

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

BRANCH=$(git -C "$REPO" branch --show-current 2>/dev/null || echo "?")
SRC_CHANGED=$(git -C "$REPO" diff --name-only 2>/dev/null | grep -cE "\.(ts|rs|py)$" | tr -d ' \n' || true)
STAGED=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
SRC_CHANGED="${SRC_CHANGED:-0}"

# Record a real observation, then certify chain integrity. The certificate establishes
# integrity of this recorded event chain only; it does not establish semantic truth,
# identity, consciousness, memory continuity, safety, or authority.
CHAIN_MJS="$REPO/.claude/metacog/chain.mjs"
CERT='{"is_valid":true,"entry_count":0,"terminal_hash":null,"broken_at":null}'
if [ -f "$CHAIN_MJS" ]; then
  node "$CHAIN_MJS" observe SENSATION T1 "prompt received | branch:$BRANCH | src-changed:$SRC_CHANGED" >/dev/null 2>&1 || true
  CERT=$(node "$CHAIN_MJS" certify 2>/dev/null || echo "$CERT")
fi

REPO="$REPO" BRANCH="$BRANCH" SRC_CHANGED="$SRC_CHANGED" STAGED="$STAGED" CERT="$CERT" python3 <<'PYEOF'
import json, os
from pathlib import Path

repo        = Path(os.environ['REPO'])
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

bootstrap_path = repo / '.claude/epistemic/bootstrap.md'
bootstrap = bootstrap_path.read_text(encoding='utf-8').strip() if bootstrap_path.is_file() else ''

ctx = (
    f'L1-L7 ACTIVE | branch:{branch} | src-changed:{src_changed} | staged:{staged}\n'
    f'ObservationChain(integrity-only): is_valid={str(valid).lower()} | entry-count={count} | '
    f'terminal:{term}{breach}\n'
    'L7:verify-hashes | L6:ASSESS→LOCK | L5:gate-seq | L4:lineage | L3:active-file | '
    'L2:test-pass≠correctness | L1:full-signal\n'
    'Claim-status-required: VERIFIED|DERIVED|ATTESTED|INFERRED|ASSUMED|NOT_CHECKED\n'
    'Non-equiv: test-pass≠correctness | auditability≠safety | governance≠alignment | '
    'chain-integrity≠truth | chain-integrity≠identity | chain-integrity≠consciousness | '
    'search-miss≠nonexistence'
)
if bootstrap:
    ctx += '\n\n--- REPO-LOCAL EPISTEMIC BOOTSTRAP ---\n' + bootstrap

print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': ctx
    }
}))
PYEOF
exit 0
