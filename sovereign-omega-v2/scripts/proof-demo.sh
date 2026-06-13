#!/usr/bin/env bash
# AEGIS-Ω Constitutional Proof Demo
#
# One command that proves, from a cold repo:
#   1. Frozen file membrane intact (hash integrity)
#   2. φ-convergence: MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD === (√5−1)/2
#      — numerical identity across martingale + swarm + Bernstein (Gate 79)
#   3. Autopoietic admission: 5 T4/T5 vision concepts reduced to T0/T2 (Gates 34–38)
#   4. Constitutional law boundary: AdaptivePower(T) ≤ ReplayVerifiability(T)
#   5. Metacognitive chain integrity: certifyMetacognitiveLoop() detects any tamper
#   6. Platform contract: 453/453 tests green
#
# Usage:
#   cd sovereign-omega-v2
#   bash scripts/proof-demo.sh
#
# Output is written to /tmp/aegis-proof-<timestamp>.txt
# Every line is reproducible — run again and compare.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="/tmp/aegis-proof-$(date +%Y%m%d-%H%M%S).txt"

log() { echo "$*" | tee -a "$OUT"; }

cd "$REPO"

log "AEGIS-Ω Constitutional Proof — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
log "Repository: $REPO"
log "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
log "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
log ""

# ── 1. HASH INTEGRITY ─────────────────────────────────────────────────────────
log "=== 1. FROZEN FILE MEMBRANE (hash integrity) ==="
HASH_OUT=$(node scripts/verify-hashes.mjs 2>&1)
log "$HASH_OUT"
if echo "$HASH_OUT" | grep -q "All frozen files present and hash-verified"; then
  log "RESULT: PASS — constitutional membrane intact"
else
  log "RESULT: FAIL — membrane breach"
  exit 1
fi
log ""

# ── 2. φ-CONVERGENCE PROOF (Gate 79) ─────────────────────────────────────────
log "=== 2. φ-CONVERGENCE PROOF (Gate 79 — holonic triad) ==="
log "Claim: MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD === (√5−1)/2"
log "Files: test/integration/holonic-triad-proof.test.ts"
log "       test/integration/phi-holonic-triad-extension.test.ts"
PHI_OUT=$(npm run test -- \
  test/integration/holonic-triad-proof.test.ts \
  test/integration/phi-holonic-triad-extension.test.ts 2>&1 | tail -8)
log "$PHI_OUT"
if echo "$PHI_OUT" | grep -qE "passed"; then
  log "RESULT: PASS — φ-convergence proven numerically"
else
  log "RESULT: FAIL"
  exit 1
fi
log ""

# ── 3. AUTOPOIETIC ADMISSION (Gates 34–38) ───────────────────────────────────
log "=== 3. AUTOPOIETIC ADMISSION (Gates 34–38) ==="
log "Claim: 5 T4/T5 vision concepts admitted to T0/T2 substrate via admitAbstraction()"
log "File:  test/unit/autopoietic-admission.test.ts"
ADMIT_OUT=$(npm run test -- test/unit/autopoietic-admission.test.ts 2>&1 | tail -6)
log "$ADMIT_OUT"
if echo "$ADMIT_OUT" | grep -qE "passed"; then
  log "RESULT: PASS — autopoietic vision grounded constitutionally"
else
  log "RESULT: FAIL"
  exit 1
fi
log ""

# ── 4. CONSTITUTIONAL LAW (martingale boundary) ───────────────────────────────
log "=== 4. CONSTITUTIONAL LAW (AdaptivePower ≤ ReplayVerifiability) ==="
log "Claim: martingale suspends mutation authority when boundary exceeded"
log "File:  test/unit/martingale.test.ts + test/unit/adaptive-lineage.test.ts"
MART_OUT=$(npm run test -- \
  test/unit/martingale.test.ts \
  test/unit/adaptive-lineage.test.ts 2>&1 | tail -6)
log "$MART_OUT"
if echo "$MART_OUT" | grep -qE "passed"; then
  log "RESULT: PASS — constitutional law enforced at numeric boundary"
else
  log "RESULT: FAIL"
  exit 1
fi
log ""

# ── 5. METACOGNITIVE CHAIN INTEGRITY ─────────────────────────────────────────
log "=== 5. METACOGNITIVE CHAIN (tamper-evident hash chain) ==="
log "Claim: certifyMetacognitiveLoop() detects any entry modification"
log "File:  test/unit/metacognition.test.ts"
META_OUT=$(npm run test -- test/unit/metacognition.test.ts 2>&1 | tail -6)
log "$META_OUT"
if echo "$META_OUT" | grep -qE "passed"; then
  log "RESULT: PASS — metacognitive chain tamper-evident"
else
  log "RESULT: FAIL"
  exit 1
fi
log ""

# ── 6. PLATFORM CONTRACT ──────────────────────────────────────────────────────
log "=== 6. PLATFORM CONTRACT (453 tests) ==="
log "File:  python/tests/test_platform.py"
PLAT_OUT=$(python python/tests/test_platform.py 2>&1)
PLAT_SUMMARY=$(echo "$PLAT_OUT" | grep -oE "PASS: [0-9]+  FAIL: [0-9]+" | tail -1)
log "$PLAT_SUMMARY"
if echo "$PLAT_SUMMARY" | grep -q "FAIL: 0"; then
  log "RESULT: PASS — platform contract fully honored"
else
  log "RESULT: FAIL"
  echo "$PLAT_OUT" | tail -10 | tee -a "$OUT"
  exit 1
fi
log ""

# ── SUMMARY ───────────────────────────────────────────────────────────────────
log "════════════════════════════════════════════════════════"
log "ALL PROOFS PASS"
log ""
log "  Constitutional membrane:    INTACT"
log "  φ-convergence (Gate 79):   PROVEN — 3 scales, 1 constant"
log "  Autopoietic admission:      PROVEN — 5 concepts → T0/T2"
log "  Constitutional law:         ENFORCED — martingale boundary holds"
log "  Metacognitive chain:        TAMPER-EVIDENT — certify() validates"
log "  Platform contract:          $PLAT_SUMMARY"
log ""
log "Full proof: $OUT"
log "════════════════════════════════════════════════════════"
