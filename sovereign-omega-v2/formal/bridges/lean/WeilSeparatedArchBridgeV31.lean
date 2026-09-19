import WeilThreeBlockCrossAssemblyV30
import Mathlib.MeasureTheory.Integral.Prod

/-!
Separated Archimedean bridge for the actual mixed correlation.
Moment transport below derives the weighted correlation integral from the
repository moments, including compact support and the Fubini justification.
No global Weil sign or RH conclusion is asserted.
-/

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators
set_option autoImplicit false
noncomputable section
namespace AEGIS.WeilSeparatedArchBridgeV31
open AEGIS.WeilMixedClosureV2
open AEGIS.WeilLogCoordinateIsometryV21
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilThreeBlockCrossPrimeV28

theorem logLift_continuous (p : WeilCompactSmoothGV1) :
    Continuous (logLift p.1) := by
  unfold logLift
  exact (by fun_prop : Continuous (fun t : ℝ => (Real.exp (t / 2) : ℂ))).mul
    (p.2.1.continuous.comp Real.continuous_exp)

theorem logCross_continuous (p q : WeilCompactSmoothGV1) :
    Continuous (logCrossV28 p q) := by
  simp_rw [logCross_eq_mixed_v28]
  exact (by fun_prop : Continuous (fun u : ℝ => (Real.exp (u / 2) : ℂ))).mul
    ((smooth p q).continuous.comp Real.continuous_exp)

theorem logCross_zero_outside
    (p q : WeilCompactSmoothGV1) (plo phi qlo qhi u : ℝ)
    (hp : LogSupportIn p plo phi) (hq : LogSupportIn q qlo qhi)
    (hu : u < plo - qhi ∨ phi - qlo < u) : logCrossV28 p q u = 0 := by
  unfold logCrossV28
  apply integral_eq_zero_of_ae
  filter_upwards [] with v
  by_cases hp0 : logLift p.1 (v + u) = 0
  · simp [hp0]
  by_cases hq0 : logLift q.1 v = 0
  · simp [hq0]
  have hpI := hp (subset_tsupport _ hp0)
  have hqI := hq (subset_tsupport _ hq0)
  exfalso
  rcases hu with hu | hu <;> linarith [hpI.1, hpI.2, hqI.1, hqI.2]

def weightedCrossIntegrand
    (p q : WeilCompactSmoothGV1) (λ : ℝ) (z : ℝ × ℝ) : ℂ :=
  (Real.exp (λ * z.1) : ℂ) * logLift p.1 (z.2 + z.1) * conj (logLift q.1 z.2)

theorem weightedCrossIntegrand_integrable
    (p q : WeilCompactSmoothGV1) (λ plo phi qlo qhi : ℝ)
    (hp : LogSupportIn p plo phi) (hq : LogSupportIn q qlo qhi) :
    Integrable (weightedCrossIntegrand p q λ) (volume.prod volume) := by
  have hc : Continuous (weightedCrossIntegrand p q λ) := by
    unfold weightedCrossIntegrand
    exact ((by fun_prop : Continuous (fun z : ℝ × ℝ =>
      (Real.exp (λ * z.1) : ℂ))).mul
      ((logLift_continuous p).comp (continuous_snd.add continuous_fst))).mul
      (continuous_conj.comp ((logLift_continuous q).comp continuous_snd))
  have hk : HasCompactSupport (weightedCrossIntegrand p q λ) := by
    apply HasCompactSupport.of_support_subset_isCompact
      ((isCompact_Icc : IsCompact (Icc (plo - qhi) (phi - qlo))).prod
        (isCompact_Icc : IsCompact (Icc qlo qhi)))
    intro z hz
    have hp0 : logLift p.1 (z.2 + z.1) ≠ 0 := by
      intro h
      exact hz (by simp [weightedCrossIntegrand, h])
    have hq0 : logLift q.1 z.2 ≠ 0 := by
      intro h
      exact hz (by simp [weightedCrossIntegrand, h])
    have hpI := hp (subset_tsupport _ hp0)
    have hqI := hq (subset_tsupport _ hq0)
    exact ⟨⟨by linarith [hpI.1, hqI.2], by linarith [hpI.2, hqI.1]⟩, hqI⟩
  exact hc.integrable_of_hasCompactSupport hk

