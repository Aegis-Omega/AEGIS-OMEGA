#!/usr/bin/env bash
set -u

ROOT="$(pwd)"
ASSET_DIR="$ROOT/aegisomega-webgpu/gq-proof-runner"
WORK="/tmp/aegis-gq-lean"
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
TARGET="GravityQuantumPureProductV1"
SRC="$ROOT/sovereign-omega-v2/formal/bridges/lean"
SOURCE_SHA256="$(sha256sum "$SRC/$TARGET.lean" | awk '{print $1}')"

write_status() {
  python3 - "$STATUS" "$HEAD_SHA" "$SOURCE_SHA256" "$1" "$2" "$3" "$4" <<'PY'
import json,sys
path,head,source_sha,stage,ok,leanv,detail=sys.argv[1:]
payload={
  "receipt_kind":"AEGIS_GQ_CLOUDFLARE_LEAN_REPLAY_V1",
  "head_sha":head,
  "source_sha256":source_sha,
  "lean_target":"4.33.1",
  "mathlib_sha":"0df444a360eaa60ab8c11dca51a86af692955474",
  "target_module":"GravityQuantumPureProductV1",
  "target_declarations":[
    "AEGIS.GravityQuantumPureProductV1.coeffDet_eq_zero_iff_pureProductCoeffs",
    "AEGIS.GravityQuantumPureProductV1.coeffDet_ne_zero_iff_not_pureProductCoeffs"
  ],
  "stage":stage,
  "verified":ok=="true",
  "lean_version_observed":leanv,
  "detail":detail,
  "gravity_quantized":False,
  "quantum_gravity_proven":False,
  "authority_effect":"NONE"
}
open(path,"w").write(json.dumps(payload,sort_keys=True,indent=2)+"\n")
PY
}

write_status "START" "false" "" "replay starting"

echo "HEAD_SHA=$HEAD_SHA"
echo "SOURCE_SHA256=$SOURCE_SHA256"
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
if ! git clone --filter=blob:none --no-checkout   https://github.com/leanprover-community/mathlib4.git "$WORK/mathlib"; then
  write_status "MATHLIB_CLONE_FAILED" "false" "$LEANV" "git clone failed"
  exit 0
fi

cd "$WORK/mathlib"
if ! git fetch --depth 1 origin "$MATHLIB_SHA" ||
   ! git checkout --detach "$MATHLIB_SHA"; then
  write_status "MATHLIB_CHECKOUT_FAILED" "false" "$LEANV" "exact pin checkout failed"
  exit 0
fi

echo "MATHLIB_HEAD=$(git rev-parse HEAD)"
if ! lake exe cache get; then
  write_status "MATHLIB_CACHE_FAILED" "false" "$LEANV" "lake cache get failed"
  exit 0
fi

BASE_LEAN_PATH="$(lake env printenv LEAN_PATH)"
OUT="$WORK/aegis-olean"
mkdir -p "$OUT"
export LEAN_PATH="$OUT:$SRC:$BASE_LEAN_PATH"

echo "=== COMPILE $TARGET ==="
if ! lean -o "$OUT/$TARGET.olean" "$SRC/$TARGET.lean"; then
  write_status "LEAN_COMPILE_FAILED" "false" "$LEANV" "see replay.log"
  exit 0
fi

cat > "$WORK/Audit.lean" <<'LEAN'
import GravityQuantumPureProductV1
#print axioms AEGIS.GravityQuantumPureProductV1.pureProductCoeffs_imp_coeffDet_zero
#print axioms AEGIS.GravityQuantumPureProductV1.coeffDet_zero_imp_pureProductCoeffs
#print axioms AEGIS.GravityQuantumPureProductV1.coeffDet_eq_zero_iff_pureProductCoeffs
#print axioms AEGIS.GravityQuantumPureProductV1.coeffDet_ne_zero_iff_not_pureProductCoeffs
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

write_status "VERIFIED_EXACT_SOURCE" "true" "$LEANV"   "F2b source compiled and axiom audit contains no sorryAx"
echo "AEGIS_GQ_CLOUDFLARE_LEAN_REPLAY=PASS"
exit 0
