import Mathlib

/-!
AEGIS Ω — the moment-zero factorisation for the Krein dual certificate, V13.

In the logarithmic coordinate the two Weil moment conditions are `∫ G(y)·e^{±y/2} dy = 0`.
Put `G₁ = e^{−|·|/2} * G`, the Green's function of `1/4 − D²` applied to `G`, so that
`Ĝ₁(ξ) = Ĝ(ξ)/(ξ² + 1/4)`. If `G` vanishes outside `[a, b]` and both moments are zero, then
`G₁` also vanishes outside `[a, b]`. The reason is that on `x ≥ b` the kernel factors as
`e^{−x/2}·e^{y/2}`, and on `x ≤ a` as `e^{x/2}·e^{−y/2}`.

`kreinFactor_lift_support` states the same for the unitary log lift `G(t) = e^{t/2}·g(e^t)` of a
multiplicative `g` supported in `[e^a, e^b]`, under the repository's moment conditions
`∫_{x>0} g(x)/x dx = 0` and `∫_{x>0} g(x) dx = 0` (the two halves of `WeilMomentConditionsV1`).

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

/-- The unitary log lift `G(t) = e^{t/2}·g(e^t)` (same as `WeilLogCoordinateIsometryV21.logLift`). -/
def lift (g : ℝ → ℂ) (t : ℝ) : ℂ := (Real.exp (t / 2) : ℂ) * g (Real.exp t)

/-- Whole-line exponential substitution for complex-valued integrands. -/
theorem integral_exp_subst (f : ℝ → ℂ) :
    (∫ t : ℝ, (Real.exp t : ℂ) * f (Real.exp t)) = ∫ x in Ioi (0 : ℝ), f x := by
  have hcov :=
    MeasureTheory.integral_image_eq_integral_abs_deriv_smul
      (f := Real.exp) (f' := Real.exp) (s := Set.univ) MeasurableSet.univ
      (fun x _ => (Real.hasDerivAt_exp x).hasDerivWithinAt)
      (Set.injOn_of_injective Real.exp_injective) f
  rw [Set.image_univ, Real.range_exp] at hcov
  rw [hcov, Measure.restrict_univ]
  congr 1
  funext t
  rw [abs_of_pos (Real.exp_pos t), Complex.real_smul]

/-- `∫ e^{t/2}·G(t) dt = ∫_{x>0} g(x) dx`. -/
theorem lift_moment_plus (g : ℝ → ℂ) :
    (∫ t, (Real.exp (t / 2) : ℂ) * lift g t) = ∫ x in Ioi (0 : ℝ), g x := by
  rw [← integral_exp_subst]
  congr 1
  funext t
  unfold lift
  rw [← mul_assoc, ← Complex.ofReal_mul, ← Real.exp_add]
  congr 3
  ring

/-- `∫ e^{−t/2}·G(t) dt = ∫_{x>0} g(x)/x dx`. -/
theorem lift_moment_minus (g : ℝ → ℂ) :
    (∫ t, (Real.exp (-t / 2) : ℂ) * lift g t) = ∫ x in Ioi (0 : ℝ), g x / (x : ℂ) := by
  rw [← integral_exp_subst]
  congr 1
  funext t
  unfold lift
  have hne : (Real.exp t : ℂ) ≠ 0 := Complex.ofReal_ne_zero.mpr (Real.exp_pos t).ne'
  rw [← mul_assoc, ← Complex.ofReal_mul, ← Real.exp_add]
  have h0 : -t / 2 + t / 2 = 0 := by ring
  rw [h0, Real.exp_zero, Complex.ofReal_one, one_mul]
  field_simp

/-- The repository's two moment conditions, for `g` supported in `[e^a, e^b]`, make
`e^{−|·|/2} * G` vanish outside `(a, b)`, where `G` is the unitary log lift of `g`. -/
theorem kreinFactor_lift_support (g : ℝ → ℂ) (a b : ℝ)
    (hsupp : ∀ x, g x ≠ 0 → x ∈ Icc (Real.exp a) (Real.exp b))
    (hinv : ∫ x in Ioi (0 : ℝ), g x / (x : ℂ) = 0)
    (hone : ∫ x in Ioi (0 : ℝ), g x = 0) :
    ∀ t, kreinFactor (lift g) t ≠ 0 → t ∈ Ioo a b := by
  refine kreinFactor_support (lift g) a b ?_ (by rw [lift_moment_plus]; exact hone)
    (by rw [lift_moment_minus]; exact hinv)
  intro t ht
  have hg : g (Real.exp t) ≠ 0 := by
    intro h0; apply ht; simp [lift, h0]
  have hmem := hsupp _ hg
  exact ⟨Real.exp_le_exp.mp hmem.1, Real.exp_le_exp.mp hmem.2⟩

end AEGIS.RHKreinFactorV13

#print axioms AEGIS.RHKreinFactorV13.kreinFactor_support
#print axioms AEGIS.RHKreinFactorV13.kreinFactor_lift_support
