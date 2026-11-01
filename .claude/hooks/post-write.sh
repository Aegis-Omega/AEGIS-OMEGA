#!/bin/bash
# Post-write constitutional auto-verification hook.
# Fires after every Write or Edit tool call.
# Routes to the appropriate verification based on the file written.
# Autopoietic property: Viability Ring auto-assertion after every production event.

set -euo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Read the file path from stdin JSON
if ! FILE_PATH=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null); then
  echo 'AEGIS_POST_WRITE_HOLD: malformed tool event' >&2
  exit 2
fi

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Normalize to absolute path
if [[ "$FILE_PATH" != /* ]]; then
  FILE_PATH="$REPO/$FILE_PATH"
fi

# ── Enact autopoiesis: record the self-production event in the metacog chain ──
# Every Write/Edit must produce a certifiable AUTOPOIETIC_PRODUCTION event.
# The write tool has already executed; a failed observation is a HOLD, not a
# claim that the underlying write was rolled back. Never swallow chain errors.
CHAIN_MJS="$REPO/.claude/metacog/chain.mjs"
if [ ! -f "$CHAIN_MJS" ]; then
  echo 'AEGIS_POST_WRITE_HOLD: metacognitive chain engine missing' >&2
  exit 2
fi
REL="${FILE_PATH#$REPO/}"
if ! node "$CHAIN_MJS" observe AUTOPOIETIC_PRODUCTION T2 "produced: $REL" >/dev/null 2>&1; then
  echo 'AEGIS_POST_WRITE_HOLD: observation not recorded (lock, corruption or execution failure)' >&2
  exit 2
fi
# Independently check the persisted bytes. A successful process exit alone is
# not sufficient to promote the observation to valid metacognitive evidence.
if ! node "$CHAIN_MJS" certify | jq -e '.is_valid == true and .entry_count >= 1' >/dev/null; then
  echo 'AEGIS_POST_WRITE_HOLD: observation certificate invalid or unavailable' >&2
  exit 2
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
  if ! RUST_OUT=$(cargo test "$MODULE" 2>&1); then
    printf '%s\n' "$RUST_OUT" >&2
    echo 'AEGIS_POST_WRITE_HOLD: Rust validation failed' >&2
    exit 2
  fi
  printf '%s\n' "$RUST_OUT" | tail -20
  exit 0
fi

# --- TypeScript src auto-typecheck (operational closure check) ---
if [[ "$FILE_PATH" == "$REPO/sovereign-omega-v2/src/"*.ts ]]; then
  RELATIVE="${FILE_PATH#$REPO/sovereign-omega-v2/}"
  echo "AUTO-TYPECHECK: $RELATIVE written — running tsc --noEmit"
  cd "$REPO/sovereign-omega-v2"
  if ! TS_OUT=$(npm run typecheck 2>&1); then
    printf '%s\n' "$TS_OUT" >&2
    echo 'AEGIS_POST_WRITE_HOLD: TypeScript validation failed' >&2
    exit 2
  fi
  printf '%s\n' "$TS_OUT" | tail -15
  exit 0
fi

exit 0
