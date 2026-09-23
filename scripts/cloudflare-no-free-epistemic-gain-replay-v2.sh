#!/usr/bin/env bash
set -u

ROOT="$(pwd)"
ASSET_DIR="$ROOT/aegisomega-webgpu/no-free-epistemic-gain-v2"
WORK="/tmp/aegis-nfeg"
LOG="$ASSET_DIR/replay.log"
PYLOG="$ASSET_DIR/python.log"
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
SRC="$ROOT/sovereign-omega-v2/formal/bridges/lean/NoFreeEpistemicGainV1.lean"
SOURCE_SHA256="$(sha256sum "$SRC" | awk '{print $1}')"
PYTHON_STATUS="NOT_RUN"

write_status() {
  python3 - "$STATUS" "$HEAD_SHA" "$SOURCE_SHA256" "$PYTHON_STATUS" "$1" "$2" "$3" "$4" <<'PY'
import json,sys
path,head,source_sha,python_status,stage,ok,leanv,detail=sys.argv[1:]
payload={
  "receipt_kind":"AEGIS_NO_FREE_EPISTEMIC_GAIN_REPLAY_V2",
  "transport_generation":"CLEAN_IMPORT_FIX_V2",
  "head_sha":head,
  "source_sha256":source_sha,
  "python_regressions":python_status,
  "lean_target":"4.33.1",
  "mathlib_sha":"0df444a360eaa60ab8c11dca51a86af692955474",
  "target_module":"NoFreeEpistemicGainV1",
  "target_theorems":[
    "AEGIS.NoFreeEpistemicGainV1.le_meet_iff",
    "AEGIS.NoFreeEpistemicGainV1.no_free_epistemic_gain",
    "AEGIS.NoFreeEpistemicGainV1.meet_assoc",
    "AEGIS.NoFreeEpistemicGainV1.meet_comm",
    "AEGIS.NoFreeEpistemicGainV1.meet_idem"
  ],
  "stage":stage,
  "verified":ok=="true",
  "lean_version_observed":leanv,
  "detail":detail,
  "mathematical_novelty":"NOT_CLAIMED",
  "authority_effect":"NONE"
}
open(path,"w").write(json.dumps(payload,sort_keys=True,indent=2)+"\n")
PY
}

write_status "START" "false" "" "no-free epistemic gain replay starting"

echo "HEAD_SHA=$HEAD_SHA"
echo "SOURCE_SHA256=$SOURCE_SHA256"

echo "=== PYTHON FINITE-MODEL ORACLE ==="
if ! PYTHONPATH="$ROOT/sovereign-omega-v2/python"   python3 "$ROOT/sovereign-omega-v2/python/tests/test_no_free_epistemic_gain.py" -v   2>&1 | tee "$PYLOG"; then
  write_status "PYTHON_REGRESSION_FAILED" "false" "" "see python.log"
  exit 0
fi
PYTHON_STATUS="PASS"
echo "PYTHON_REGRESSIONS=PASS"

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
if [ "$(git rev-parse HEAD)" != "$MATHLIB_SHA" ]; then
  write_status "MATHLIB_HEAD_MISMATCH" "false" "$LEANV" "$(git rev-parse HEAD)"
  exit 0
fi

if ! lake exe cache get; then
  write_status "MATHLIB_CACHE_FAILED" "false" "$LEANV" "lake cache get failed"
  exit 0
fi

cp "$SRC" "$WORK/mathlib/NoFreeEpistemicGainV1.lean"
COPIED="$(sha256sum "$WORK/mathlib/NoFreeEpistemicGainV1.lean" | awk '{print $1}')"
echo "COPIED_SOURCE_SHA256=$COPIED"
if [ "$COPIED" != "$SOURCE_SHA256" ]; then
  write_status "SOURCE_COPY_MISMATCH" "false" "$LEANV" "$COPIED"
  exit 0
fi

BASE_LEAN_PATH="$(lake env printenv LEAN_PATH)"
OUT="$WORK/aegis-olean"
mkdir -p "$OUT"
export LEAN_PATH="$OUT:$BASE_LEAN_PATH"

echo "=== COMPILE NoFreeEpistemicGainV1 ==="
if ! lean -o "$OUT/NoFreeEpistemicGainV1.olean"   "$WORK/mathlib/NoFreeEpistemicGainV1.lean"; then
  write_status "LEAN_COMPILE_FAILED" "false" "$LEANV" "see replay.log"
  exit 0
fi

cat > "$WORK/mathlib/NFEGAudit.lean" <<'LEAN'
import NoFreeEpistemicGainV1
#print axioms AEGIS.NoFreeEpistemicGainV1.le_meet_iff
#print axioms AEGIS.NoFreeEpistemicGainV1.no_free_epistemic_gain
#print axioms AEGIS.NoFreeEpistemicGainV1.meet_assoc
#print axioms AEGIS.NoFreeEpistemicGainV1.meet_comm
#print axioms AEGIS.NoFreeEpistemicGainV1.meet_idem
LEAN

echo "=== AXIOM AUDIT ==="
if ! lean "$WORK/mathlib/NFEGAudit.lean" 2>&1 | tee "$AXLOG"; then
  write_status "AXIOM_AUDIT_FAILED" "false" "$LEANV" "audit did not compile"
  exit 0
fi
if grep -q "sorryAx" "$AXLOG"; then
  write_status "SORRYAX_PRESENT" "false" "$LEANV" "sorryAx found"
  exit 0
fi

write_status "VERIFIED_EXACT_SOURCE" "true" "$LEANV"   "Python finite-model suite passed; exact-source Lean module compiled; axiom audit has no sorryAx"

echo "AEGIS_NO_FREE_EPISTEMIC_GAIN_REPLAY_V2=PASS"
exit 0
