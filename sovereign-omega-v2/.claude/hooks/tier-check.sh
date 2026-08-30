#!/bin/bash
# ============================================================
# SOVEREIGN OMEGA — Epistemic Tier Boundary Check Hook
# Triggered: PostToolUse on Write operations
# Warns when T4/T5 vocabulary appears in T0-T2 files
# ============================================================

FILEPATH="$1"

# Only check implementation source files
if [[ "$FILEPATH" != src/* && "$FILEPATH" != test/* ]]; then
  exit 0
fi

# T4/T5 vocabulary that must not appear in implementation code
T4_TERMS=(
  "planetary"
  "civilisational"
  "metamaterial"
  "consciousness"
  "multiverse"
  "PNAS"
  "thermodynamic liquefaction"
  "ego dissolution"
  "morphogenesis"
  "axiomatic arbitration"
  "quantum reality"
)

if [ ! -f "$FILEPATH" ]; then
  exit 0
fi

for term in "${T4_TERMS[@]}"; do
  if grep -qi "$term" "$FILEPATH" 2>/dev/null; then
    echo "TIER WARNING: '$term' (T4/T5 vocabulary) detected in $FILEPATH"
    echo "This term may represent epistemic tier contamination."
    echo "Review against the T0-T5 taxonomy before proceeding."
  fi
done

exit 0
