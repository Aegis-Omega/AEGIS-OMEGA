#!/usr/bin/env bash
set -u

ROOT="$(pwd)"
ASSET_DIR="$ROOT/aegisomega-webgpu/sgm-proof-runner"
WORK="/tmp/aegis-sgm"
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
AUTH_FILE="EpistemicAuthorityConservationV1.lean"
ACC_FILE="EpistemicAccountingV1.lean"
AUTH_SHA256="$(sha256sum "$SRC/$AUTH_FILE" | awk '{print $1}')"
ACC_SHA256="$(sha256sum "$SRC/$ACC_FILE" | awk '{print $1}')"
PYTHON_STATUS="NOT_RUN"

write_status() {
  python3 - "$STATUS" "$HEAD_SHA" "$AUTH_SHA256" "$ACC_SHA256" "$PYTHON_STATUS" "$1" "$2" "$3" "$4" <<'PY'
import json,sys
path,head,auth_sha,acc_sha,python_status,stage,ok,leanv,detail=sys.argv[1:]
payload={
  "receipt_kind":"AEGIS_SGM_CLOUDFLARE_REPLAY_V1",
  "head_sha":head,
  "authority_source_sha256":auth_sha,
  "accounting_source_sha256":acc_sha,
  "python_regressions":python_status,
  "python_suites":[
    "epistemic_authority_conservation",
    "epistemic_accounting",
    "epistemic_conservation_kernel",
    "statistical_godel_machine"
  ],
  "lean_target":"4.33.1",
  "mathlib_sha":"0df444a360eaa60ab8c11dca51a86af692955474",
  "target_modules":[
    "EpistemicAuthorityConservationV1",
    "EpistemicAccountingV1"
  ],
  "stage":stage,
  "verified":ok=="true",
  "lean_version_observed":leanv,
  "detail":detail,
  "automatic_rewrite":False,
  "global_optimality_claimed":False,
  "authority_effect":"NONE"
}
open(path,"w").write(json.dumps(payload,sort_keys=True,indent=2)+"\n")
PY
}

write_status "START" "false" "" "SGM replay starting"
echo "HEAD_SHA=$HEAD_SHA"
echo "AUTHORITY_SOURCE_SHA256=$AUTH_SHA256"
echo "ACCOUNTING_SOURCE_SHA256=$ACC_SHA256"

run_python_suite() {
  local file="$1"
  echo "=== PYTHON $file ==="
  PYTHONPATH="$ROOT/sovereign-omega-v2/python"     python3 "$ROOT/sovereign-omega-v2/python/tests/$file" -v
}

{
  run_python_suite test_epistemic_authority_conservation.py &&
  run_python_suite test_epistemic_accounting.py &&
  run_python_suite test_epistemic_conservation_kernel.py &&
  run_python_suite test_statistical_godel_machine.py
} 2>&1 | tee "$PYLOG"
PY_RC=${PIPESTATUS[0]}
if [ "$PY_RC" -ne 0 ]; then
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
echo "MATHLIB_HEAD=$(git rev-parse HEAD)"

if ! lake exe cache get; then
  write_status "MATHLIB_CACHE_FAILED" "false" "$LEANV" "lake cache get failed"
  exit 0
fi

cp "$SRC/$AUTH_FILE" "$WORK/mathlib/$AUTH_FILE"
cp "$SRC/$ACC_FILE" "$WORK/mathlib/$ACC_FILE"

AUTH_COPY="$(sha256sum "$WORK/mathlib/$AUTH_FILE" | awk '{print $1}')"
ACC_COPY="$(sha256sum "$WORK/mathlib/$ACC_FILE" | awk '{print $1}')"
echo "AUTHORITY_COPIED_SHA256=$AUTH_COPY"
echo "ACCOUNTING_COPIED_SHA256=$ACC_COPY"
if [ "$AUTH_COPY" != "$AUTH_SHA256" ] || [ "$ACC_COPY" != "$ACC_SHA256" ]; then
  write_status "SOURCE_COPY_MISMATCH" "false" "$LEANV" "copied theorem bytes differ"
  exit 0
fi

BASE_LEAN_PATH="$(lake env printenv LEAN_PATH)"
OUT="$WORK/aegis-olean"
mkdir -p "$OUT"
export LEAN_PATH="$OUT:$BASE_LEAN_PATH"

echo "=== COMPILE EpistemicAuthorityConservationV1 ==="
if ! lean -o "$OUT/EpistemicAuthorityConservationV1.olean"   "$WORK/mathlib/EpistemicAuthorityConservationV1.lean"; then
  write_status "AUTHORITY_LEAN_COMPILE_FAILED" "false" "$LEANV" "see replay.log"
  exit 0
fi

echo "=== COMPILE EpistemicAccountingV1 ==="
if ! lean -o "$OUT/EpistemicAccountingV1.olean"   "$WORK/mathlib/EpistemicAccountingV1.lean"; then
  write_status "ACCOUNTING_LEAN_COMPILE_FAILED" "false" "$LEANV" "see replay.log"
  exit 0
fi

cat > "$WORK/mathlib/SGMAudit.lean" <<'LEAN'
import EpistemicAuthorityConservationV1
import EpistemicAccountingV1
#print axioms AEGIS.EpistemicAuthorityConservationV1.chainAuthority_le_initial
#print axioms AEGIS.EpistemicAuthorityConservationV1.zero_is_absorbing
#print axioms AEGIS.EpistemicAccountingV1.left_uncertainty_le_of_loss
#print axioms AEGIS.EpistemicAccountingV1.right_uncertainty_le_of_loss
#print axioms AEGIS.EpistemicAccountingV1.card_disjoint_partition
LEAN

echo "=== AXIOM AUDIT ==="
if ! lean "$WORK/mathlib/SGMAudit.lean" 2>&1 | tee "$AXLOG"; then
  write_status "AXIOM_AUDIT_FAILED" "false" "$LEANV" "audit did not compile"
  exit 0
fi

if grep -q "sorryAx" "$AXLOG"; then
  write_status "SORRYAX_PRESENT" "false" "$LEANV" "sorryAx found"
  exit 0
fi

write_status "VERIFIED_EXACT_SOURCE" "true" "$LEANV"   "four Python suites passed; both exact-source Lean modules compiled; axiom audit has no sorryAx"
echo "AEGIS_SGM_CLOUDFLARE_REPLAY=PASS"
exit 0
