import RHSmallWindowProducerV1
import Mathlib.Tactic

/-!
AEGIS Ω — unconditional narrow-window sign producer V1.

PR #659 proves `WindowArithmeticNonpositiveV1 (1/128)`, whose interface carries
`WeilMomentConditionsV1 g`.  Inspection of the proof shows that premise is
not used: the load-bearing theorem `narrow_diagonal_32_over_25_v2` already
gives a stronger statement for every repository packet with logarithmic support
inside a radius-1/128 window.

This module exposes that stronger producer explicitly.  It is useful for a
future localization / partition argument because localized pieces need not
individually preserve the two global moment constraints.

No arbitrary-window theorem and no RH conclusion is asserted.

AUTHORITY_EFFECT = NONE.
-/

open Set Complex

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHSmallWindowUnconditionalV1

open AEGIS.WeilMixedAlgebraV2
open AEGIS.RHNarrowDiagonalUpgradeV2
open AEGIS.WeilWindowExhaustionV1

def NarrowWindowArithmeticNonpositiveV1 (L : ℝ) : Prop :=
  ∀ g : WeilCompactSmoothGV1,
    LogWindowContainsV1 g L →
    (WeilExplicitRightSideV1 (WeilAutocorrelationV1 g)).re ≤ 0

theorem narrowWindowArithmeticNonpositive_one_over_128_v1 :
    NarrowWindowArithmeticNonpositiveV1 (1 / 128 : ℝ) := by
  intro g hwindow
  have hw : WidthOneSixtyFourAt g 0 := by
    intro t ht
    have h := hwindow ht
    simpa only [zero_sub, zero_add] using h
  have hdiag := narrow_diagonal_32_over_25_v2 g 0 hw
  have hE := AEGIS.WeilDisjointEnergyV2.energy_nonnegative g.1
  change (B g g).re ≤ 0
  nlinarith

theorem windowArithmeticNonpositive_one_over_128_from_unconditional_v1 :
    WindowArithmeticNonpositiveV1 (1 / 128 : ℝ) := by
  intro g _hm hwindow
  exact narrowWindowArithmeticNonpositive_one_over_128_v1 g hwindow

theorem narrowWindowArithmeticNonpositive_of_nonneg_le_one_over_128_v1
    (L : ℝ) (hL0 : 0 ≤ L) (hL : L ≤ (1 / 128 : ℝ)) :
    NarrowWindowArithmeticNonpositiveV1 L := by
  intro g hwindow
  apply narrowWindowArithmeticNonpositive_one_over_128_v1 g
  intro t ht
  have h := hwindow ht
  exact ⟨by linarith [h.1], by linarith [h.2]⟩

/-- Exact localization-ready form: no moment premise appears. -/
theorem localized_packet_diagonal_nonpositive_v1
    (g : WeilCompactSmoothGV1)
    (hwindow : LogWindowContainsV1 g (1 / 128 : ℝ)) :
    (B g g).re ≤ 0 := by
  exact narrowWindowArithmeticNonpositive_one_over_128_v1 g hwindow

/-- Quantitative localization-ready form retaining the 32/25 coercive margin. -/
theorem localized_packet_diagonal_coercive_v1
    (g : WeilCompactSmoothGV1)
    (hwindow : LogWindowContainsV1 g (1 / 128 : ℝ)) :
    (32 / 25 : ℝ) * AEGIS.WeilDisjointEnergyV2.energy g.1 ≤ -(B g g).re := by
  have hw : WidthOneSixtyFourAt g 0 := by
    intro t ht
    have h := hwindow ht
    simpa only [zero_sub, zero_add] using h
  exact narrow_diagonal_32_over_25_v2 g 0 hw

end AEGIS.RHSmallWindowUnconditionalV1

#print axioms AEGIS.RHSmallWindowUnconditionalV1.narrowWindowArithmeticNonpositive_one_over_128_v1
#print axioms AEGIS.RHSmallWindowUnconditionalV1.localized_packet_diagonal_nonpositive_v1
#print axioms AEGIS.RHSmallWindowUnconditionalV1.localized_packet_diagonal_coercive_v1
