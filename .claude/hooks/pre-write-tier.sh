#!/bin/bash
# L6 ASSESS: dynamic tier classification before every Write/Edit.
# Frozen files → permissionDecision:deny (membrane protection).
# All others → additionalContext with tier + constitutional constraints.

set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# ── Frozen-file membrane check (T0_ABORT) ──────────────────────────────────
if echo "$FILE_PATH" | grep -qE "(python/(gate|dna|router)\.py)$"; then
  BASENAME=$(basename "$FILE_PATH")
  BASENAME="$BASENAME" python3 <<'PYEOF'
import json, os
bn = os.environ['BASENAME']
print(json.dumps({
  'systemMessage': f'T0_ABORT: {bn} is constitutionally frozen. Requires /guardian APPROVED.',
  'hookSpecificOutput': {
    'hookEventName': 'PreToolUse',
    'permissionDecision': 'deny',
    'permissionDecisionReason': (
      f'{bn} is a frozen constitutional file (SHA-256 anchored). '
      'Modification requires /guardian APPROVED. '
      'Run: cd sovereign-omega-v2 && node scripts/verify-hashes.mjs'
    )
  }
}))
PYEOF
  exit 0
fi

# ── Tier classification ─────────────────────────────────────────────────────
TIER="T2"
RULE="No T4/T5 in src/. Read before edit. Classify tier."

if echo "$FILE_PATH" | grep -qE "src/(core|event|gate)/.*\.ts$"; then
  TIER="T0"
  RULE="canonicalizeJCS only | No Date.now() except uuid.ts | No JSON.stringify for integrity | deepFreeze after construction | IndexedDBSequenceAllocator not array.length"
elif echo "$FILE_PATH" | grep -qE "src/(constitutional|consensus)/.*\.ts$"; then
  TIER="T1"
  RULE="certifyMartingale+assertMartingaleAnchored | BFT quorum at φ=0.6180339887 | Bernstein bounds not Hoeffding | No Set/Map in ProjectionState | arrays only"
elif echo "$FILE_PATH" | grep -qE "aegis-cl-psi/src/.*\.rs$"; then
  TIER="T2"
  RULE="BTreeMap/BTreeSet only (never HashMap) | to_be_bytes() always | saturating_add/mul | f64→value.to_bits().to_be_bytes() | verify_chain() required | GENESIS=[0u8;32]"
elif echo "$FILE_PATH" | grep -qE "aegis-runtime/src/.*\.rs$"; then
  TIER="T2"
  RULE="Seven-Pillar contract | BTreeMap only | StateAnchor+DomainFirewall+AffineCanvas+SemanticGraph+ValidationDFA+GossipEmitter+HysteresisFilter"
elif echo "$FILE_PATH" | grep -qE "sovereign-omega-v2/src/.*\.ts$"; then
  TIER="T2"
  RULE="No Set/Map in ProjectionState | .js imports | 150-line soft limit | deepFreeze state | version mismatch=hard abort"
elif echo "$FILE_PATH" | grep -qE "python/.*\.py$"; then
  TIER="T2"
  RULE="No time.time() in determinism paths | PGCS before TGCS | corruption_count must equal 0"
elif echo "$FILE_PATH" | grep -qE "\.(ts|tsx)$"; then
  TIER="T2"
  RULE="No hardcoded secrets | use .env | check @shared components before duplicating"
fi

TIER="$TIER" RULE="$RULE" python3 <<'PYEOF'
import json, os
tier = os.environ['TIER']
rule = os.environ['RULE']
ctx = (
    f'L6 PRE-WRITE ASSESS | Tier: {tier}\n'
    f'{rule}\n'
    'Protocol: ASSESS before LOCK | Read-before-Write enforced | No T4/T5 in src/'
)
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'additionalContext': ctx
    }
}))
PYEOF
exit 0
