import WeilDiagonalLogGainS1
import WeilSeparatedArchBridgeV31

/-!
# Diagonal log-gain at width 1/32 (transport of S1 to the repository diagonal)

For every retained width-1/32 packet (`WidthOneThirtyTwoAt g a`; no moment hypothesis):

  (103/100 + e^{−1/32} · log 2) · E ≤ −Re B(g, g).

V27 bounds the inner Archimedean window `∫_{(0,1/32]} widthArchLogIntegrandV26` by
`+E · diagonalSmallV21`, using only `‖C‖ ≤ E`. Writing the integrand as
`((e^{u/2} − 1)E − e^{u/2}(E − Re C(u)))/sinh u` keeps the nonnegative part
`E − Re C(u) = ½∫‖h(v+u) − h(v)‖²`, whose weighted integral S1 bounds below by `log 2 · E`.

Not a Weil-positivity statement for any class beyond the diagonal, and not RH.
-/

open MeasureTheory Set Complex
open scoped ComplexConjugate

noncomputable section

namespace AEGIS.WeilDiagonalLogGainV1

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilLogCoordinateIsometryV21
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilThreeBlockAnalyticConstantsV21
open AEGIS.WeilDiagonalKernelReductionV21
open AEGIS.WeilWidthDiagonalArchFrontierV24
open AEGIS.WeilWidthArchCorrelationV25
open AEGIS.WeilWidthArchBudgetV26
open AEGIS.WeilWidthArchIntegralV27

/-- `‖h(v+u) − h(v)‖²` integrates to `2E − 2 Re C(u)`. -/
theorem diff_sq_integral (g : WeilCompactSmoothGV1) (u : ℝ) :
    (∫ v : ℝ, ‖logLift g.1 (v + u) - logLift g.1 v‖ ^ 2) =
      2 * energy g.1 - 2 * (logCorrelationV25 g u).re := by
  have h0 : (∫ v : ℝ, ‖logLift g.1 v‖ ^ 2) = energy g.1 := by
    simpa using shifted_logLift_sq_integral_v25 g 0
  have hpt : (fun v : ℝ => ‖logLift g.1 (v + u) - logLift g.1 v‖ ^ 2) =
      fun v => ‖logLift g.1 (v + u)‖ ^ 2 + ‖logLift g.1 v‖ ^ 2 -
        2 * (logLift g.1 (v + u) * conj (logLift g.1 v)).re := by
    funext v
    simp only [Complex.sq_norm]
    rw [Complex.normSq_sub]
  have i1 := shifted_logLift_sq_integrable_v25 g u
  have i2 := logLift_sq_integrable_v25 g
  have i3 : Integrable (fun v : ℝ => (logLift g.1 (v + u) * conj (logLift g.1 v)).re) :=
    (logCorrelation_integrable_v25 g u).re
  have i12 : Integrable (fun v : ℝ => ‖logLift g.1 (v + u)‖ ^ 2 + ‖logLift g.1 v‖ ^ 2) :=
    i1.add i2
  have e1 := integral_sub i12 (i3.const_mul 2)
  have e2 := integral_add i1 i2
  have e3 := integral_const_mul (μ := volume) (2 : ℝ)
    (fun v : ℝ => (logLift g.1 (v + u) * conj (logLift g.1 v)).re)
  have e4 : (∫ v : ℝ, (logLift g.1 (v + u) * conj (logLift g.1 v)).re) =
      (logCorrelationV25 g u).re := by
    have := integral_re (logCorrelation_integrable_v25 g u)
    simpa [logCorrelationV25] using this
  rw [hpt, e1, e2, e3, e4, shifted_logLift_sq_integral_v25 g u, h0]
  ring

