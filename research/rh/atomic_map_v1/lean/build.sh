#!/usr/bin/env bash
# Kernel replay (--trust=0) of the diagonal log-gain modules; writes the *.trust0.txt evidence files.
# usage: FC=<formal-conjectures checkout at ce4868fd> OLEAN=<dir with the 26 V21-V31 oleans from ../scripts/replay.sh> bash build.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${FC:?formal-conjectures checkout}"; : "${OLEAN:?olean dir of the V21-V31 closure}"
cd "$FC"
export LEAN_PATH="$OLEAN:$(lake env printenv LEAN_PATH)"
for m in WeilDiagonalLogGainS1 WeilDiagonalLogGainV1; do
  out="$HERE/$m.trust0.txt"
  set +e
  lean --root="$HERE" --trust=0 -o "$OLEAN/$m.olean" "$HERE/$m.lean" > "$out" 2>&1; rc=$?
  set -e
  echo "rc=$rc" >> "$out"
  [ "$rc" -eq 0 ] || { echo "FAIL $m"; exit 1; }
  if grep -Eq "sorryAx|warning|error" "$out"; then echo "FAIL $m: sorry/warning/error in output"; exit 1; fi
  echo "OK $m"
done
