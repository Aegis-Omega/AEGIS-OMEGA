#!/usr/bin/env bash
# Kernel replay (--trust=0) of the module closure listed in $S/w/order.tsv, then the axiom audit.
# usage: FC=<formal-conjectures checkout at ce4868fd> S=<scratch dir with w/order.tsv> bash replay.sh
# Exits non-zero if any module or the audit fails.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${FC:?formal-conjectures checkout}"; : "${S:?scratch dir containing w/order.tsv}"
mkdir -p "$S/olean" "$S/w"
cd "$FC" || exit 1
BASE="$(lake env printenv LEAN_PATH)" || exit 1
export LEAN_PATH="$S/olean:$BASE"
# Refuse an empty or truncated closure: the audit could otherwise import stale .olean files.
EXPECTED="${EXPECTED:-26}"
n="$(grep -c . "$S/w/order.tsv")" || true
last="$(tail -n 1 "$S/w/order.tsv" | cut -f 1)"
if [ "$n" != "$EXPECTED" ] || [ "$last" != WeilSeparatedArchBridgeV31 ]; then
  echo "FAIL order.tsv: $n modules ending in '$last', expected $EXPECTED ending in WeilSeparatedArchBridgeV31"; exit 1
fi
: > "$S/w/replay.tsv"
while IFS=$'\t' read -r name file digest; do
  actual="$(sha256sum "$file" | cut -d ' ' -f 1)"
  if [ "$actual" != "$digest" ]; then echo "FAIL $name: source sha256 $actual does not match order.tsv $digest"; exit 1; fi
  t0=$(date +%s)
  lean --trust=0 -o "$S/olean/$name.olean" "$file" > "$S/w/log_$name.txt" 2>&1; rc=$?
  t1=$(date +%s)
  printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$rc" "$((t1-t0))" "$digest" "$(grep -c -i 'error' "$S/w/log_$name.txt")" >> "$S/w/replay.tsv"
  if [ "$rc" -ne 0 ]; then echo "FAIL $name"; exit 1; fi
done < "$S/w/order.tsv"
[ "$(wc -l < "$S/w/replay.tsv")" -eq "$EXPECTED" ] || { echo "FAIL replay.tsv row count"; exit 1; }
lean --trust=0 "$HERE/Audit.lean" > "$S/w/audit.log" 2>&1; rc=$?
echo "AUDIT_RC $rc" >> "$S/w/audit.log"
[ "$rc" -eq 0 ] || { echo "FAIL audit"; exit 1; }
if grep -q "sorryAx" "$S/w/audit.log"; then echo "FAIL sorryAx in audit"; exit 1; fi
python3 -I "$HERE/check_axioms.py" "$S/w/audit.log" "$HERE/Audit.lean" || { echo "FAIL audit axiom allowlist"; exit 1; }
echo DONE
