#!/bin/bash
# UserPromptSubmit: repository-cognition admission + L1-L7 metacognitive snapshot.
# This is the blocking boundary available in Claude Code before each user prompt.

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Repository existence/content claims must be bound to a complete current Git
# source corpus. UserPromptSubmit supports a real blocking decision, unlike
# SessionStart/PostCompact. Fail before the prompt reaches the model.
COGNITION_OUT=$(python3 "$REPO/scripts/repo_cognition.py" --check --receipt 2>&1)
COGNITION_RC=$?
if [ "$COGNITION_RC" -ne 0 ]; then
  COGNITION_OUT="$COGNITION_OUT" python3 <<'PYEOF'
import json, os
reason = os.environ.get('COGNITION_OUT', 'repository cognition check failed')
print(json.dumps({
    'decision': 'block',
    'reason': 'REPOSITORY_KNOWLEDGE_INCOMPLETE — refresh the content-addressed repository corpus before continuing.',
    'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': reason[:4000]
    }
}))
PYEOF
  exit 0
fi

COGNITION_RECEIPT=$(printf '%s\n' "$COGNITION_OUT" | grep '^{' | tail -1)
BRANCH=$(git -C "$REPO" branch --show-current 2>/dev/null || echo "?")
SRC_CHANGED=$(git -C "$REPO" diff --name-only 2>/dev/null | grep -cE "\.(ts|rs|py)$" | tr -d ' \n' || true)
STAGED=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
SRC_CHANGED="${SRC_CHANGED:-0}"

# Enact metacognition: append a SENSATION observation, then certify the chain.
# Integrity failure is evidence of unavailable/invalid metacognitive state; it
# must never be silently rewritten to is_valid=true.
CHAIN_MJS="$REPO/.claude/metacog/chain.mjs"
CERT='{"is_valid":false,"entry_count":0,"terminal_hash":null,"broken_at":"UNAVAILABLE"}'
MC_STATUS="UNAVAILABLE"
if [ -f "$CHAIN_MJS" ]; then
  if node "$CHAIN_MJS" observe SENSATION T1 "prompt received | branch:$BRANCH | src-changed:$SRC_CHANGED" >/dev/null 2>&1; then
    MC_STATUS="OBSERVED"
    CERT_OUT=$(node "$CHAIN_MJS" certify 2>/dev/null)
    CERT_RC=$?
    if [ "$CERT_RC" -eq 0 ] && [ -n "$CERT_OUT" ]; then
      CERT="$CERT_OUT"
      MC_STATUS="CERTIFIED"
    else
      MC_STATUS="CERTIFICATION_FAILED"
    fi
  else
    MC_STATUS="OBSERVATION_FAILED"
  fi
else
  MC_STATUS="CHAIN_MISSING"
fi

BRANCH="$BRANCH" SRC_CHANGED="$SRC_CHANGED" STAGED="$STAGED" CERT="$CERT" \
MC_STATUS="$MC_STATUS" COGNITION_RECEIPT="$COGNITION_RECEIPT" python3 <<'PYEOF'
import json, os

branch = os.environ['BRANCH']
src_changed = os.environ['SRC_CHANGED']
staged = os.environ['STAGED']
mc_status = os.environ['MC_STATUS']
repo_receipt = os.environ.get('COGNITION_RECEIPT', '')

try:
    cert = json.loads(os.environ['CERT'])
except Exception:
    cert = {
        'is_valid': False,
        'entry_count': 0,
        'terminal_hash': None,
        'broken_at': 'CERT_JSON_INVALID',
    }
    mc_status = 'CERT_JSON_INVALID'

valid = cert.get('is_valid') is True
count = cert.get('entry_count', 0)
term = (cert.get('terminal_hash') or '—')[:12]
broken_at = cert.get('broken_at')
mc_label = 'VERIFIED' if valid and mc_status == 'CERTIFIED' else 'UNVERIFIED'
warning = '' if mc_label == 'VERIFIED' else f' | warning={mc_status}:{broken_at}'

ctx = (
    f'REPOSITORY COGNITION VERIFIED | {repo_receipt}\n'
    f'L1-L7 STATE | branch:{branch} | src-changed:{src_changed} | staged:{staged}\n'
    f'MetacognitiveLoop: status={mc_label} | is_valid={str(valid).lower()} | '
    f'temporal-mass={count} obs | terminal:{term}{warning}\n'
    'Do not promote metacognitive-chain availability/integrity into proposition truth. '
    'Do not claim repository-global absence without the verified corpus.\n'
    'Non-equiv: test-pass≠correctness | auditability≠safety | '
    'metacognition≠safety | governance≠alignment'
)
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': ctx
    }
}))
PYEOF
exit 0
