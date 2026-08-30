#!/bin/bash
# ============================================================
# SOVEREIGN OMEGA — Frozen File Write Protection Hook
# Triggered: PreToolUse on Write operations
# Blocks writes to constitutional frozen files
# ============================================================

FILEPATH="$1"

FROZEN_FILES=(
  "gate.py"
  "dna.py"
  "router.py"
  "docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md"
  "ARTIFACT_REGISTRY.md"
)

for frozen in "${FROZEN_FILES[@]}"; do
  if [[ "$FILEPATH" == *"$frozen"* ]]; then
    echo "FROZEN FILE PROTECTION: $frozen is a constitutional file."
    echo "Modification requires /guardian APPROVED verdict."
    echo "This write has been blocked."
    exit 1
  fi
done

exit 0
