import WeilArchSineKernelIntegerV1
import Mathlib.Tactic

/-!
AEGIS Ω — pointwise finite Archimedean sine-source quadratic v1.

This module composes only already-proved pointwise ingredients:
- true Arch sine-source entry = `WeilArchScaleV1` times the rank-two Cauchy entry;
- the finite real Cauchy quadratic is nonnegative.

It remains pointwise in the spectral parameter `T`.  It does NOT perform the
continuous T-integration, bind the full Archimedean weight, prove tail operator
order, promote finite Galerkin PSD, prove the formula-to-Weil operator identity,
or prove RH.
-/

open scoped BigOperators

set_option autoImplicit false

noncomputable section

/-- Finite quadratic contraction of the true Archimedean sine-source entry on
the symmetric Galerkin band. -/
def WeilArchFiniteQuadraticV1
    (N : ℕ) (u : ℤ → ℝ) (L T : ℝ) : ℝ :=
  ∑ m ∈ Finset.Icc (-(N : ℤ)) (N : ℤ),
    ∑ n ∈ Finset.Icc (-(N : ℤ)) (N : ℤ),
      u m * u n * WeilArchSineEntryV1 L T m n

/-- On a band with no resonant denominator, the true Arch sine-source quadratic
is exactly its scalar factor times the already-proved finite Cauchy quadratic. -/
theorem weil_arch_finite_quadratic_scaled_cauchy_v1
    (N : ℕ) (u : ℤ → ℝ) (L T : ℝ) (hL : L ≠ 0)
    (hband : ∀ n ∈ Finset.Icc (-(N : ℤ)) (N : ℤ),
      T ^ 2 - (WeilArchRhoV1 L * (n : ℝ)) ^ 2 ≠ 0) :
    WeilArchFiniteQuadraticV1 N u L T =
      WeilArchScaleV1 L T *
        WeilCauchyFiniteQuadraticV1 N u (WeilArchNodeV1 L T) := by
  classical
  unfold WeilArchFiniteQuadraticV1 WeilCauchyFiniteQuadraticV1
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro m hm
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro n hn
  rw [weil_arch_sine_entry_cauchy_rank_two_v1
    L T m n hL (hband m hm) (hband n hn)]
  ring

/-- The pointwise Arch sine-source scale is nonnegative for positive `L`. -/
theorem weil_arch_scale_nonnegative_v1
    (L T : ℝ) (hL : 0 < L) :
    0 ≤ WeilArchScaleV1 L T := by
  have hrho : 0 < WeilArchRhoV1 L := by
    unfold WeilArchRhoV1
    exact div_pos (mul_pos (by norm_num) Real.pi_pos) hL
  unfold WeilArchScaleV1
  exact div_nonneg
    (mul_nonneg (by norm_num) (sq_nonneg (Real.sin (L * T / 2))))
    (le_of_lt hrho)

/-- Pointwise nonnegativity of the true finite Arch sine-source quadratic under
positive scale and band-wide nonresonance.  This is not the integrated
Archimedean tail-order theorem. -/
theorem weil_arch_finite_quadratic_nonnegative_v1
    (N : ℕ) (u : ℤ → ℝ) (L T : ℝ) (hL : 0 < L)
    (hband : ∀ n ∈ Finset.Icc (-(N : ℤ)) (N : ℤ),
      T ^ 2 - (WeilArchRhoV1 L * (n : ℝ)) ^ 2 ≠ 0) :
    0 ≤ WeilArchFiniteQuadraticV1 N u L T := by
  rw [weil_arch_finite_quadratic_scaled_cauchy_v1 N u L T hL.ne' hband]
  exact mul_nonneg
    (weil_arch_scale_nonnegative_v1 L T hL)
    (weil_cauchy_finite_quadratic_nonnegative_v1
      N u (WeilArchNodeV1 L T))

/-- Public bounded alias emphasizing that this is the true sine-source finite
quadratic, not the integrated Archimedean operator. -/
theorem weil_arch_sine_finite_quadratic_nonnegative_v1
    (N : ℕ) (u : ℤ → ℝ) (L T : ℝ) (hL : 0 < L)
    (hband : ∀ n ∈ Finset.Icc (-(N : ℤ)) (N : ℤ),
      T ^ 2 - (WeilArchRhoV1 L * (n : ℝ)) ^ 2 ≠ 0) :
    0 ≤ WeilArchFiniteQuadraticV1 N u L T :=
  weil_arch_finite_quadratic_nonnegative_v1 N u L T hL hband

#print axioms weil_arch_finite_quadratic_scaled_cauchy_v1
#print axioms weil_arch_scale_nonnegative_v1
#print axioms weil_arch_finite_quadratic_nonnegative_v1
#print axioms weil_arch_sine_finite_quadratic_nonnegative_v1
