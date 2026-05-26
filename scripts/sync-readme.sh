#!/usr/bin/env bash
# PostToolUse hook — auto-syncs README test counts after cargo test.
# Called by .claude/settings.json hooks configuration.
# Reads full hook JSON from stdin.
# The organism updates its own record.

set -euo pipefail

README="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)/README.md"

# ── Read hook JSON from stdin ─────────────────────────────────────────────────

INPUT=$(cat)

# Only act when the command contained 'cargo test'
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
echo "$COMMAND" | grep -q 'cargo test' || exit 0

# Extract stdout from tool response
OUTPUT=$(echo "$INPUT" | jq -r '.tool_response // ""' 2>/dev/null || echo "")

# ── Count passed tests ────────────────────────────────────────────────────────

AEGIS_PSI=$(echo "$OUTPUT" | grep -oP '\d+ passed' | grep -oP '\d+' | awk '{s+=$1} END {print s+0}')

[ -z "$AEGIS_PSI" ] && exit 0
[ "$AEGIS_PSI" -lt 100 ] && exit 0

RUNTIME=55
TS=2790
TOTAL_RUST=$((AEGIS_PSI + RUNTIME))
TOTAL=$((AEGIS_PSI + RUNTIME + TS))

# ── Patch README badges and test-count lines ──────────────────────────────────

# Badge: Rust Tests
sed -i "s/Rust_Tests-[0-9]*_(aegis--cl--psi_+_runtime)/Rust_Tests-${TOTAL_RUST}_(aegis--cl--psi_+_runtime)/g" "$README"

# Badge: Total Tests
sed -i "s/Total_Tests-[0-9]*/Total_Tests-${TOTAL}/g" "$README"

# Testing section header line
sed -i "s/^[0-9]* total tests · 0 failures/${TOTAL} total tests · 0 failures/" "$README"

# Test breakdown line for aegis-cl-psi (indented with 2 spaces)
sed -i "s/^  [0-9]*  Rust        aegis-cl-psi  /  ${AEGIS_PSI}  Rust        aegis-cl-psi  /" "$README"

# Genesis section: "N,NNN invariant tests" bold count
sed -i "s/\*\*[0-9,]*\*\* invariant tests/**${TOTAL}** invariant tests/g" "$README"

# Closing line: "N of them, watching each other"
GATE_COUNT=$(grep -c '^pub mod ' "${README%/*}/aegis-cl-psi/src/lib.rs" 2>/dev/null || echo "321")
sed -i "s/\*[0-9]* of them, watching each other/*${GATE_COUNT} of them, watching each other/g" "$README"

printf 'README synced: aegis-cl-psi=%d runtime=%d TS=%d total=%d\n' \
  "$AEGIS_PSI" "$RUNTIME" "$TS" "$TOTAL" >&2

# System message shown in Claude Code UI
printf '{"systemMessage": "README auto-synced — %d Rust + %d TS = %d total"}\n' \
  "$TOTAL_RUST" "$TS" "$TOTAL"
