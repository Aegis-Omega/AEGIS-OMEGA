import WeilWindowExhaustionV1
import RHNarrowDiagonalUpgradeV2
import Mathlib.Tactic

/-!
AEGIS Ω — unconditional small-window sign producer V1.

This module binds the existing narrow-support diagonal theorem to the exact
window-exhaustion API.

For every repository packet whose logarithmic support is contained in
[-1/128, 1/128], the actual autocorrelation explicit-formula right side is
nonpositive.

No RH hypothesis, no universal sign hypothesis, no supplied PSD matrix and no
external certificate is used.

This is a genuine producer for one nontrivial finite window. It does not yet
prove arbitrary-window nonpositivity or universal Weil negativity.

AUTHORITY_EFFECT = NONE.
-/

open Set MeasureTheory Complex

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHSmallWindowProducerV1

open AEGIS.WeilWindowExhaustionV1
open AEGIS.RHNarrowDiagonalUpgradeV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilDisjointEnergyV2

/-- A radius-1/128 symmetric log window is exactly the width-1/64 support
condition consumed by the narrow diagonal theorem. -/
theorem window_one_over_128_implies_narrow_v1
    (g : WeilCompactSmoothGV1)
    (hw : LogWindowContainsV1 g (1 / 128 : ℝ)) :
    WidthOneSixtyFourAt g 0 := by
  intro t ht
  have h := hw ht
  simpa [WidthOneSixtyFourAt] using h

/-- First unconditional producer for the window-exhaustion hierarchy. -/
theorem windowArithmeticNonpositive_one_over_128_v1 :
    WindowArithmeticNonpositiveV1 (1 / 128 : ℝ) := by
  intro g hm hw
  have hnarrow : WidthOneSixtyFourAt g 0 :=
    window_one_over_128_implies_narrow_v1 g hw
  have hdiag :=
    narrow_diagonal_32_over_25_v2 g 0 hnarrow
  have hE : 0 ≤ energy g.1 := energy_nonnegative g.1
  change (B g g).re ≤ 0
  nlinarith

/-- Every smaller nonnegative symmetric window inherits the same sign result. -/
theorem windowArithmeticNonpositive_of_nonneg_le_one_over_128_v1
    {L : ℝ} (hL0 : 0 ≤ L) (hL : L ≤ (1 / 128 : ℝ)) :
    WindowArithmeticNonpositiveV1 L := by
  exact windowArithmeticNonpositive_mono_v1 hL
    windowArithmeticNonpositive_one_over_128_v1

end AEGIS.RHSmallWindowProducerV1

#print axioms AEGIS.RHSmallWindowProducerV1.window_one_over_128_implies_narrow_v1
#print axioms AEGIS.RHSmallWindowProducerV1.windowArithmeticNonpositive_one_over_128_v1
#print axioms AEGIS.RHSmallWindowProducerV1.windowArithmeticNonpositive_of_nonneg_le_one_over_128_v1
