import RHFourBlockBoundObstructionV1
import Mathlib.Tactic

/-!
AEGIS Ω — four-block margin target v1.

This isolates the exact scalar improvement required to extend the current
three-block absolute-cross certificate to four consecutive blocks, while
keeping the existing adjacent (51/100) and next-neighbour (9/25) bounds.

Current diagonal coercivity is 103/100.  The four-block absolute budget closes
exactly at 9/8, so the missing per-diagonal margin is 19/200.

This is a residual theorem only.  It does not assert that the stronger
diagonal estimate is available, and it does not assert global Weil sign or RH.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

set_option autoImplicit false

namespace AEGIS.RHFourBlockMarginV1

/-- Exact diagonal coefficient required by the current four-block
Gershgorin/absolute-cross aggregation. -/
theorem four_block_required_diagonal_v1 :
    (2 * (3 * ((51 : ℝ) / 100) + 2 * ((9 : ℝ) / 25))) / 4 =
      (9 : ℝ) / 8 := by
  norm_num

/-- Exact improvement over the current 103/100 diagonal certificate. -/
theorem four_block_required_increment_v1 :
    (9 : ℝ) / 8 - (103 : ℝ) / 100 = (19 : ℝ) / 200 := by
  norm_num

/-- A 9/8 diagonal lower bound is sufficient to close the four-block
absolute-cross scalar budget with the existing cross constants. -/
theorem four_block_budget_closes_at_nine_eighths_v1
    (E : ℝ) (hE : 0 ≤ E)
    (D : ℝ) (hD : (9 / 8 : ℝ) * E ≤ D) :
    2 * (3 * ((51 : ℝ) / 100) + 2 * ((9 : ℝ) / 25)) * E ≤
      4 * D := by
  have hscalar :
      2 * (3 * ((51 : ℝ) / 100) + 2 * ((9 : ℝ) / 25)) =
        4 * ((9 : ℝ) / 8) := by
    norm_num
  rw [hscalar]
  nlinarith

/-- Equivalent residual formulation: improving 103/100 by 19/200 reaches
exactly the four-block threshold. -/
theorem current_plus_missing_margin_eq_required_v1 :
    (103 : ℝ) / 100 + (19 : ℝ) / 200 = (9 : ℝ) / 8 := by
  norm_num

end AEGIS.RHFourBlockMarginV1

#print axioms AEGIS.RHFourBlockMarginV1.four_block_required_diagonal_v1
#print axioms AEGIS.RHFourBlockMarginV1.four_block_required_increment_v1
#print axioms AEGIS.RHFourBlockMarginV1.four_block_budget_closes_at_nine_eighths_v1
#print axioms AEGIS.RHFourBlockMarginV1.current_plus_missing_margin_eq_required_v1
