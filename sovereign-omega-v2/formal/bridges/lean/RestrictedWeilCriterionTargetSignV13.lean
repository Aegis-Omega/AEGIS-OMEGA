import RestrictedWeilCriterionKernelBridgeV10
import RestrictedWeilCriterionResidueWitnessV11
import Mathlib.Tactic

/-!
AEGIS Omega -- target-local translated-sign ABI V13.

The restricted-Weil forward direction does not require the universal final sign
on every moment-zero packet.  For a fixed packet g it uses the sign only on the
two-point translation span

  g + c * T_d g,   d : R, c : C.

This module isolates exactly that weaker hypothesis and derives the same
translated-kernel component and norm bounds used by the Laplace/pole lane.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set Filter Complex
open scoped ComplexConjugate

set_option autoImplicit false
noncomputable section

namespace AEGIS.RestrictedWeilCriterionTargetSignV13

open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.RestrictedWeilCriterionKernelBridgeV10
open AEGIS.RestrictedWeilCriterionResidueWitnessV11
open AEGIS.RestrictedWeilCriterionZeroKernelV10

def TwoPointTranslateSignV13 (g : WeilCompactSmoothGV1) : Prop :=
  ∀ (d : ℝ) (c : ℂ),
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (TwoPointPacketV1 g (translatePacket g d) c))).re ≤ 0

theorem twoPoint_translate_sign_implies_component_bounds_v13
    (g : WeilCompactSmoothGV1)
    (hsign : TwoPointTranslateSignV13 g)
    (d : ℝ) :
    ArithmeticComponentBoundsV1 g (translatePacket g d) := by
  apply
    (weil_four_phase_nonnegative_iff_components_v1
      (ArithmeticDiagonalV1 g)
      (ArithmeticCrossV1 g (translatePacket g d))).mp
  intro c hc
  have hs := hsign d c
  have hdiag :
      (B (translatePacket g d) (translatePacket g d)).re =
        (B g g).re := by
    rw [translate_B_diagonal_eq_v10]
  have hexact :=
    neg_actual_two_point_eq_weil_two_point_v1
      g (translatePacket g d) c hdiag
  rw [← hexact]
  linarith

theorem twoPoint_translate_sign_implies_kernel_bounded_v13
    (g : WeilCompactSmoothGV1)
    (hsign : TwoPointTranslateSignV13 g) :
    ∀ d : ℝ,
      ‖TranslatedArithmeticKernelV10 g d‖ ≤
        2 * TranslatedArithmeticDiagonalV10 g := by
  intro d
  exact translated_component_bounds_imply_norm_bound_v10 g d
    (twoPoint_translate_sign_implies_component_bounds_v13 g hsign d)

/-- The exact witness-level obligation needed by the restricted-Weil pole
contradiction: one moment-zero packet sees rho with nonzero residue coefficient
and its two-point translation span has the required sign. -/
def ResidueWitnessTranslateSignV13
    (rho : RiemannNontrivialZeroIndexV2) : Prop :=
  ∃ g : WeilCompactSmoothGV1,
    WeilMomentConditionsV1 g ∧
    ZeroCoefficientV10 g rho ≠ 0 ∧
    TwoPointTranslateSignV13 g

/-- The existing residue construction already discharges the first two pieces;
only target-local translated sign remains as a new mathematical obligation. -/
theorem residue_witness_exists_without_sign_v13
    (rho : RiemannNontrivialZeroIndexV2) :
    ∃ g : WeilCompactSmoothGV1,
      WeilMomentConditionsV1 g ∧
      ZeroCoefficientV10 g rho ≠ 0 := by
  exact
    AEGIS.RestrictedWeilCriterionResidueCoefficientV11
      .exists_nonzero_zero_coefficient_v11 rho

end AEGIS.RestrictedWeilCriterionTargetSignV13

#print axioms AEGIS.RestrictedWeilCriterionTargetSignV13.twoPoint_translate_sign_implies_component_bounds_v13
#print axioms AEGIS.RestrictedWeilCriterionTargetSignV13.twoPoint_translate_sign_implies_kernel_bounded_v13
#print axioms AEGIS.RestrictedWeilCriterionTargetSignV13.residue_witness_exists_without_sign_v13
