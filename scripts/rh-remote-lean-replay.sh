#!/usr/bin/env bash
set -euo pipefail

AEGIS_ROOT="${AEGIS_ROOT:-$(pwd)}"
MATHLIB_SHA="${MATHLIB_SHA:-0df444a360eaa60ab8c11dca51a86af692955474}"
LEAN_TOOLCHAIN="${LEAN_TOOLCHAIN:-leanprover/lean4:v4.33.1}"
WORKDIR="${WORKDIR:-/tmp/aegis-rh-lean}"
ROOT="$AEGIS_ROOT/sovereign-omega-v2/formal/bridges/lean"

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

git clone --filter=blob:none --no-checkout https://github.com/leanprover-community/mathlib4.git mathlib4
cd mathlib4
git fetch --depth=1 origin "$MATHLIB_SHA"
git checkout --detach "$MATHLIB_SHA"

if [ "$(cat lean-toolchain)" != "$LEAN_TOOLCHAIN" ]; then
  echo "lean-toolchain mismatch: expected $LEAN_TOOLCHAIN, got $(cat lean-toolchain)" >&2
  exit 2
fi

if ! command -v elan >/dev/null 2>&1; then
  curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh |
    sh -s -- -y --default-toolchain none
fi
export PATH="$HOME/.elan/bin:$PATH"

mkdir -p evidence .lake/build/lib/lean
lake exe cache get
lean --version | tee evidence/lean-version.log
printf 'MATHLIB_SHA=%s\nLEAN_TOOLCHAIN=%s\nAEGIS_ROOT=%s\n'   "$MATHLIB_SHA" "$LEAN_TOOLCHAIN" "$AEGIS_ROOT" | tee evidence/pins.log

modules=(
  WeilCriterionCompactSmoothV1
  WeilPrimeSummabilityV1
  WeilArchimedeanConvergenceV1
  WeilAutocorrelationRealityV1
  WeilAutocorrelationClosureV1
  WeilFiniteSourceCalculusV1
  WeilArchSineKernelV1
  WeilArchSineKernelIntegerV1
  WeilArchFiniteQuadraticV1
  WeilArchTailIntegralV1
  WeilThreeBlockRationalV1
  WeilMixedClosureV2
  WeilThreeBlockComplexV2
  WeilMixedAlgebraV2
  WeilDisjointEnergyV2
  WeilThreeBlockAnalyticConstantsV21
  WeilLogCoordinateIsometryV21
  WeilThreeBlockNormBridgeV21
  WeilThreeBlockTranslatedPacketsV22
  WeilWidthPrimeVanishingV23
  WeilDiagonalKernelReductionV21
  WeilArchimedeanCothTailV1
  WeilWidthDiagonalArchFrontierV24
  WeilWidthArchCorrelationV25
  WeilWidthArchBudgetV26
  WeilWidthArchIntegralV27
  WeilThreeBlockCrossPrimeV28
  WeilThreeBlockCrossPrimeWindowV29
  WeilThreeBlockPrimeEvaluationV30
  WeilThreeBlockCrossAssemblyV30
  WeilSeparatedArchBridgeV31
  WeilMomentKillerConstructionV1
  WeilLogTransportCanonicalV1
  WeilTwoPointPositivityV1
  WeilAbjadFourPhaseBridgeV1
  RHNarrowMomentPacketV1
  RHFinalClosureSpineV1
  RHNarrowRetainedSignV1
  RHTranslatedKernelDominanceV1
  RHFourBlockBoundObstructionV1
)

for m in "${modules[@]}"; do
  test -f "$ROOT/$m.lean"
  cp "$ROOT/$m.lean" "$m.lean"
  sha256sum "$m.lean" | tee -a evidence/source-sha256.log
  echo "=== COMPILE $m ==="
  lake env lean -o ".lake/build/lib/lean/$m.olean" "$m.lean" 2>&1 |
    tee "evidence/$m.log"
done

cat > RHFinalAudit.lean <<'EOF'
import RHTranslatedKernelDominanceV1
import RHNarrowRetainedSignV1
#print axioms AEGIS.RHFinalClosureV1.final_sign_residual_iff_weil_negativity_v1
#print axioms AEGIS.RHTranslatedKernelDominanceV1.zero_shift_component_dominance_iff_final_sign_v1
#print axioms AEGIS.RHNarrowMomentPacketV1.gNarrow_moments
#print axioms AEGIS.RHNarrowMomentPacketV1.gNarrow_width
#print axioms AEGIS.RHNarrowRetainedSignV1.narrow_three_block_sign_v1
EOF

lake env lean RHFinalAudit.lean 2>&1 | tee evidence/axioms.log
if grep -Fq 'sorryAx' evidence/axioms.log; then
  echo "sorryAx detected" >&2
  exit 3
fi

echo "RH_LEAN_REPLAY=PASS"
