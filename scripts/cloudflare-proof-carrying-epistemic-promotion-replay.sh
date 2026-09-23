#!/usr/bin/env bash
set -u

ROOT="$(pwd)"
ASSET_DIR="$ROOT/aegisomega-webgpu/proof-carrying-epistemic-promotion-v1"
WORK="/tmp/aegis-pcep"
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
SRC="$ROOT/sovereign-omega-v2/formal/bridges/lean"
PARENT_FILE="NoFreeEpistemicGainV1.lean"
CHILD_FILE="ProofCarryingEpistemicPromotionV1.lean"
PARENT_SHA256="$(sha256sum "$SRC/$PARENT_FILE" | awk '{print $1}')"
CHILD_SHA256="$(sha256sum "$SRC/$CHILD_FILE" | awk '{print $1}')"
PYTHON_STATUS="NOT_RUN"

write_status() {
  python3 - "$STATUS" "$HEAD_SHA" "$PARENT_SHA256" "$CHILD_SHA256" "$PYTHON_STATUS" "$1" "$2" "$3" "$4" <<'PY'
import json,sys
path,head,parent_sha,child_sha,python_status,stage,ok,leanv,detail=sys.argv[1:]
payload={
  "receipt_kind":"AEGIS_PROOF_CARRYING_EPISTEMIC_PROMOTION_REPLAY_V1",
  "head_sha":head,
  "parent_source_sha256":parent_sha,
  "child_source_sha256":child_sha,
  "python_regressions":python_status,
  "lean_target":"4.33.1",
  "mathlib_sha":"0df444a360eaa60ab8c11dca51a86af692955474",
  "target_modules":[
    "NoFreeEpistemicGainV1",
    "ProofCarryingEpistemicPromotionV1"
  ],
  "stage":stage,
  "verified":ok=="true",
  "lean_version_observed":leanv,
  "detail":detail,
  "automatic_promotion":False,
  "application_novelty":"NOT_ESTABLISHED",
  "authority_effect":"NONE"
}
open(path,"w").write(json.dumps(payload,sort_keys=True,indent=2)+"\n")
PY
}

write_status "START" "false" "" "promotion replay starting"
echo "HEAD_SHA=$HEAD_SHA"
echo "PARENT_SOURCE_SHA256=$PARENT_SHA256"
echo "CHILD_SOURCE_SHA256=$CHILD_SHA256"

echo "=== PYTHON PROMOTION REGRESSIONS ==="
if ! PYTHONPATH="$ROOT/sovereign-omega-v2/python"   python3 "$ROOT/sovereign-omega-v2/python/tests/test_proof_carrying_epistemic_promotion.py" -v   2>&1 | tee "$PYLOG"; then
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
test "$(git rev-parse HEAD)" = "$MATHLIB_SHA"

if ! lake exe cache get; then
  write_status "MATHLIB_CACHE_FAILED" "false" "$LEANV" "lake cache get failed"
  exit 0
fi

cp "$SRC/$PARENT_FILE" "$WORK/mathlib/$PARENT_FILE"
cp "$SRC/$CHILD_FILE" "$WORK/mathlib/$CHILD_FILE"

PARENT_COPY="$(sha256sum "$WORK/mathlib/$PARENT_FILE" | awk '{print $1}')"
CHILD_COPY="$(sha256sum "$WORK/mathlib/$CHILD_FILE" | awk '{print $1}')"
echo "PARENT_COPIED_SHA256=$PARENT_COPY"
echo "CHILD_COPIED_SHA256=$CHILD_COPY"

if [ "$PARENT_COPY" != "$PARENT_SHA256" ] || [ "$CHILD_COPY" != "$CHILD_SHA256" ]; then
  write_status "SOURCE_COPY_MISMATCH" "false" "$LEANV" "copied theorem bytes differ"
  exit 0
fi

BASE_LEAN_PATH="$(lake env printenv LEAN_PATH)"
OUT="$WORK/aegis-olean"
mkdir -p "$OUT"
export LEAN_PATH="$OUT:$BASE_LEAN_PATH"

echo "=== COMPILE NoFreeEpistemicGainV1 ==="
if ! lean -o "$OUT/NoFreeEpistemicGainV1.olean"   "$WORK/mathlib/NoFreeEpistemicGainV1.lean"; then
  write_status "PARENT_LEAN_COMPILE_FAILED" "false" "$LEANV" "see replay.log"
  exit 0
fi

echo "=== COMPILE ProofCarryingEpistemicPromotionV1 ==="
if ! lean -o "$OUT/ProofCarryingEpistemicPromotionV1.olean"   "$WORK/mathlib/ProofCarryingEpistemicPromotionV1.lean"; then
  write_status "CHILD_LEAN_COMPILE_FAILED" "false" "$LEANV" "see replay.log"
  exit 0
fi

cat > "$WORK/mathlib/PCEPAudit.lean" <<'LEAN'
import NoFreeEpistemicGainV1
import ProofCarryingEpistemicPromotionV1
#print axioms AEGIS.ProofCarryingEpistemicPromotionV1.claim_gain_not_common_lower_bound
#print axioms AEGIS.ProofCarryingEpistemicPromotionV1.authority_gain_not_common_lower_bound
#print axioms AEGIS.ProofCarryingEpistemicPromotionV1.uncertainty_reduction_not_common_lower_bound
#print axioms AEGIS.ProofCarryingEpistemicPromotionV1.gain_not_common_lower_bound
LEAN

echo "=== AXIOM AUDIT ==="
if ! lean "$WORK/mathlib/PCEPAudit.lean" 2>&1 | tee "$AXLOG"; then
  write_status "AXIOM_AUDIT_FAILED" "false" "$LEANV" "audit did not compile"
  exit 0
fi
if grep -q "sorryAx" "$AXLOG"; then
  write_status "SORRYAX_PRESENT" "false" "$LEANV" "sorryAx found"
  exit 0
fi

write_status "VERIFIED_EXACT_SOURCE" "true" "$LEANV"   "promotion Python suite passed; exact parent and child Lean modules compiled; axiom audit has no sorryAx"

echo "AEGIS_PROOF_CARRYING_EPISTEMIC_PROMOTION_REPLAY=PASS"
exit 0
