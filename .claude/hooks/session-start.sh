#!/usr/bin/env bash
# AEGIS SessionStart: local, read-only inventory. Never install on a hook.
set -euo pipefail
if [[ "${CLAUDE_CODE_REMOTE:-}" != "true" ]]; then
  exit 0
fi
REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
if [[ ! -d "$REPO" ]]; then
  printf 'AEGIS session preflight UNKNOWN: repository unavailable. No dependencies installed.\n'
  exit 0
fi
printf 'AEGIS session preflight: no auto-install, no credential changes, no network fetch.\n'
if [[ -f "$REPO/scripts/ground-truth.sh" ]]; then
  (cd "$REPO" && bash scripts/ground-truth.sh) || printf 'AEGIS local inventory UNKNOWN: inspect repository before acting.\n'
else
  printf 'AEGIS local inventory UNKNOWN: ground-truth.sh is absent.\n'
fi
printf 'Missing dependencies remain UNKNOWN until explicit, authorized setup; do not infer readiness.\n'
