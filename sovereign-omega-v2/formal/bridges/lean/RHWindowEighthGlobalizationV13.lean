import RHMomentGainV13
import WeilWindowExhaustionV1
import Mathlib.Tactic

/-!
AEGIS Ω — bind the V13 moment-gain theorem to the globalization window language.

RHMomentGainV13.wide_coercive proves arithmetic nonpositivity for every
moment-zero packet whose logarithmic support is contained in an interval of
half-width 1/8. WeilWindowExhaustionV1 formulates the remaining global
obligation as arithmetic nonpositivity on every finite symmetric log window.

This file closes the concrete symmetric window L = 1/8 and, by monotonicity,
every smaller window. It does not prove the positive-integer cofinal family,
universal arithmetic nonpositivity, UniversalZeroQuadraticNonnegativeV10,
or the Riemann Hypothesis.

AUTHORITY_EFFECT = NONE.
-/

open Set Complex

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHWindowEighthGlobalizationV13

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.RHDyadicDiagonalV13
open AEGIS.RHMomentGainV13
open AEGIS.WeilWindowExhaustionV1

/-- The V13 moment-gain estimate closes the globalization obligation on the
symmetric logarithmic window [-1/8, 1/8]. -/
theorem window_eighth_arithmetic_nonpositive_v13 :
    WindowArithmeticNonpositiveV1 (1 / 8) := by
  intro g hm hwindow
  have hw : HalfWidthAt g (1 / 8) 0 := by
    simpa [HalfWidthAt, LogSupportIn, LogWindowContainsV1] using hwindow
  have h := wide_coercive g 0 hw hm
  have hE := energy_nonnegative g.1
  nlinarith

/-- Every positive window no wider than 1/8 inherits the same sign theorem. -/
theorem window_le_eighth_arithmetic_nonpositive_v13
    {L : ℝ} (hL0 : 0 < L) (hL : L ≤ 1 / 8) :
    WindowArithmeticNonpositiveV1 L :=
  windowArithmeticNonpositive_mono_v1 hL
    window_eighth_arithmetic_nonpositive_v13

end AEGIS.RHWindowEighthGlobalizationV13

#print axioms AEGIS.RHWindowEighthGlobalizationV13.window_eighth_arithmetic_nonpositive_v13
#print axioms AEGIS.RHWindowEighthGlobalizationV13.window_le_eighth_arithmetic_nonpositive_v13
