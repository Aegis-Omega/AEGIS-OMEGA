import Mathlib.Tactic

/-!
AEGIS Omega -- exact rational ten-block comparison certificate V1.

Pure finite algebra for a ten-block Hermitian comparison problem with:
- diagonal lower bound 5671/3200;
- baseline off-diagonal norm envelope 1/100 for all pairs;
- one distinguished endpoint pair (0,9) with envelope 57/100.

The distinguished pair is represented as the baseline 1/100 contribution
plus an extra 14/25. The exact SOS identity leaves coercive margin 3591/3200.

No repository-B binding, packet construction, globalization, universal Weil
sign, or RH conclusion is asserted here.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHTenBlockComparisonV1

def energy10 (x0 : ℝ) (x1 : ℝ) (x2 : ℝ) (x3 : ℝ) (x4 : ℝ) (x5 : ℝ) (x6 : ℝ) (x7 : ℝ) (x8 : ℝ) (x9 : ℝ) : ℝ :=
  x0 ^ 2 + x1 ^ 2 + x2 ^ 2 + x3 ^ 2 + x4 ^ 2 + x5 ^ 2 + x6 ^ 2 + x7 ^ 2 + x8 ^ 2 + x9 ^ 2

def pairSum10 (x0 : ℝ) (x1 : ℝ) (x2 : ℝ) (x3 : ℝ) (x4 : ℝ) (x5 : ℝ) (x6 : ℝ) (x7 : ℝ) (x8 : ℝ) (x9 : ℝ) : ℝ :=
  x0 * x1 +
      x0 * x2 +
      x0 * x3 +
      x0 * x4 +
      x0 * x5 +
      x0 * x6 +
      x0 * x7 +
      x0 * x8 +
      x0 * x9 +
      x1 * x2 +
      x1 * x3 +
      x1 * x4 +
      x1 * x5 +
      x1 * x6 +
      x1 * x7 +
      x1 * x8 +
      x1 * x9 +
      x2 * x3 +
      x2 * x4 +
      x2 * x5 +
      x2 * x6 +
      x2 * x7 +
      x2 * x8 +
      x2 * x9 +
      x3 * x4 +
      x3 * x5 +
      x3 * x6 +
      x3 * x7 +
      x3 * x8 +
      x3 * x9 +
      x4 * x5 +
      x4 * x6 +
      x4 * x7 +
      x4 * x8 +
      x4 * x9 +
      x5 * x6 +
      x5 * x7 +
      x5 * x8 +
      x5 * x9 +
      x6 * x7 +
      x6 * x8 +
      x6 * x9 +
      x7 * x8 +
      x7 * x9 +
      x8 * x9

def cross10 (x0 : ℝ) (x1 : ℝ) (x2 : ℝ) (x3 : ℝ) (x4 : ℝ) (x5 : ℝ) (x6 : ℝ) (x7 : ℝ) (x8 : ℝ) (x9 : ℝ) : ℝ :=
  (2 / 100 : ℝ) * pairSum10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 +
    (28 / 25 : ℝ) * x0 * x9

