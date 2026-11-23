#!/usr/bin/env bash
# Run after scripts/replay.sh and lean/build.sh have built the pinned dependencies.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${FC:?formal-conjectures checkout at ce4868fd}"
: "${OLEAN:?olean directory populated by the prior two replay steps}"
: "${E1_LOGS:?absolute output directory for replay logs}"
mkdir -p "$E1_LOGS"
cd "$FC"
export LEAN_PATH="$OLEAN:$(lake env printenv LEAN_PATH)"

audit() {
  local source="$1" log="$2"
  shift 2
  if ! lean --trust=0 "$@" "$source" > "$log" 2>&1; then
    cat "$log" >&2
    return 1
  fi
  if grep -Eq 'sorryAx|warning|error' "$log"; then
    cat "$log" >&2
    return 1
  fi
  python3 -I "$HERE/../scripts/check_axioms.py" "$log" "$source"
}

audit "$HERE/../scripts/FiveBlockArithmetic.lean" "$E1_LOGS/FiveBlockArithmetic.log"
for module in WeilFiveBlockPerronV1 WeilFiveBlockCrossV1 WeilFiveBlockE1V1; do
  audit "$HERE/$module.lean" "$E1_LOGS/$module.log" \
    --root="$HERE" -o "$OLEAN/$module.olean"
done