theorem diff_sq_integrable (g : WeilCompactSmoothGV1) (u : ℝ) :
    Integrable (fun v : ℝ => ‖logLift g.1 (v + u) - logLift g.1 v‖ ^ 2) := by
  have hc := AEGIS.WeilSeparatedArchBridgeV31.logLift_continuous g
  refine Integrable.mono' (((shifted_logLift_sq_integrable_v25 g u).add
      (logLift_sq_integrable_v25 g)).const_mul 2) ?_ ?_
  · exact ((hc.comp (continuous_add_const u)).sub hc).norm.pow 2 |>.aestronglyMeasurable
  · filter_upwards with v
    simp only [Pi.add_apply]
    rw [Real.norm_eq_abs, abs_of_nonneg (by positivity)]
    have hd := norm_sub_le (logLift g.1 (v + u)) (logLift g.1 v)
    have ha := norm_nonneg (logLift g.1 (v + u))
    have hb := norm_nonneg (logLift g.1 v)
    have hn := norm_nonneg (logLift g.1 (v + u) - logLift g.1 v)
    have hsq : ‖logLift g.1 (v + u) - logLift g.1 v‖ ^ 2 ≤
        (‖logLift g.1 (v + u)‖ + ‖logLift g.1 v‖) ^ 2 := pow_le_pow_left₀ hn hd 2
    nlinarith [sq_nonneg (‖logLift g.1 (v + u)‖ - ‖logLift g.1 v‖)]

theorem re_corr_le (g : WeilCompactSmoothGV1) (u : ℝ) :
    (logCorrelationV25 g u).re ≤ energy g.1 :=
  (Complex.re_le_norm _).trans (norm_logCorrelation_le_energy_v25 g u)

theorem corr_continuous (g : WeilCompactSmoothGV1) :
    Continuous (logCorrelationV25 g) :=
  AEGIS.WeilSeparatedArchBridgeV31.logCross_continuous g g

theorem sinh_le_mul_exp (u : ℝ) : Real.sinh u ≤ u * Real.exp u := by
  rw [Real.sinh_eq]
  have he : Real.exp u * Real.exp (-2 * u) = Real.exp (-u) := by
    rw [← Real.exp_add]; ring_nf
  have h1 := Real.add_one_le_exp (-2 * u)
  have hp := Real.exp_pos u
  nlinarith [mul_le_mul_of_nonneg_left h1 hp.le]

theorem exp_half_sub_one_le {u : ℝ} :
    Real.exp (u / 2) - 1 ≤ u / 2 * Real.exp (u / 2) := by
  have he : Real.exp (u / 2) * Real.exp (-(u / 2)) = 1 := by
    rw [← Real.exp_add]; simp
  have h1 := Real.add_one_le_exp (-(u / 2))
  have hp := Real.exp_pos (u / 2)
  nlinarith [mul_le_mul_of_nonneg_left h1 hp.le]

