#!/bin/bash
# Pre-commit Gate 8 auto-block.
# Reads Bash tool input from stdin — blocks commit if typecheck or build fails.

set -euo pipefail

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null || echo "")

if ! echo "$CMD" | grep -q "git commit"; then
  exit 0
fi

echo "GATE 8: pre-commit typecheck + build..."
cd /home/user/AEGIS--/sovereign-omega-v2

TYPECHECK=$(npm run typecheck 2>&1 | tail -8)
if echo "$TYPECHECK" | grep -qE "error TS|Found [0-9]+ error"; then
  echo "BLOCKED: typecheck failed."
  echo "$TYPECHECK"
  exit 2
fi
echo "  typecheck: OK"

BUILD=$(npm run build 2>&1 | tail -8)
if echo "$BUILD" | grep -qiE "error|failed"; then
  echo "BLOCKED: build failed."
  echo "$BUILD"
  exit 2
fi
echo "  build: OK"
echo "Gate 8 passed — commit proceeding."
exit 0
