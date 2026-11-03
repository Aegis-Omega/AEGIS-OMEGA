#!/usr/bin/env bash
# AEGIS local ground-truth. Read-only: no git fetch, install, curl or deploy.
set -uo pipefail
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo 'AEGIS local ground-truth: UNKNOWN (not a git checkout)'
  exit 0
}
cd "$ROOT" || exit 0
echo '── AEGIS LOCAL GROUND TRUTH ─────────────────────────'
BR=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')
echo "branch:       $BR"
if git show-ref --verify --quiet refs/remotes/origin/main; then
  AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo '?')
  BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo '?')
  echo "vs main:      ${AHEAD} ahead · ${BEHIND} behind (LAST-FETCHED LOCAL REF, not live)"
else
  echo 'vs main:      UNKNOWN (no local origin/main; remote not queried)'
fi
UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
if [[ -n "$UPSTREAM" ]]; then
  UNPUSHED=$(git rev-list --count "$UPSTREAM"..HEAD 2>/dev/null || echo '?')
  echo "unpushed:     $UNPUSHED commit(s), relative to local upstream"
else
  echo 'unpushed:     UNKNOWN (upstream not configured locally)'
fi
DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo "uncommitted:  ${DIRTY:-?} file(s)"
if [[ -f sovereign-omega-v2/scripts/verify-hashes.mjs ]]; then
  if (cd sovereign-omega-v2 && node scripts/verify-hashes.mjs >/dev/null 2>&1); then
    echo 'membrane:     VERIFIED by current local hash checker'
  else
    echo 'membrane:     FAILED or UNAVAILABLE; no promotion without inspection'
  fi
else
  echo 'membrane:     UNKNOWN (hash checker missing)'
fi
echo 'production:   NOT_CHECKED (no automatic HTTP or deploy operations)'
echo 'CI status:    NOT_CHECKED (local inventory is not a native CI receipt)'
echo 'Proof status: NOT_ASSESSED (branch/CI state is not mathematical truth)'
echo '────────────────────────────────────────────────────'
