import RHFourBlockBoundObstructionV1
import Mathlib.Tactic

/-!
AEGIS Ω — historical equal-coefficient four-block scalar budget v1.

Scope correction: 9/8 is ONLY the equal-coefficient scalar threshold after
omitting the farthest pair. It is NOT an all-coefficient PSD or Gershgorin
threshold. The existing theorem statements below remain unchanged for
compatibility. Their arithmetic is valid; the earlier general interpretation
was not. RHFourBlockComparisonV2 contains the exact counterexample and the
complete six-pair sum-of-squares certificate.

The 19/200 number is the increment from 103/100 to this truncated scalar
threshold, not a sufficient analytic residual for arbitrary four-block tests.
No stronger diagonal estimate, global Weil sign, or RH is asserted.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

set_option autoImplicit false

namespace AEGIS.RHFourBlockMarginV1

/-- Historical name: equal-coefficient truncated scalar threshold only. -/
theorem four_block_required_diagonal_v1 :
    (2 * (3 * ((51 : ℝ) / 100) + 2 * ((9 : ℝ) / 25))) / 4 =
      (9 : ℝ) / 8 := by
  norm_num

/-- Increment to the truncated equal-coefficient threshold, not a PSD proof. -/
theorem four_block_required_increment_v1 :
    (9 : ℝ) / 8 - (103 : ℝ) / 100 = (19 : ℝ) / 200 := by
  norm_num

/-- Closes only the displayed scalar inequality. This statement has neither
four arbitrary coefficients nor a bound for the farthest pair. -/
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

/-- Preserved arithmetic identity with the corrected scalar-only scope. -/
theorem current_plus_missing_margin_eq_required_v1 :
    (103 : ℝ) / 100 + (19 : ℝ) / 200 = (9 : ℝ) / 8 := by
  norm_num

end AEGIS.RHFourBlockMarginV1

#print axioms AEGIS.RHFourBlockMarginV1.four_block_required_diagonal_v1
#print axioms AEGIS.RHFourBlockMarginV1.four_block_required_increment_v1
#print axioms AEGIS.RHFourBlockMarginV1.four_block_budget_closes_at_nine_eighths_v1
#print axioms AEGIS.RHFourBlockMarginV1.current_plus_missing_margin_eq_required_v1