theorem weighted_logCross_integrable
    (p q : WeilCompactSmoothGV1) (λ plo phi qlo qhi : ℝ)
    (hp : LogSupportIn p plo phi) (hq : LogSupportIn q qlo qhi) :
    Integrable (fun u : ℝ => (Real.exp (λ * u) : ℂ) * logCrossV28 p q u) := by
  have hi := (weightedCrossIntegrand_integrable p q λ plo phi qlo qhi hp hq).integral_prod_left
  simpa only [weightedCrossIntegrand, logCrossV28, mul_assoc, integral_const_mul] using hi

/-- Fubini and additive translation transport a zero weighted packet moment
to a zero weighted mixed-correlation moment. -/
theorem weighted_logCross_moment_zero
    (p q : WeilCompactSmoothGV1) (λ plo phi qlo qhi : ℝ)
    (hp : LogSupportIn p plo phi) (hq : LogSupportIn q qlo qhi)
    (hm : (∫ s : ℝ, (Real.exp (λ * s) : ℂ) * logLift p.1 s) = 0) :
    (∫ u : ℝ, (Real.exp (λ * u) : ℂ) * logCrossV28 p q u) = 0 := by
  have hi := weightedCrossIntegrand_integrable p q λ plo phi qlo qhi hp hq
  calc
    (∫ u : ℝ, (Real.exp (λ * u) : ℂ) * logCrossV28 p q u) =
        ∫ u : ℝ, ∫ v : ℝ, weightedCrossIntegrand p q λ (u, v) := by
      simp only [weightedCrossIntegrand, logCrossV28, mul_assoc, integral_const_mul]
    _ = ∫ v : ℝ, ∫ u : ℝ, weightedCrossIntegrand p q λ (u, v) :=
      integral_integral_swap hi
    _ = 0 := by
      apply integral_eq_zero_of_ae
      filter_upwards [] with v
      have he (u : ℝ) : Real.exp (λ * u) =
          Real.exp (-λ * v) * Real.exp (λ * (u + v)) := by
        rw [← Real.exp_add]
        congr 1
        ring
      have hinner : (∫ u : ℝ, weightedCrossIntegrand p q λ (u, v)) =
          (Real.exp (-λ * v) : ℂ) *
            (∫ u : ℝ, (Real.exp (λ * (u + v)) : ℂ) * logLift p.1 (u + v)) *
              conj (logLift q.1 v) := by
        rw [← integral_mul_const, ← integral_const_mul]
        apply integral_congr_ae
        filter_upwards [] with u
        unfold weightedCrossIntegrand
        rw [he u, Complex.ofReal_mul, add_comm v u]
        ring
      rw [hinner, integral_add_right_eq_self, hm, mul_zero, zero_mul]

theorem logCross_plus_moment_zero
    (p q : WeilCompactSmoothGV1) (plo phi qlo qhi : ℝ)
    (hp : LogSupportIn p plo phi) (hq : LogSupportIn q qlo qhi)
    (hm : WeilMomentConditionsV1 p) :
    (∫ u : ℝ, (Real.exp (u / 2) : ℂ) * logCrossV28 p q u) = 0 := by
  have hz : (∫ s : ℝ, (Real.exp ((1 / 2 : ℝ) * s) : ℂ) * logLift p.1 s) = 0 := by
    simpa only [one_div_mul_eq_div] using
      (logMomentPlus_eq_repository p).trans hm.2
  simpa only [one_div_mul_eq_div] using
    weighted_logCross_moment_zero p q (1 / 2) plo phi qlo qhi hp hq hz

theorem logCross_minus_moment_zero
    (p q : WeilCompactSmoothGV1) (plo phi qlo qhi : ℝ)
    (hp : LogSupportIn p plo phi) (hq : LogSupportIn q qlo qhi)
    (hm : WeilMomentConditionsV1 p) :
    (∫ u : ℝ, (Real.exp (-u / 2) : ℂ) * logCrossV28 p q u) = 0 := by
  have hz : (∫ s : ℝ, (Real.exp ((-1 / 2 : ℝ) * s) : ℂ) * logLift p.1 s) = 0 := by
    convert (logMomentMinus_eq_repository p).trans hm.1 using 1
    unfold logMomentMinus
    congr 1
    funext s
    congr 2
    ring
  convert weighted_logCross_moment_zero p q (-1 / 2) plo phi qlo qhi hp hq hz using 1
  congr 1
  funext u
  congr 2
  ring

