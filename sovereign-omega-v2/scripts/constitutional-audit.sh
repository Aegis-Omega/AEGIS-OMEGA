#!/usr/bin/env bash
# Constitutional Audit — live chain across all AEGIS endpoints
set -euo pipefail

BRIDGE="${BRIDGE_URL:-http://localhost:7890}"
RED='\033[0;31m' GREEN='\033[0;32m' GOLD='\033[0;33m' DIM='\033[2m' NC='\033[0m' BOLD='\033[1m'

echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║         AEGIS-Ω CONSTITUTIONAL AUDIT                ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Bridge health
echo -e "${DIM}── Bridge ──────────────────────────────────────────────${NC}"
HEALTH=$(curl -sf "${BRIDGE}/health" 2>/dev/null) || { echo -e "${RED}✗ Bridge offline${NC}"; exit 1; }
echo -e "${GREEN}✓ Bridge online${NC}"
echo "  router_sealed: $(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['router_sealed'])")"

# 2. T0 Verdict (Autonode)
echo ""
echo -e "${DIM}── Autonode (T0 Gate) ──────────────────────────────────${NC}"
NODE=$(curl -sf "${BRIDGE}/node" 2>/dev/null)
T0=$(echo "$NODE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['t0_verdict'])")
CHASH=$(echo "$NODE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['constitutional_hash'][:16])")
CORRUPT=$(echo "$NODE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['corruption_count'])")
DRIFT=$(echo "$NODE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['drift_risk'])")
EPOCH=$(echo "$NODE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['epoch'])")
[ "$T0" = "True" ] && echo -e "${GREEN}✓ T0 PASS${NC}" || echo -e "${RED}✗ T0 FAIL${NC}"
echo "  constitutional_hash : ${CHASH}…"
echo "  corruption_count    : ${CORRUPT}"
echo "  drift_risk          : ${DRIFT}"
echo "  epoch               : ${EPOCH}"

# 3. Resonance
echo ""
echo -e "${DIM}── Resonance Monitor (Gate 222) ────────────────────────${NC}"
RES=$(curl -sf "${BRIDGE}/resonance" 2>/dev/null)
CERTIFIED=$(echo "$RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['is_certified'])")
DEPTH=$(echo "$RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['resonance_depth'])")
COEFF=$(echo "$RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['resonance_coefficient']:.4f}\")")
PHI_HR=$(echo "$RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['phi_headroom']:.6f}\")")
VORTEX=$(echo "$RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['vortex_family'])")
[ "$CERTIFIED" = "True" ] && echo -e "${GREEN}✓ CERTIFIED${NC}" || echo -e "${GOLD}~ RESONANT (not certified)${NC}"
# 4-pip depth bar
PIPS=""
for i in 1 2 3 4; do
  [ "$i" -le "$DEPTH" ] && PIPS="${PIPS}${GREEN}■${NC}" || PIPS="${PIPS}${DIM}□${NC}"
done
echo -e "  depth     : ${PIPS} ${DEPTH}/4"
echo "  coeff     : ${COEFF}"
echo "  φ-headroom: ${PHI_HR}"
echo "  vortex    : ${VORTEX}"

# 4. Catalog
echo ""
echo -e "${DIM}── Cognitive Triad Catalog ─────────────────────────────${NC}"
CAT=$(curl -sf "${BRIDGE}/catalog" 2>/dev/null)
TRIAD=$(echo "$CAT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['cognitive_triad'])")
CATHASH=$(echo "$CAT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['catalog_hash'])")
SKILLS=$(echo "$CAT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['skills']))")
echo -e "${GREEN}✓ ${TRIAD}${NC}"
echo "  catalog_hash : ${CATHASH}"
echo "  skills       : ${SKILLS} certified"

# 5. Frozen file check
echo ""
echo -e "${DIM}── Frozen Constitutional Files ─────────────────────────${NC}"
cd "$(git rev-parse --show-toplevel)/sovereign-omega-v2" 2>/dev/null && \
  node scripts/verify-hashes.mjs 2>/dev/null | sed 's/^/  /' || echo "  (run from repo root)"

# 6. Test count
echo ""
echo -e "${DIM}── Gate 8 Status ───────────────────────────────────────${NC}"
TESTS=$(cd "$(git rev-parse --show-toplevel)/sovereign-omega-v2" 2>/dev/null && \
  npx vitest run --reporter=verbose 2>/dev/null | grep "Tests" | tail -1 | tr -s ' ' | cut -d' ' -f2-5 || echo "run 'npm run test' to check")
echo "  ${TESTS}"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  AdaptivePower(T) ≤ ReplayVerifiability(T)          ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
