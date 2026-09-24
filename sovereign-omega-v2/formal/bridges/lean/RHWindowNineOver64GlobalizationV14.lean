import RHMomentGainV13
import RHMomentNumericsV14
import WeilWindowExhaustionV1
import Mathlib.Tactic

/-!
AEGIS Ω — radius-9/64 globalization producer V14.

Combines the generic V13 moment diagonal with the V14 rational certificate
momentGain (9/64) <= -1/10.  This closes arithmetic nonpositivity and the
canonical zero-quadratic sign on every moment-zero packet of logarithmic
half-width at most 9/64, and binds that result to WindowArithmeticNonpositiveV1.

This strictly extends the certified 1/8 window, but still does not prove all
finite windows or UniversalZeroQuadraticNonnegativeV10.
AUTHORITY_EFFECT = NONE.
-/

open Set Complex
open scoped BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHWindowNineOver64GlobalizationV14

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.RHDyadicDiagonalV13
open AEGIS.WeilAutocorrelationExplicitFormulaV10
open AEGIS.WeilThreeBlockAnalyticConstantsV21
open AEGIS.RHMomentGainV13
open AEGIS.RHMomentNumericsV14
open AEGIS.WeilWindowExhaustionV1

theorem nine_over_64_coercive
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : HalfWidthAt g (9 / 64) a)
    (hm : WeilMomentConditionsV1 g) :
    (WeilExplicitRightSideV1 (WeilAutocorrelationV1 g)).re ≤
      -(1 / 10) * energy g.1 := by
  have hlog : 2 * (9 / 64 : ℝ) < Real.log 2 := by
    linarith [log_two_lower]
  have hd := moment_diagonal g (9 / 64) a (by norm_num) hlog hw hm
  have hg := mul_le_mul_of_nonneg_right
    momentGain_nine_over_64 (energy_nonnegative g.1)
  linarith

theorem nine_over_64_zero_quadratic_nonnegative
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : HalfWidthAt g (9 / 64) a)
    (hm : WeilMomentConditionsV1 g) :
    0 ≤ (∑' rho : RiemannNontrivialZeroIndexV2,
      WeilZeroIndexSummandV1 (WeilAutocorrelationV1 g) rho).re := by
  have hc := nine_over_64_coercive g a hw hm
  have hE := energy_nonnegative g.1
  exact (autocorrelation_arithmetic_nonpositive_iff_zero_nonnegative_v10 g hm).mp
    (by nlinarith)

theorem window_nine_over_64_arithmetic_nonpositive_v14 :
    WindowArithmeticNonpositiveV1 (9 / 64) := by
  intro g hm hwindow
  have hw : HalfWidthAt g (9 / 64) 0 := by
    simpa [HalfWidthAt, LogSupportIn, LogWindowContainsV1] using hwindow
  have hc := nine_over_64_coercive g 0 hw hm
  have hE := energy_nonnegative g.1
  nlinarith

theorem window_le_nine_over_64_arithmetic_nonpositive_v14
    {L : ℝ} (hL : L ≤ 9 / 64) :
    WindowArithmeticNonpositiveV1 L :=
  windowArithmeticNonpositive_mono_v1 hL
    window_nine_over_64_arithmetic_nonpositive_v14

end AEGIS.RHWindowNineOver64GlobalizationV14

#print axioms AEGIS.RHWindowNineOver64GlobalizationV14.nine_over_64_coercive
#print axioms AEGIS.RHWindowNineOver64GlobalizationV14.nine_over_64_zero_quadratic_nonnegative
#print axioms AEGIS.RHWindowNineOver64GlobalizationV14.window_nine_over_64_arithmetic_nonpositive_v14
#print axioms AEGIS.RHWindowNineOver64GlobalizationV14.window_le_nine_over_64_arithmetic_nonpositive_v14
