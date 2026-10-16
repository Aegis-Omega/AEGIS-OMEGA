#!/usr/bin/env bash
# AEGIS OPTIMUS: zero-cloud-cost offline scheduler and graph regression.
# Does not attest admission, host CI, execution, provider identity or completion.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
EXPECTED="${1:-}"
if [[ ! "$EXPECTED" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: bash scripts/verify-optimus-offline.sh <exact-40-hex-commit>" >&2
  exit 2
fi
HEAD="$(git rev-parse HEAD)"
if [[ "$HEAD" != "$EXPECTED" ]]; then
  echo "HOLD: commit changed; checkout exact expected SHA" >&2
  exit 2
fi
for path in scripts/optimus_company_tick.py scripts/test_optimus_company_tick.py; do
  if [[ ! -f "$path" || -L "$path" ]]; then
    echo "HOLD: missing or symlink $path" >&2
    exit 2
  fi
  COMMITTED="$(git rev-parse "HEAD:$path")"
  OBSERVED="$(git hash-object "$path")"
  if [[ "$COMMITTED" != "$OBSERVED" ]]; then
    echo "HOLD: working file differs from commit: $path" >&2
    exit 2
  fi
  echo "SOURCE_BOUND $path $COMMITTED"
done
export PYTHONPATH="$ROOT"
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest scripts.test_optimus_company_tick agents.tests.test_issue_evolution agents.tests.test_evolution_no_self_promotion -v
printf '\nSOURCE_LOCAL_TEST_PASS head=%s authority=NONE spend_usd=0 hosted_ci=UNVERIFIED main_admission=DENIED\n' "$HEAD"
