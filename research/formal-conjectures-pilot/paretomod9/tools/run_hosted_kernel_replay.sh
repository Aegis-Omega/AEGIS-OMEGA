#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PINS="$ROOT/PINS.json"
WORK="${RUNNER_TEMP:-/tmp}/aegis-paretomod9-lean-replay"
rm -rf "$WORK"
mkdir -p "$WORK" "$ROOT/evidence"

json_get() {
  python3 - "$PINS" "$1" <<'PY'
import json,sys
data=json.load(open(sys.argv[1]))
print(data[sys.argv[2]])
PY
}

FC_SHA="$(json_get formal_conjectures_sha)"
MATHLIB_SHA="$(json_get mathlib_sha)"
SOURCE_FILE="$(json_get candidate_file)"
SOURCE_SHA="$(json_get candidate_sha256)"
LEAN_ASSET="$(json_get lean_linux_asset)"
LEAN_ASSET_SHA="$(json_get lean_linux_asset_sha256)"

test "$(sha256sum "$ROOT/$SOURCE_FILE" | awk '{print $1}')" = "$SOURCE_SHA"

curl -fL --retry 4 --retry-all-errors \
  "https://github.com/leanprover/lean4/releases/download/v4.33.1/$LEAN_ASSET" \
  -o "$WORK/$LEAN_ASSET"
test "$(sha256sum "$WORK/$LEAN_ASSET" | awk '{print $1}')" = "$LEAN_ASSET_SHA"

tar --zstd -xf "$WORK/$LEAN_ASSET" -C "$WORK"
export PATH="$WORK/lean-4.33.1-linux/bin:$PATH"
lean --version | tee "$ROOT/evidence/lean-version.log"
lake --version | tee "$ROOT/evidence/lake-version.log"
lean --version | grep -F '4.33.1'
lean --version | grep -F '819816b2e0a3bf405af45ae5c7af2491d8f5bee6'

git clone --filter=blob:none --no-checkout \
  https://github.com/google-deepmind/formal-conjectures.git "$WORK/formal-conjectures"
git -C "$WORK/formal-conjectures" fetch --depth 1 origin "$FC_SHA"
git -C "$WORK/formal-conjectures" checkout --detach FETCH_HEAD
test "$(git -C "$WORK/formal-conjectures" rev-parse HEAD)" = "$FC_SHA"
test "$(tr -d '\r\n' < "$WORK/formal-conjectures/lean-toolchain")" = 'leanprover/lean4:v4.33.1'

python3 - "$WORK/formal-conjectures/lake-manifest.json" "$MATHLIB_SHA" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
pkgs={p["name"]:p for p in m["packages"]}
assert pkgs["mathlib"]["rev"] == sys.argv[2], pkgs["mathlib"]
print("MATHLIB_MANIFEST_PIN_OK", pkgs["mathlib"]["rev"])
PY

cd "$WORK/formal-conjectures"
lake exe cache get
test "$(git -C .lake/packages/mathlib rev-parse HEAD)" = "$MATHLIB_SHA"

cp "$ROOT/$SOURCE_FILE" .
set -o pipefail
lake env lean "$SOURCE_FILE" 2>&1 | tee "$ROOT/evidence/lean-kernel.log"

cd "$ROOT"
python3 tools/verify_axioms.py "$ROOT"