/-- Pointwise bound on the inner window, keeping the `E − Re C` part. -/
theorem inner_pointwise (g : WeilCompactSmoothGV1) {u : ℝ}
    (hu0 : 0 < u) (huw : u ≤ (1 / 32 : ℝ)) :
    widthArchLogIntegrandV26 g u ≤
      energy g.1 * (Real.exp (1 / 64 : ℝ) / 2) -
        Real.exp (-(1 / 32 : ℝ)) * ((energy g.1 - (logCorrelationV25 g u).re) / u) := by
  set E := energy g.1
  set c := (logCorrelationV25 g u).re
  set q := Real.exp (u / 2)
  set s := Real.sinh u
  have hE : 0 ≤ E := energy_nonnegative g.1
  have hD : 0 ≤ E - c := sub_nonneg.mpr (re_corr_le g u)
  have hs : 0 < s := AEGIS.WeilArchimedeanCothTailV1.sinh_pos_of_pos hu0
  have hus : u ≤ s := Real.self_le_sinh_iff.mpr hu0.le
  have hsu : s ≤ u * Real.exp u := sinh_le_mul_exp u
  have hq1 : 1 ≤ q := Real.one_le_exp (by linarith)
  have hq64 : q ≤ Real.exp (1 / 64) := Real.exp_le_exp.mpr (by linarith)
  have hqq : Real.exp u = q * q := by rw [← Real.exp_add]; ring_nf
  have hcq : Real.exp u * (WeilAutocorrelationV1 g (Real.exp u)).re = q * c := by
    have hC := logCorrelation_eq_autocorrelation_v25 g u
    have : c = q * (WeilAutocorrelationV1 g (Real.exp u)).re := by
      simp only [c, q, hC, Complex.re_ofReal_mul]
    rw [this, hqq]; ring
  have hint : widthArchLogIntegrandV26 g u = (q * c - E) / s := by
    unfold widthArchLogIntegrandV26; rw [hcq]
  rw [hint]
  have hexpu : Real.exp u ≤ Real.exp (1 / 32) := Real.exp_le_exp.mpr huw
  have hinv : Real.exp (-(1 / 32 : ℝ)) * Real.exp (1 / 32) = 1 := by
    rw [← Real.exp_add]; simp
  -- (q − 1) E / s ≤ E e^{1/64} / 2
  have hA : (q - 1) * E / s ≤ E * (Real.exp (1 / 64) / 2) := by
    rw [div_le_iff₀ hs]
    have h1 : q - 1 ≤ u / 2 * q := exp_half_sub_one_le
    have h2 : (q - 1) * E ≤ u / 2 * q * E := mul_le_mul_of_nonneg_right h1 hE
    have h3 : u / 2 * q * E ≤ s / 2 * Real.exp (1 / 64) * E := by
      have : u / 2 * q ≤ s / 2 * Real.exp (1 / 64) :=
        mul_le_mul (by linarith) hq64 (by linarith) (by positivity)
      exact mul_le_mul_of_nonneg_right this hE
    nlinarith
  -- e^{−1/32} (E − c)/u ≤ q (E − c)/s
  have hB : Real.exp (-(1 / 32 : ℝ)) * ((E - c) / u) ≤ q * (E - c) / s := by
    rw [mul_div_assoc', div_le_div_iff₀ hu0 hs]
    have h1 : Real.exp (-(1 / 32 : ℝ)) * (E - c) * s ≤
        Real.exp (-(1 / 32 : ℝ)) * (E - c) * (u * Real.exp (1 / 32)) := by
      apply mul_le_mul_of_nonneg_left (hsu.trans (mul_le_mul_of_nonneg_left hexpu hu0.le))
      exact mul_nonneg (Real.exp_pos _).le hD
    have h2 : Real.exp (-(1 / 32 : ℝ)) * (E - c) * (u * Real.exp (1 / 32)) = (E - c) * u := by
      calc _ = (Real.exp (-(1 / 32 : ℝ)) * Real.exp (1 / 32)) * ((E - c) * u) := by ring
        _ = _ := by rw [hinv, one_mul]
    have h3 : (E - c) * u ≤ q * (E - c) * u := by
      have := mul_le_mul_of_nonneg_right hq1 (mul_nonneg hD hu0.le)
      nlinarith
    linarith
  have hsplit : (q * c - E) / s = (q - 1) * E / s - q * (E - c) / s := by
    field_simp; ring
  rw [hsplit]
  linarith

/-- The weighted moment `∫_{(0,1/32]} (E − Re C(u))/u du` is at least `log 2 · E`. -/
theorem weighted_gain (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a)
    (hI : IntegrableOn (fun u => (energy g.1 - (logCorrelationV25 g u).re) / u)
      (Ioc (0 : ℝ) (1 / 32))) :
    Real.log 2 * energy g.1 ≤
      ∫ u in Ioc (0 : ℝ) (1 / 32), (energy g.1 - (logCorrelationV25 g u).re) / u := by
  have hcont := AEGIS.WeilSeparatedArchBridgeV31.logLift_continuous g
  have hsupp : ∀ x, x ∉ Icc (a - 1 / 64) (a - 1 / 64 + 1 / 32) → logLift g.1 x = 0 := by
    intro x hx
    apply image_eq_zero_of_notMem_tsupport
    intro hm
    apply hx
    have := hw hm
    exact ⟨this.1, by linarith [this.2]⟩
  have hS1 := AEGIS.WeilDiagonalLogGainS1.log_gain (logLift g.1) hcont.measurable (a - 1 / 64) (1 / 32) hsupp
  have hE : (∫⁻ x, AEGIS.WeilDiagonalLogGainS1.F (logLift g.1) x) = ENNReal.ofReal (energy g.1) := by
    unfold AEGIS.WeilDiagonalLogGainS1.F
    rw [← ofReal_integral_eq_lintegral_ofReal (logLift_sq_integrable_v25 g)
      (Filter.Eventually.of_forall fun _ => by positivity)]
    congr 1
    simpa using shifted_logLift_sq_integral_v25 g 0
  have hR : (∫⁻ s in Ioc (0 : ℝ) (1 / 32), AEGIS.WeilDiagonalLogGainS1.w s *
        ∫⁻ x, ENNReal.ofReal (‖logLift g.1 (x + s) - logLift g.1 x‖ ^ 2)) =
      ∫⁻ s in Ioc (0 : ℝ) (1 / 32),
        ENNReal.ofReal ((energy g.1 - (logCorrelationV25 g s).re) / s) := by
    apply setLIntegral_congr_fun measurableSet_Ioc
    intro s hs
    simp only []
    unfold AEGIS.WeilDiagonalLogGainS1.w
    rw [← ofReal_integral_eq_lintegral_ofReal (diff_sq_integrable g s)
      (Filter.Eventually.of_forall fun _ => by positivity),
      ← ENNReal.ofReal_mul (by have := hs.1; positivity), diff_sq_integral]
    congr 1
    have : s ≠ 0 := ne_of_gt hs.1
    field_simp
  have hnn : 0 ≤ᵐ[volume.restrict (Ioc (0 : ℝ) (1 / 32))]
      fun u => (energy g.1 - (logCorrelationV25 g u).re) / u := by
    filter_upwards [ae_restrict_mem measurableSet_Ioc] with u hu
    exact div_nonneg (sub_nonneg.mpr (re_corr_le g u)) hu.1.le
  rw [hE, hR, ← ofReal_integral_eq_lintegral_ofReal hI hnn,
    ← ENNReal.ofReal_mul (Real.log_nonneg (by norm_num))] at hS1
  exact (ENNReal.ofReal_le_ofReal_iff (integral_nonneg_of_ae hnn)).mp hS1

/-- The improved inner-window bound. -/
theorem inner_log_gain (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a) :
    (∫ u in Ioc (0 : ℝ) (1 / 32), widthArchLogIntegrandV26 g u) ≤
      energy g.1 * diagonalSmallV21 -
        Real.exp (-(1 / 32 : ℝ)) * (Real.log 2 * energy g.1) := by
  set E := energy g.1
  set K : ℝ := E * (Real.exp (1 / 64 : ℝ) / 2)
  set P : ℝ → ℝ := fun u => (E - (logCorrelationV25 g u).re) / u
  have hf : IntegrableOn (widthArchLogIntegrandV26 g) (Ioc (0 : ℝ) (1 / 32)) :=
    (width_arch_log_integrableOn_v27 g).mono_set (fun u hu => hu.1)
  have hK : IntegrableOn (fun _ : ℝ => K) (Ioc (0 : ℝ) (1 / 32)) :=
    continuous_const.integrableOn_Ioc
  have hPmeas : AEStronglyMeasurable P (volume.restrict (Ioc (0 : ℝ) (1 / 32))) := by
    apply ContinuousOn.aestronglyMeasurable _ measurableSet_Ioc
    apply ContinuousOn.div _ continuousOn_id (fun u hu => ne_of_gt hu.1)
    exact (continuous_const.sub (Complex.continuous_re.comp (corr_continuous g))).continuousOn
  have hcexp : 0 < Real.exp (1 / 32 : ℝ) := Real.exp_pos _
  have hinv : Real.exp (1 / 32 : ℝ) * Real.exp (-(1 / 32 : ℝ)) = 1 := by
    rw [← Real.exp_add]; simp
  have hPint : IntegrableOn P (Ioc (0 : ℝ) (1 / 32)) := by
    refine Integrable.mono' ((hK.sub hf).const_mul (Real.exp (1 / 32 : ℝ))) hPmeas ?_
    filter_upwards [ae_restrict_mem measurableSet_Ioc] with u hu
    have hp := inner_pointwise g hu.1 hu.2
    have hP0 : 0 ≤ P u := div_nonneg (sub_nonneg.mpr (re_corr_le g u)) hu.1.le
    rw [Real.norm_eq_abs, abs_of_nonneg hP0]
    have : Real.exp (-(1 / 32 : ℝ)) * P u ≤ K - widthArchLogIntegrandV26 g u := by
      simp only [P, K, E] at *; linarith
    calc P u = Real.exp (1 / 32 : ℝ) * (Real.exp (-(1 / 32 : ℝ)) * P u) := by
          rw [← mul_assoc, hinv, one_mul]
      _ ≤ Real.exp (1 / 32 : ℝ) * (K - widthArchLogIntegrandV26 g u) :=
          mul_le_mul_of_nonneg_left this hcexp.le
  have hmono : (∫ u in Ioc (0 : ℝ) (1 / 32), widthArchLogIntegrandV26 g u) ≤
      ∫ u in Ioc (0 : ℝ) (1 / 32), (K - Real.exp (-(1 / 32 : ℝ)) * P u) := by
    refine setIntegral_mono_on hf (hK.sub (hPint.const_mul _)) measurableSet_Ioc ?_
    intro u hu
    exact inner_pointwise g hu.1 hu.2
  have hgain := weighted_gain g a hw hPint
  have hP2 : (∫ u in Ioc (0 : ℝ) (1 / 32), Real.exp (-(1 / 32 : ℝ)) * P u) =
      Real.exp (-(1 / 32 : ℝ)) * ∫ u in Ioc (0 : ℝ) (1 / 32), P u :=
    integral_const_mul _ _
  have hK2 : (∫ _u in Ioc (0 : ℝ) (1 / 32), K) = E * diagonalSmallV21 := by
    rw [setIntegral_const, smul_eq_mul,
      Real.volume_real_Ioc_of_le (by norm_num : (0 : ℝ) ≤ 1 / 32)]
    simp only [K]; unfold diagonalSmallV21; ring
  rw [integral_sub hK (hPint.const_mul _), hP2, hK2] at hmono
  have hc0 : 0 ≤ Real.exp (-(1 / 32 : ℝ)) := (Real.exp_pos _).le
  have hg' : Real.log 2 * E ≤ ∫ u in Ioc (0 : ℝ) (1 / 32), P u := hgain
  nlinarith [mul_le_mul_of_nonneg_left hg' hc0]

/-- **Diagonal log-gain**: `(103/100 + e^{−1/32} log 2) · E ≤ −Re B(g,g)` at width 1/32. -/
theorem width_diagonal_log_gain_v1 (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) :
    (103 / 100 + Real.exp (-(1 / 32 : ℝ)) * Real.log 2) * energy g.1 ≤ -(B g g).re := by
  set E := energy g.1
  set c := Real.exp (-(1 / 32 : ℝ)) * Real.log 2
  have hE : 0 ≤ E := energy_nonnegative g.1
  have harch : (WeilArchimedeanIntegralV1 (WeilAutocorrelationV1 g)).re ≤
      E * ((diagonalSmallV21 - c) - diagonalTailV24) := by
    rw [archimedean_real_eq_log_integral_v27, width_arch_log_split_v27,
      width_arch_tail_integral_eq_v27 g a hw]
    have := inner_log_gain g a hw
    simp only [c, E] at *
    nlinarith
  have hred := actual_diagonal_from_arch_budget g diagonalTailV24 (diagonalSmallV21 - c)
    (width_diagonal_prime_sum_zero_v24 g a hw) harch
  have hbase : (103 / 100 : ℝ) < 6 * Real.log 2 - diagonalKappaV21 - diagonalSmallV21 := by
    unfold diagonalKappaV21 diagonalSmallV21
    nlinarith [certificate_diagonal_threshold, diagonal_constant_floor]
  have htail := diagonal_tail_gt_six_log_two_v24
  have h1 : (103 / 100 + c) * E ≤ E * (diagonalTailV24 - diagonalKappaV21 - (diagonalSmallV21 - c)) := by
    have : 103 / 100 + c ≤ diagonalTailV24 - diagonalKappaV21 - (diagonalSmallV21 - c) := by
      linarith
    nlinarith
  linarith

/-- Numerical form of the new constant: `103/100 + e^{−1/32} log 2 > 17/10`. -/
theorem log_gain_constant_gt : (17 / 10 : ℝ) < 103 / 100 + Real.exp (-(1 / 32 : ℝ)) * Real.log 2 := by
  have h1 : (1 - 1 / 32 : ℝ) ≤ Real.exp (-(1 / 32 : ℝ)) := by
    have := Real.add_one_le_exp (-(1 / 32 : ℝ)); linarith
  have h2 := Real.log_two_gt_d9
  nlinarith

end AEGIS.WeilDiagonalLogGainV1

#print axioms AEGIS.WeilDiagonalLogGainV1.diff_sq_integral
#print axioms AEGIS.WeilDiagonalLogGainV1.inner_pointwise
#print axioms AEGIS.WeilDiagonalLogGainV1.weighted_gain
#print axioms AEGIS.WeilDiagonalLogGainV1.inner_log_gain
#print axioms AEGIS.WeilDiagonalLogGainV1.width_diagonal_log_gain_v1
#print axioms AEGIS.WeilDiagonalLogGainV1.log_gain_constant_gt
