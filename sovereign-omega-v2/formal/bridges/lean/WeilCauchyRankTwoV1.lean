import WeilFiniteSourceCalculusV1
import Mathlib.Tactic

/-!
AEGIS Ω — rank-two Cauchy entry algebra v1.

This file isolates only the algebraic Cauchy factorization used by the
Archimedean Gram lane. It does not identify the actual Archimedean source or
tail with this kernel, does not import finite PSD, and makes no global Weil or
RH claim.
-/

set_option autoImplicit false

noncomputable section

/-- Rational core whose divided difference produces the rank-two Cauchy
kernel. -/
def WeilCauchyCoreV1 (a x : ℝ) : ℝ :=
  x / ((a - x) * (a + x))

/-- Symmetric rank-two Cauchy kernel, written as the average of the two feature
products corresponding to poles at `+a` and `-a`. -/
def WeilCauchyRankTwoKernelV1 (a x y : ℝ) : ℝ :=
  (1 / 2 : ℝ) *
    (1 / ((a - x) * (a - y)) +
      1 / ((a + x) * (a + y)))

/-- Off the diagonal, the divided difference of `x / (a² - x²)` is exactly the
rank-two Cauchy kernel. -/
theorem weil_cauchy_divided_difference_rank_two_v1
    (a x y : ℝ)
    (hxy : x ≠ y)
    (hamx : a - x ≠ 0) (hapx : a + x ≠ 0)
    (hamy : a - y ≠ 0) (hapy : a + y ≠ 0) :
    (WeilCauchyCoreV1 a x - WeilCauchyCoreV1 a y) / (x - y) =
      WeilCauchyRankTwoKernelV1 a x y := by
  have hxy0 : x - y ≠ 0 := sub_ne_zero.mpr hxy
  have hxden : (a - x) * (a + x) ≠ 0 := mul_ne_zero hamx hapx
  have hyden : (a - y) * (a + y) ≠ 0 := mul_ne_zero hamy hapy
  unfold WeilCauchyCoreV1 WeilCauchyRankTwoKernelV1
  field_simp [hxy0, hxden, hyden, hamx, hapx, hamy, hapy]
  ring

/-- The diagonal derivative value of the same rational core is exactly the
rank-two Cauchy kernel on the diagonal. -/
theorem weil_cauchy_diagonal_rank_two_v1
    (a x : ℝ)
    (hamx : a - x ≠ 0) (hapx : a + x ≠ 0) :
    (a ^ 2 + x ^ 2) / (((a - x) * (a + x)) ^ 2) =
      WeilCauchyRankTwoKernelV1 a x x := by
  have hxden : (a - x) * (a + x) ≠ 0 := mul_ne_zero hamx hapx
  unfold WeilCauchyRankTwoKernelV1
  field_simp [hxden, hamx, hapx]
  ring

#print axioms weil_cauchy_divided_difference_rank_two_v1
#print axioms weil_cauchy_diagonal_rank_two_v1
