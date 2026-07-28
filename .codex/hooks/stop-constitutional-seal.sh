#!/bin/bash
# asyncRewake Stop hook: constitutional seal on every session end.
# Always runs: L7 hash verify (fast, ~0.5s).
# Conditionally runs: typecheck if TypeScript src files changed.
# Exits 2 (rewake model) on failure only — silent on green.

set -uo pipefail

REPO="/home/user/AEGIS--"

# L7: frozen-file membrane verify (always — fast)
HASH_OUT=$(cd "$REPO/sovereign-omega-v2" && node scripts/verify-hashes.mjs 2>&1 | tail -5)
HASH_EXIT=$?

if [ "$HASH_EXIT" -ne 0 ]; then
  cat <<MSG
STOP SEAL: L7 MEMBRANE BREACH — frozen constitutional file modified!
$HASH_OUT
Restore: git checkout sovereign-omega-v2/python/gate.py dna.py router.py
MSG
  exit 2
fi

# Conditional: typecheck only if TypeScript source was changed
TS_CHANGED=$(git -C "$REPO" diff --name-only 2>/dev/null | grep -cE "sovereign-omega-v2/src/.*\.ts$" || true)
STAGED_TS=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | grep -cE "sovereign-omega-v2/src/.*\.ts$" || true)
TOTAL_TS=$(( ${TS_CHANGED:-0} + ${STAGED_TS:-0} ))

if [ "$TOTAL_TS" -gt 0 ]; then
  TC_OUT=$(cd "$REPO/sovereign-omega-v2" && npm run typecheck 2>&1 | tail -8)
  if echo "$TC_OUT" | grep -qE "error TS|Found [0-9]+ error"; then
    cat <<MSG
STOP SEAL: typecheck FAILED on uncommitted TypeScript changes.
Fix before committing — Gate 8 will also fail.
$TC_OUT
MSG
    exit 2
  fi
fi

# ── Enact operational closure: observe the turn boundary in the live chain ──
# Stop fires on every turn-end, so this records a lightweight AUTOPOIETIC_CLOSURE
# observation into the gitignored live chain (no tracked-file churn). The durable
# cross-session seal is a DELIBERATE act — `node .claude/metacog/chain.mjs seal`,
# invoked by the evening-seal ritual or when the operator wraps a session — so
# seals.jsonl grows once per real session, not once per turn.
CHAIN_MJS="$REPO/.claude/metacog/chain.mjs"
if [ -f "$CHAIN_MJS" ]; then
  node "$CHAIN_MJS" observe AUTOPOIETIC_CLOSURE T2 "turn boundary | t0_verdict=true" >/dev/null 2>&1 || true
fi

# All clear — exit 0 (silent success, no rewake)
exit 0