def comparisonSOS10 (x0 : ℝ) (x1 : ℝ) (x2 : ℝ) (x3 : ℝ) (x4 : ℝ) (x5 : ℝ) (x6 : ℝ) (x7 : ℝ) (x8 : ℝ) (x9 : ℝ) : ℝ :=
  (1 / 100 : ℝ) * (
      (x0 - x1) ^ 2 +
      (x0 - x2) ^ 2 +
      (x0 - x3) ^ 2 +
      (x0 - x4) ^ 2 +
      (x0 - x5) ^ 2 +
      (x0 - x6) ^ 2 +
      (x0 - x7) ^ 2 +
      (x0 - x8) ^ 2 +
      (x0 - x9) ^ 2 +
      (x1 - x2) ^ 2 +
      (x1 - x3) ^ 2 +
      (x1 - x4) ^ 2 +
      (x1 - x5) ^ 2 +
      (x1 - x6) ^ 2 +
      (x1 - x7) ^ 2 +
      (x1 - x8) ^ 2 +
      (x1 - x9) ^ 2 +
      (x2 - x3) ^ 2 +
      (x2 - x4) ^ 2 +
      (x2 - x5) ^ 2 +
      (x2 - x6) ^ 2 +
      (x2 - x7) ^ 2 +
      (x2 - x8) ^ 2 +
      (x2 - x9) ^ 2 +
      (x3 - x4) ^ 2 +
      (x3 - x5) ^ 2 +
      (x3 - x6) ^ 2 +
      (x3 - x7) ^ 2 +
      (x3 - x8) ^ 2 +
      (x3 - x9) ^ 2 +
      (x4 - x5) ^ 2 +
      (x4 - x6) ^ 2 +
      (x4 - x7) ^ 2 +
      (x4 - x8) ^ 2 +
      (x4 - x9) ^ 2 +
      (x5 - x6) ^ 2 +
      (x5 - x7) ^ 2 +
      (x5 - x8) ^ 2 +
      (x5 - x9) ^ 2 +
      (x6 - x7) ^ 2 +
      (x6 - x8) ^ 2 +
      (x6 - x9) ^ 2 +
      (x7 - x8) ^ 2 +
      (x7 - x9) ^ 2 +
      (x8 - x9) ^ 2) +
  (14 / 25 : ℝ) * (
      (x0 - x9) ^ 2 +
      x1 ^ 2 + x2 ^ 2 + x3 ^ 2 + x4 ^ 2 + x5 ^ 2 + x6 ^ 2 + x7 ^ 2 + x8 ^ 2)

theorem comparison_sos_identity_ten_v1 (x0 : ℝ) (x1 : ℝ) (x2 : ℝ) (x3 : ℝ) (x4 : ℝ) (x5 : ℝ) (x6 : ℝ) (x7 : ℝ) (x8 : ℝ) (x9 : ℝ) :
    (5671 / 3200 : ℝ) * energy10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 -
      cross10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 -
      (3591 / 3200 : ℝ) * energy10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 =
        comparisonSOS10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 := by
  unfold energy10 pairSum10 cross10 comparisonSOS10
  ring

theorem comparison_sos_nonnegative_ten_v1 (x0 : ℝ) (x1 : ℝ) (x2 : ℝ) (x3 : ℝ) (x4 : ℝ) (x5 : ℝ) (x6 : ℝ) (x7 : ℝ) (x8 : ℝ) (x9 : ℝ) :
    0 ≤ comparisonSOS10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 := by
  unfold comparisonSOS10
  positivity

theorem cross_ten_le_thirteen_over_twenty_v1 (x0 : ℝ) (x1 : ℝ) (x2 : ℝ) (x3 : ℝ) (x4 : ℝ) (x5 : ℝ) (x6 : ℝ) (x7 : ℝ) (x8 : ℝ) (x9 : ℝ) :
    cross10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 ≤
      (13 / 20 : ℝ) * energy10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 := by
  have hi := comparison_sos_identity_ten_v1 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9
  have hp := comparison_sos_nonnegative_ten_v1 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9
  linarith

theorem diagonal_5671_over_3200_margin_ten_v1 (x0 : ℝ) (x1 : ℝ) (x2 : ℝ) (x3 : ℝ) (x4 : ℝ) (x5 : ℝ) (x6 : ℝ) (x7 : ℝ) (x8 : ℝ) (x9 : ℝ) :
    (3591 / 3200 : ℝ) * energy10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 ≤
      (5671 / 3200 : ℝ) * energy10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 -
        cross10 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9 := by
  have hi := comparison_sos_identity_ten_v1 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9
  have hp := comparison_sos_nonnegative_ten_v1 x0 x1 x2 x3 x4 x5 x6 x7 x8 x9
  linarith

end AEGIS.RHTenBlockComparisonV1

#print axioms AEGIS.RHTenBlockComparisonV1.comparison_sos_identity_ten_v1
#print axioms AEGIS.RHTenBlockComparisonV1.comparison_sos_nonnegative_ten_v1
#print axioms AEGIS.RHTenBlockComparisonV1.cross_ten_le_thirteen_over_twenty_v1
#print axioms AEGIS.RHTenBlockComparisonV1.diagonal_5671_over_3200_margin_ten_v1
