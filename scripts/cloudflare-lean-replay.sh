#!/usr/bin/env bash
set -u

ROOT="$(pwd)"
ASSET_DIR="$ROOT/aegisomega-webgpu/proof-runner"
WORK="/tmp/aegis-rh-lean"
LOG="$ASSET_DIR/replay.log"
AXLOG="$ASSET_DIR/axioms.log"
STATUS="$ASSET_DIR/status.json"
mkdir -p "$ASSET_DIR"
rm -rf "$WORK"
mkdir -p "$WORK"

exec > >(tee "$LOG") 2>&1

HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
LEAN_VERSION="4.33.1"
LEAN_SHA256="890afd185370f85666025b883914ab4f4b339136f8c96167b69cfb62aecaf235"
MATHLIB_SHA="0df444a360eaa60ab8c11dca51a86af692955474"
TARGET="RHFourBlockConcreteV3"
TARGET_DECL="AEGIS.RHFourBlockConcreteV3.canonical_four_packet_sign_v3"

write_status() {
  python3 - "$STATUS" "$HEAD_SHA" "$1" "$2" "$3" "$4" <<'PY'
import json,sys
path,head,stage,ok,leanv,detail=sys.argv[1:]
payload={
  "receipt_kind":"AEGIS_CLOUDFLARE_LEAN_REPLAY_V1",
  "head_sha":head,
  "lean_target":"4.33.1",
  "mathlib_sha":"0df444a360eaa60ab8c11dca51a86af692955474",
  "target_module":"RHFourBlockConcreteV3",
  "target_decl":"AEGIS.RHFourBlockConcreteV3.canonical_four_packet_sign_v3",
  "stage":stage,
  "verified":ok=="true",
  "lean_version_observed":leanv,
  "detail":detail,
  "authority_effect":"NONE",
  "rh_proven":False
}
open(path,"w").write(json.dumps(payload,sort_keys=True,indent=2)+"\n")
PY
}

write_status "START" "false" "" "replay starting"

echo "HEAD_SHA=$HEAD_SHA"
echo "Downloading Lean $LEAN_VERSION"
if ! curl -fL --retry 3 --retry-delay 2   "https://github.com/leanprover/lean4/releases/download/v4.33.1/lean-4.33.1-linux.tar.zst"   -o "$WORK/lean.tar.zst"; then
  write_status "LEAN_DOWNLOAD_FAILED" "false" "" "curl failed"
  exit 0
fi

ACTUAL="$(sha256sum "$WORK/lean.tar.zst" | awk '{print $1}')"
echo "LEAN_TARBALL_SHA256=$ACTUAL"
if [ "$ACTUAL" != "$LEAN_SHA256" ]; then
  write_status "LEAN_DIGEST_MISMATCH" "false" "" "$ACTUAL"
  exit 0
fi

if ! tar --zstd -xf "$WORK/lean.tar.zst" -C "$WORK"; then
  write_status "LEAN_EXTRACT_FAILED" "false" "" "tar failed"
  exit 0
fi
LEAN_HOME="$WORK/lean-4.33.1-linux"
export PATH="$LEAN_HOME/bin:$PATH"
LEANV="$(lean --version 2>&1 | tr '\n' ' ')"
echo "LEAN_VERSION_OBSERVED=$LEANV"

echo "Fetching Mathlib exact pin $MATHLIB_SHA"
if ! git clone --filter=blob:none --no-checkout https://github.com/leanprover-community/mathlib4.git "$WORK/mathlib"; then
  write_status "MATHLIB_CLONE_FAILED" "false" "$LEANV" "git clone failed"
  exit 0
fi
cd "$WORK/mathlib"
if ! git fetch --depth 1 origin "$MATHLIB_SHA" || ! git checkout --detach "$MATHLIB_SHA"; then
  write_status "MATHLIB_CHECKOUT_FAILED" "false" "$LEANV" "exact pin checkout failed"
  exit 0
fi
echo "MATHLIB_HEAD=$(git rev-parse HEAD)"

echo "Downloading Mathlib cache"
if ! lake exe cache get; then
  write_status "MATHLIB_CACHE_FAILED" "false" "$LEANV" "lake cache get failed"
  exit 0
fi

BASE_LEAN_PATH="$(lake env printenv LEAN_PATH)"
SRC="$ROOT/sovereign-omega-v2/formal/bridges/lean"
OUT="$WORK/aegis-olean"
mkdir -p "$OUT"

echo "Computing local dependency closure for $TARGET"
python3 - "$SRC" "$TARGET" "$WORK/order.txt" <<'PY'
import pathlib,re,sys
src=pathlib.Path(sys.argv[1]); target=sys.argv[2]; out=pathlib.Path(sys.argv[3])
mods={p.stem:p for p in src.glob("*.lean")}
deps={}
for m,p in mods.items():
    ds=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        s=line.strip()
        if not s.startswith("import "): continue
        for token in s[len("import "):].split():
            root=token.split(".")[0]
            if root in mods: ds.append(root)
    deps[m]=ds
seen=set(); temp=set(); order=[]
def visit(m):
    if m in seen: return
    if m in temp: raise SystemExit("cycle:"+m)
    if m not in mods: raise SystemExit("missing local module:"+m)
    temp.add(m)
    for d in deps[m]: visit(d)
    temp.remove(m); seen.add(m); order.append(m)
visit(target)
out.write_text("\n".join(order)+"\n")
print("LOCAL_CLOSURE_COUNT",len(order))
print("\n".join(order))
PY
if [ $? -ne 0 ]; then
  write_status "DEPENDENCY_GRAPH_FAILED" "false" "$LEANV" "closure generation failed"
  exit 0
fi

export LEAN_PATH="$OUT:$SRC:$BASE_LEAN_PATH"
COMPILE_OK=true
while IFS= read -r MOD; do
  [ -z "$MOD" ] && continue
  echo "=== COMPILE $MOD ==="
  if ! lean -o "$OUT/$MOD.olean" "$SRC/$MOD.lean"; then
    echo "COMPILE_FAILED=$MOD"
    COMPILE_OK=false
    break
  fi
done < "$WORK/order.txt"

if [ "$COMPILE_OK" != "true" ]; then
  write_status "LEAN_COMPILE_FAILED" "false" "$LEANV" "see replay.log"
  exit 0
fi

cat > "$WORK/Audit.lean" <<'LEAN'
import RHFourBlockConcreteV3
#print axioms AEGIS.RHFourBlockPrimeEightV3.farthest_B_norm_bound_v3
#print axioms AEGIS.RHNarrowDiagonalUpgradeV2.narrow_diagonal_32_over_25_v2
#print axioms AEGIS.RHFourBlockConcreteV3.four_packet_coercive_v3
#print axioms AEGIS.RHFourBlockConcreteV3.canonical_four_packet_sign_v3
LEAN

echo "=== AXIOM AUDIT ==="
if ! lean "$WORK/Audit.lean" 2>&1 | tee "$AXLOG"; then
  write_status "AXIOM_AUDIT_FAILED" "false" "$LEANV" "audit did not compile"
  exit 0
fi
if grep -q "sorryAx" "$AXLOG"; then
  write_status "SORRYAX_PRESENT" "false" "$LEANV" "sorryAx found"
  exit 0
fi

write_status "VERIFIED_EXACT_SOURCE" "true" "$LEANV" "target closure compiled; see axioms.log"
echo "AEGIS_CLOUDFLARE_LEAN_REPLAY=PASS"
exit 0
