#!/bin/bash
# Post-write constitutional auto-verification hook.
# Fires after every Write or Edit tool call.
# Routes to the appropriate verification based on the file written.
# Autopoietic property: Viability Ring auto-assertion after every production event.

set -euo pipefail

REPO="${CLAUDE_PROJECT_DIR:-/home/user/AEGIS--}"

# Read the file path from stdin JSON
FILE_PATH=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Normalize to absolute path
if [[ "$FILE_PATH" != /* ]]; then
  FILE_PATH="$REPO/$FILE_PATH"
fi

# ── Enact autopoiesis: record the self-production event in the metacog chain ──
# Every Write/Edit is a component the system produced of itself; the chain is
# the membrane inventory. Tier T2 (engineering production); failures are silent.
CHAIN_MJS="$REPO/.claude/metacog/chain.mjs"
if [ -f "$CHAIN_MJS" ]; then
  REL="${FILE_PATH#$REPO/}"
  node "$CHAIN_MJS" observe AUTOPOIETIC_PRODUCTION T2 "produced: $REL" >/dev/null 2>&1 || true
fi

# --- Frozen file check (membrane breach detection) ---
FROZEN_FILES=(
  "$REPO/sovereign-omega-v2/python/gate.py"
  "$REPO/sovereign-omega-v2/python/dna.py"
  "$REPO/sovereign-omega-v2/python/router.py"
)
for FROZEN in "${FROZEN_FILES[@]}"; do
  if [ "$FILE_PATH" = "$FROZEN" ]; then
    echo "MEMBRANE BREACH: $FILE_PATH is a frozen constitutional file."
    echo "Running verify-hashes.mjs to detect damage..."
    cd "$REPO/sovereign-omega-v2"
    node scripts/verify-hashes.mjs
    exit 0
  fi
done

# --- Rust gate module auto-test (viability ring verification) ---
if [[ "$FILE_PATH" == "$REPO/aegis-cl-psi/src/"*.rs ]] && [[ "$FILE_PATH" != *"lib.rs" ]]; then
  MODULE=$(basename "$FILE_PATH" .rs)
  echo "AUTO-GATE: $MODULE written — running cargo test $MODULE"
  cd "$REPO/aegis-cl-psi"
  cargo test "$MODULE" 2>&1 | grep -E "FAILED|test result|error\[" | head -20 || true
  exit 0
fi

# --- TypeScript src auto-typecheck (operational closure check) ---
if [[ "$FILE_PATH" == "$REPO/sovereign-omega-v2/src/"*.ts ]]; then
  RELATIVE="${FILE_PATH#$REPO/sovereign-omega-v2/}"
  echo "AUTO-TYPECHECK: $RELATIVE written — running tsc --noEmit"
  cd "$REPO/sovereign-omega-v2"
  npm run typecheck 2>&1 | tail -15 || true
  exit 0
fi

exit 0
