#!/usr/bin/env bash
# Kernel replay of the diagonal log-gain modules.
# usage: FC=<formal-conjectures checkout at ce4868fd> OLEAN=<dir with the 26 V21-V31 oleans from ../scripts/replay.sh> bash build.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${FC:?formal-conjectures checkout}"; : "${OLEAN:?olean dir of the V21-V31 closure}"
cd "$FC"
export LEAN_PATH="$OLEAN:$(lake env printenv LEAN_PATH)"
lean --root="$HERE" --trust=0 -o "$OLEAN/WeilDiagonalLogGainS1.olean" "$HERE/WeilDiagonalLogGainS1.lean"
lean --root="$HERE" --trust=0 -o "$OLEAN/WeilDiagonalLogGainV1.olean" "$HERE/WeilDiagonalLogGainV1.lean"
