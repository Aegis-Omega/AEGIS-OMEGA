#!/usr/bin/env bash
# AEGIS reuse gate, offline/zero-cloud-cost local test. NOT admission.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
EXPECTED="${1:-}"
HEAD="$(git rev-parse HEAD)"
if [[ -n "$EXPECTED" && "$EXPECTED" != "$HEAD" ]]; then
  echo "HOLD: exact HEAD mismatch: expected $EXPECTED; found $HEAD" >&2; exit 2
fi
for path in agents/source_reuse_preflight.py agents/tests/test_source_reuse_preflight.py; do
  [[ -f "$path" && ! -L "$path" ]] || { echo "HOLD: missing or symlink $path" >&2; exit 2; }
  INDEX_BLOB="$(git rev-parse "HEAD:$path")" || { echo "HOLD: file not committed: $path" >&2; exit 2; }
  WORK_BLOB="$(git hash-object "$path")"
  [[ "$INDEX_BLOB" == "$WORK_BLOB" ]] || { echo "HOLD: working file differs from exact HEAD: $path" >&2; exit 2; }
  echo "SOURCE_VERIFIED $path $INDEX_BLOB"
done
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
python3 -B -m unittest agents.tests.test_source_reuse_preflight -v
printf '\nAEGIS_REUSE_OFFLINE_PASS head=%s cloud_spend=0 admission=DENIED hosted_ci=UNVERIFIED\n' "$HEAD"
