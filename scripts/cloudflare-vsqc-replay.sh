#!/usr/bin/env bash
set -u

ROOT="$(pwd)"
ASSET_DIR="$ROOT/aegisomega-webgpu/verified-semantic-quotient-consensus-v1"
WORK="/tmp/aegis-vsqc"
LOG="$ASSET_DIR/replay.log"
PYLOG="$ASSET_DIR/python.log"
AXLOG="$ASSET_DIR/axioms.log"
STATUS="$ASSET_DIR/status.json"

mkdir -p "$ASSET_DIR"
rm -rf "$WORK"
mkdir -p "$WORK"

exec > >(tee "$LOG") 2>&1

HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
MHP_BLOB="$(git rev-parse HEAD:harness/sdk/meaning_heritage.py 2>/dev/null || echo UNKNOWN)"
EXPECTED_MHP_BLOB="2cbd3293c1264cc976009fc85e03333f1790043f"
LEAN_VERSION="4.33.1"
LEAN_SHA256="890afd185370f85666025b883914ab4f4b339136f8c96167b69cfb62aecaf235"
MATHLIB_SHA="0df444a360eaa60ab8c11dca51a86af692955474"
SRC="$ROOT/sovereign-omega-v2/formal/bridges/lean/VerifiedSemanticQuotientConsensusV1.lean"
SOURCE_SHA256="$(sha256sum "$SRC" | awk '{print $1}')"
PYTHON_STATUS="NOT_RUN"

write_status() {
  python3 - "$STATUS" "$HEAD_SHA" "$MHP_BLOB" "$SOURCE_SHA256" "$PYTHON_STATUS" "$1" "$2" "$3" "$4" <<'PY'
import json,sys
path,head,mhp_blob,source_sha,python_status,stage,ok,leanv,detail=sys.argv[1:]
payload={
  "receipt_kind":"AEGIS_VERIFIED_SEMANTIC_QUOTIENT_CONSENSUS_REPLAY_V1",
  "head_sha":head,
  "mhp_meaning_heritage_blob":mhp_blob,
  "source_sha256":source_sha,
  "python_regressions":python_status,
  "lean_target":"4.33.1",
  "mathlib_sha":"0df444a360eaa60ab8c11dca51a86af692955474",
  "target_module":"VerifiedSemanticQuotientConsensusV1",
  "stage":stage,
  "verified":ok=="true",
  "lean_version_observed":leanv,
  "detail":detail,
  "accepted_relation":"SEMANTIC_EQUIVALENCE",
  "paraphrase_abstraction_accepted":False,
  "caller_minted_projection_trusted":False,
  "application_novelty":"NOT_ESTABLISHED",
  "authority_effect":"NONE"
}
open(path,"w").write(json.dumps(payload,sort_keys=True,indent=2)+"\n")
PY
}

write_status "START" "false" "" "semantic quotient replay starting"

echo "HEAD_SHA=$HEAD_SHA"
echo "MHP_BLOB=$MHP_BLOB"
echo "SOURCE_SHA256=$SOURCE_SHA256"

if [ "$MHP_BLOB" != "$EXPECTED_MHP_BLOB" ]; then
  write_status "MHP_DEPENDENCY_MISMATCH" "false" "" "$MHP_BLOB"
  exit 0
fi

echo "=== PYTHON SEMANTIC QUOTIENT REGRESSIONS ==="
if ! PYTHONPATH="$ROOT:$ROOT/sovereign-omega-v2/python"   python3 "$ROOT/sovereign-omega-v2/python/tests/test_verified_semantic_quotient_consensus.py" -v   2>&1 | tee "$PYLOG"; then
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

cp "$SRC" "$WORK/mathlib/VerifiedSemanticQuotientConsensusV1.lean"
COPIED="$(sha256sum "$WORK/mathlib/VerifiedSemanticQuotientConsensusV1.lean" | awk '{print $1}')"
echo "COPIED_SOURCE_SHA256=$COPIED"
if [ "$COPIED" != "$SOURCE_SHA256" ]; then
  write_status "SOURCE_COPY_MISMATCH" "false" "$LEANV" "$COPIED"
  exit 0
fi

BASE_LEAN_PATH="$(lake env printenv LEAN_PATH)"
OUT="$WORK/aegis-olean"
mkdir -p "$OUT"
export LEAN_PATH="$OUT:$BASE_LEAN_PATH"

echo "=== COMPILE VerifiedSemanticQuotientConsensusV1 ==="
if ! lean -o "$OUT/VerifiedSemanticQuotientConsensusV1.olean"   "$WORK/mathlib/VerifiedSemanticQuotientConsensusV1.lean"; then
  write_status "LEAN_COMPILE_FAILED" "false" "$LEANV" "see replay.log"
  exit 0
fi

cat > "$WORK/mathlib/VSQCAudit.lean" <<'LEAN'
import VerifiedSemanticQuotientConsensusV1
#print axioms AEGIS.VerifiedSemanticQuotientConsensusV1.retained_class_has_sound_pair
#print axioms AEGIS.VerifiedSemanticQuotientConsensusV1.no_retained_class_without_left_witness
#print axioms AEGIS.VerifiedSemanticQuotientConsensusV1.no_retained_class_without_right_witness
LEAN

echo "=== AXIOM AUDIT ==="
if ! lean "$WORK/mathlib/VSQCAudit.lean" 2>&1 | tee "$AXLOG"; then
  write_status "AXIOM_AUDIT_FAILED" "false" "$LEANV" "audit did not compile"
  exit 0
fi
if grep -q "sorryAx" "$AXLOG"; then
  write_status "SORRYAX_PRESENT" "false" "$LEANV" "sorryAx found"
  exit 0
fi

write_status "VERIFIED_EXACT_SOURCE" "true" "$LEANV"   "MHP-bound semantic projection suite passed; exact Lean quotient soundness compiled; axiom audit has no sorryAx"

echo "AEGIS_VERIFIED_SEMANTIC_QUOTIENT_CONSENSUS_REPLAY=PASS"
exit 0
