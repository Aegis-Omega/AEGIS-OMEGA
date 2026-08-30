#!/usr/bin/env bash
# AEGIS ground-truth — the sense organ every session opens with.
# Answers, in five lines, the questions that kept getting forgotten:
#   what branch am I on · is work stranded off main · is it pushed ·
#   is the membrane intact · is production actually live.
# Read-only. Safe to run anytime, in a loop, at session start.
set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 0

echo "── AEGIS GROUND TRUTH ──────────────────────────────"
BR=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')
echo "branch:       $BR"

git fetch -q origin main 2>/dev/null || true
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo '?')
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo '?')
echo "vs main:      ${AHEAD} ahead · ${BEHIND} behind"
[ "$AHEAD" != "0" ] && [ "$AHEAD" != "?" ] && \
  echo "  ⚠ ${AHEAD} commit(s) are NOT on main — this work is stranded until merged."

UNPUSHED=$(git log --oneline '@{u}..' 2>/dev/null | wc -l | tr -d ' ')
DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo "unpushed:     ${UNPUSHED:-0} commit(s)"
echo "uncommitted:  ${DIRTY:-0} file(s)"
[ "${UNPUSHED:-0}" != "0" ] && \
  echo "  ⚠ local commits not on origin — push or they die with the container."

if [ -f sovereign-omega-v2/scripts/verify-hashes.mjs ]; then
  if (cd sovereign-omega-v2 && node scripts/verify-hashes.mjs >/dev/null 2>&1); then
    echo "membrane:     INTACT"
  else
    echo "membrane:     ⚠ HASH MISMATCH — halt, re-anchor before proceeding."
  fi
fi

for u in "https://aegisomega.com" "https://aegis-vertex.aegisomega.com/platform/status"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 6 "$u" 2>/dev/null || echo "---")
  echo "live:         $u -> $code"
done
echo "────────────────────────────────────────────────────"
echo "Loop: ground-truth → R·A·L·P·H → Gate 8 → push → PR to main."
echo "Nothing is 'done' until it is on main and verified."