private theorem kernel_algebra (x y z w m : ℂ)
    (hx : x ≠ 0) (hd : 1 - w ≠ 0)
    (hy : y = x⁻¹) (hz : z * z = y) (hw : x * w = y) :
    x * ((1 / x * m) / (x - y)) = z / (1 - w) * (z * m) := by
  have hden : x - y = x * (1 - w) := by rw [mul_sub, mul_one, hw]
  calc
    x * ((1 / x * m) / (x - y)) = x⁻¹ * m / (1 - w) := by
      rw [hden]
      field_simp [hx, hd]
      <;> ring
    _ = y * m / (1 - w) := by rw [hy]
    _ = z / (1 - w) * (z * m) := by rw [← hz]; ring

/-- Exact conversion of the repository Archimedean integral for strictly
ordered logarithmic supports. Both centre and positive-displacement terms
vanish by support; the surviving term has the stated negative log shift. -/
theorem separated_arch_eq_log_kernel
    (p q : WeilCompactSmoothGV1) (plo phi qlo qhi : ℝ)
    (hp : LogSupportIn p plo phi) (hq : LogSupportIn q qlo qhi)
    (hsep : phi < qlo) :
    WeilArchimedeanIntegralV1 (mixed p q) =
      ∫ u in Ioi (0 : ℝ),
        ((Real.exp (-u / 2) / (1 - Real.exp (-2 * u)) : ℝ) : ℂ) *
          logCrossV28 p q (-u) := by
  have hzero (u : ℝ) (hu : 0 ≤ u) : mixed p q (Real.exp u) = 0 := by
    have hc := logCross_zero_outside p q plo phi qlo qhi u hp hq
      (Or.inr (by linarith))
    rw [logCross_eq_mixed_v28] at hc
    exact (mul_eq_zero.mp hc).resolve_left (by simp)
  have hcenter : mixed p q 1 = 0 := by simpa using hzero 0 le_rfl
  unfold WeilArchimedeanIntegralV1
  rw [← show (∫ u in Ioi (0 : ℝ), Real.exp u •
      WeilArchimedeanIntegrandV1 (mixed p q) (Real.exp u)) =
        ∫ x in Ioi (1 : ℝ), WeilArchimedeanIntegrandV1 (mixed p q) x from
      by simpa using (integral_comp_exp_Ioi (WeilArchimedeanIntegrandV1 (mixed p q)) 0)]
  apply setIntegral_congr_fun measurableSet_Ioi
  intro u hu
  have heinv : (Real.exp u)⁻¹ = Real.exp (-u) := (Real.exp_neg u).symm
  simp only [WeilArchimedeanIntegrandV1, hzero u hu.le, hcenter,
    mul_zero, sub_zero, zero_add, Complex.real_smul, heinv,
    logCross_eq_mixed_v28, neg_div, Complex.ofReal_div, Complex.ofReal_sub,
    Complex.ofReal_one]
  apply kernel_algebra
  · simp
  · exact_mod_cast (ne_of_gt (sub_pos.mpr
      (Real.exp_lt_one_iff.mpr (by linarith))) : (1 - Real.exp (-2 * u) : ℝ) ≠ 0)
  · simp [Real.exp_neg]
  · rw [← Complex.ofReal_mul]
    congr 1
    rw [← Real.exp_add]
    congr 1
    ring
  · rw [← Complex.ofReal_mul]
    congr 1
    rw [← Real.exp_add]
    congr 1
    ring

end AEGIS.WeilSeparatedArchBridgeV31

#print axioms AEGIS.WeilSeparatedArchBridgeV31.weightedCrossIntegrand_integrable
#print axioms AEGIS.WeilSeparatedArchBridgeV31.weighted_logCross_integrable
#print axioms AEGIS.WeilSeparatedArchBridgeV31.weighted_logCross_moment_zero
#print axioms AEGIS.WeilSeparatedArchBridgeV31.logCross_plus_moment_zero
#print axioms AEGIS.WeilSeparatedArchBridgeV31.logCross_minus_moment_zero
#print axioms AEGIS.WeilSeparatedArchBridgeV31.separated_arch_eq_log_kernel
