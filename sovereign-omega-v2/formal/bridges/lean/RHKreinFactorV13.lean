import Mathlib

/-!
AEGIS Ω — the moment-zero factorisation for the Krein dual certificate, V13.

In the logarithmic coordinate the two Weil moment conditions are `∫ G(y)·e^{±y/2} dy = 0`.
Put `G₁ = e^{−|·|/2} * G`, the Green's function of `1/4 − D²` applied to `G`, so that
`Ĝ₁(ξ) = Ĝ(ξ)/(ξ² + 1/4)`. If `G` vanishes outside `[a, b]` and both moments are zero, then
`G₁` also vanishes outside `[a, b]`. The reason is that on `x ≥ b` the kernel factors as
`e^{−x/2}·e^{y/2}`, and on `x ≤ a` as `e^{x/2}·e^{−y/2}`.

This is the support half of the factorisation `g = (1/4 − D²)g₁` used by the Fourier-side
certificate in `RH_STATUS.md`. Not RH. AUTHORITY_EFFECT = NONE.
-/

open Set MeasureTheory
set_option autoImplicit false
noncomputable section

namespace AEGIS.RHKreinFactorV13

/-- `G₁(x) = ∫ e^{−|x − y|/2}·G(y) dy`. -/
def kreinFactor (G : ℝ → ℂ) (x : ℝ) : ℂ :=
  ∫ y, (Real.exp (-(|x - y|) / 2) : ℂ) * G y

theorem kreinFactor_eq_zero_of_le (G : ℝ → ℂ) (a b : ℝ)
    (hsupp : ∀ y, G y ≠ 0 → y ∈ Icc a b)
    (hmom : ∫ y, (Real.exp (y / 2) : ℂ) * G y = 0) {x : ℝ} (hx : b ≤ x) :
    kreinFactor G x = 0 := by
  have hpt : ∀ y, (Real.exp (-(|x - y|) / 2) : ℂ) * G y =
      (Real.exp (-x / 2) : ℂ) * ((Real.exp (y / 2) : ℂ) * G y) := by
    intro y
    by_cases hG : G y = 0
    · simp [hG]
    · have hy : y ≤ x := le_trans (hsupp y hG).2 hx
      have habs : |x - y| = x - y := abs_of_nonneg (by linarith)
      rw [habs, ← mul_assoc, ← Complex.ofReal_mul, ← Real.exp_add]
      congr 3
      ring
  unfold kreinFactor
  simp_rw [hpt]
  rw [integral_const_mul, hmom, mul_zero]

theorem kreinFactor_eq_zero_of_ge (G : ℝ → ℂ) (a b : ℝ)
    (hsupp : ∀ y, G y ≠ 0 → y ∈ Icc a b)
    (hmom : ∫ y, (Real.exp (-y / 2) : ℂ) * G y = 0) {x : ℝ} (hx : x ≤ a) :
    kreinFactor G x = 0 := by
  have hpt : ∀ y, (Real.exp (-(|x - y|) / 2) : ℂ) * G y =
      (Real.exp (x / 2) : ℂ) * ((Real.exp (-y / 2) : ℂ) * G y) := by
    intro y
    by_cases hG : G y = 0
    · simp [hG]
    · have hy : x ≤ y := le_trans hx (hsupp y hG).1
      have habs : |x - y| = y - x := by rw [abs_sub_comm]; exact abs_of_nonneg (by linarith)
      rw [habs, ← mul_assoc, ← Complex.ofReal_mul, ← Real.exp_add]
      congr 3
      ring
  unfold kreinFactor
  simp_rw [hpt]
  rw [integral_const_mul, hmom, mul_zero]

/-- Both moments zero and `G` supported in `[a, b]`: `G₁ = e^{−|·|/2} * G` is supported in `[a, b]`. -/
theorem kreinFactor_support (G : ℝ → ℂ) (a b : ℝ)
    (hsupp : ∀ y, G y ≠ 0 → y ∈ Icc a b)
    (hplus : ∫ y, (Real.exp (y / 2) : ℂ) * G y = 0)
    (hminus : ∫ y, (Real.exp (-y / 2) : ℂ) * G y = 0) :
    ∀ x, kreinFactor G x ≠ 0 → x ∈ Ioo a b := by
  intro x hx
  refine ⟨?_, ?_⟩
  · by_contra h
    exact hx (kreinFactor_eq_zero_of_ge G a b hsupp hminus (not_lt.mp h))
  · by_contra h
    exact hx (kreinFactor_eq_zero_of_le G a b hsupp hplus (not_lt.mp h))

end AEGIS.RHKreinFactorV13

#print axioms AEGIS.RHKreinFactorV13.kreinFactor_support
