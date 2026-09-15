import WeilAutocorrelationClosureV1
import Mathlib.Analysis.Complex.ExponentialBounds
import Mathlib.Tactic

open Set MeasureTheory Complex
open scoped ComplexConjugate

set_option autoImplicit false

noncomputable section

def WeilLogWindowV1 (g : ℝ → ℂ) (a w : ℝ) : Prop :=
  ∀ {y : ℝ}, g y ≠ 0 → Real.log y ∈ Icc a (a + w)

theorem log_mem_difference_window_of_integrand_ne_zero
    {gᵢ gⱼ : ℝ → ℂ} {aᵢ aⱼ w x y : ℝ}
    (hx : 0 < x) (hy : 0 < y)
    (hᵢ : WeilLogWindowV1 gᵢ aᵢ w)
    (hⱼ : WeilLogWindowV1 gⱼ aⱼ w)
    (hprod : gᵢ (x * y) * star (gⱼ y) ≠ 0) :
    Real.log x ∈ Icc (aᵢ - aⱼ - w) (aᵢ - aⱼ + w) := by
  have hxy_ne : gᵢ (x * y) ≠ 0 := by
    intro h
    apply hprod
    simp [h]
  have hy_ne : gⱼ y ≠ 0 := by
    intro h
    apply hprod
    simp [h]
  have hxy := hᵢ hxy_ne
  have hyw := hⱼ hy_ne
  rw [Real.log_mul hx.ne' hy.ne'] at hxy
  constructor <;> linarith [hxy.1, hxy.2, hyw.1, hyw.2]

def WeilPrimeWindowWidthV1 : ℝ := (1 : ℝ) / 32

theorem weil_prime_window_width_lt_log_two_v1 :
    WeilPrimeWindowWidthV1 < Real.log 2 := by
  unfold WeilPrimeWindowWidthV1
  exact lt_trans (by norm_num) Real.log_two_gt_d9

theorem weil_narrow_log_window_integrand_zero_v1
    (g : ℝ → ℂ) (a : ℝ)
    (hwin : WeilLogWindowV1 g a WeilPrimeWindowWidthV1)
    {x y : ℝ} (hx : 2 ≤ x) (hy : 0 < y) :
    g (x * y) * star (g y) = 0 := by
  by_contra hprod
  have hxpos : 0 < x := lt_of_lt_of_le (by norm_num) hx
  have hmem :=
    log_mem_difference_window_of_integrand_ne_zero
      hxpos hy hwin hwin hprod
  have hlogx_le : Real.log x ≤ WeilPrimeWindowWidthV1 := by
    linarith [hmem.2]
  have hlog2_le : Real.log 2 ≤ Real.log x := by
    exact (Real.log_le_log_iff (by norm_num) hxpos).2 hx
  have hsep := weil_prime_window_width_lt_log_two_v1
  linarith

theorem weil_autocorrelation_zero_of_narrow_log_window_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hwin : WeilLogWindowV1 g.1 a WeilPrimeWindowWidthV1)
    {x : ℝ} (hx : 2 ≤ x) :
    WeilAutocorrelationV1 g x = 0 := by
  unfold WeilAutocorrelationV1
  apply integral_eq_zero_of_ae
  filter_upwards [ae_restrict_mem measurableSet_Ioi] with y hy
  exact weil_narrow_log_window_integrand_zero_v1 g.1 a hwin hx hy

theorem weil_autocorrelation_inv_zero_of_narrow_log_window_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hwin : WeilLogWindowV1 g.1 a WeilPrimeWindowWidthV1)
    {x : ℝ} (hx : 2 ≤ x) :
    WeilAutocorrelationV1 g x⁻¹ = 0 := by
  have hxpos : 0 < x := lt_of_lt_of_le (by norm_num) hx
  have hzero := weil_autocorrelation_zero_of_narrow_log_window_v1 g a hwin hx
  have hrec := weil_autocorrelation_reciprocal_v1 g hxpos
  simpa [hzero] using hrec

theorem weil_prime_term_zero_of_narrow_log_window_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hwin : WeilLogWindowV1 g.1 a WeilPrimeWindowWidthV1)
    (n : ℕ) :
    WeilPrimeTermV1 (WeilAutocorrelationV1 g) n = 0 := by
  cases n with
  | zero =>
      simp [WeilPrimeTermV1]
  | succ k =>
      have hm_nat : 2 ≤ k + 2 := by omega
      have hm_real : (2 : ℝ) ≤ (k + 2 : ℕ) := by exact_mod_cast hm_nat
      have hdir :=
        weil_autocorrelation_zero_of_narrow_log_window_v1
          g a hwin (x := ((k + 2 : ℕ) : ℝ)) hm_real
      have hinv :=
        weil_autocorrelation_inv_zero_of_narrow_log_window_v1
          g a hwin (x := ((k + 2 : ℕ) : ℝ)) hm_real
      simp [WeilPrimeTermV1, hdir, hinv]

theorem weil_prime_sum_zero_of_narrow_log_window_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hwin : WeilLogWindowV1 g.1 a WeilPrimeWindowWidthV1) :
    WeilPrimeSumV1 (WeilAutocorrelationV1 g) = 0 := by
  simp [WeilPrimeSumV1, weil_prime_term_zero_of_narrow_log_window_v1 g a hwin]

theorem nat_eq_two_of_log_mem_two_window_v1
    {m : ℕ} (hm : 2 ≤ m)
    (hlog : Real.log (m : ℝ) ∈
      Icc (Real.log 2 - WeilPrimeWindowWidthV1)
          (Real.log 2 + WeilPrimeWindowWidthV1)) :
    m = 2 := by
  have hm0 : 0 < m := lt_of_lt_of_le (by omega) hm
  have hmpos : (0 : ℝ) < (m : ℝ) := by exact_mod_cast hm0
  have hsep :
      Real.log 2 + WeilPrimeWindowWidthV1 < Real.log 3 := by
    unfold WeilPrimeWindowWidthV1
    nlinarith [Real.log_two_lt_d9, Real.log_three_gt_d9]
  have hm_lt_three : m < 3 := by
    by_contra h
    have hm3 : 3 ≤ m := by omega
    have hlog3_le : Real.log 3 ≤ Real.log (m : ℝ) := by
      apply (Real.log_le_log_iff (by norm_num) hmpos).2
      exact_mod_cast hm3
    linarith [hlog.2]
  omega

theorem nat_eq_four_of_log_mem_four_window_v1
    {m : ℕ} (hm : 2 ≤ m)
    (hlog : Real.log (m : ℝ) ∈
      Icc (Real.log 4 - WeilPrimeWindowWidthV1)
          (Real.log 4 + WeilPrimeWindowWidthV1)) :
    m = 4 := by
  have hm0 : 0 < m := lt_of_lt_of_le (by omega) hm
  have hmpos : (0 : ℝ) < (m : ℝ) := by exact_mod_cast hm0
  have hleft :
      Real.log 3 < Real.log 4 - WeilPrimeWindowWidthV1 := by
    unfold WeilPrimeWindowWidthV1
    rw [Real.log_four_eq]
    nlinarith [Real.log_three_lt_d9, Real.log_two_gt_d9]
  have hright :
      Real.log 4 + WeilPrimeWindowWidthV1 < Real.log 5 := by
    unfold WeilPrimeWindowWidthV1
    rw [Real.log_four_eq]
    nlinarith [Real.log_two_lt_d9, Real.log_five_gt_d9]
  have hm4 : 4 ≤ m := by
    by_contra h
    have hm3 : m ≤ 3 := by omega
    have hlogm_le : Real.log (m : ℝ) ≤ Real.log 3 := by
      apply (Real.log_le_log_iff hmpos (by norm_num)).2
      exact_mod_cast hm3
    linarith [hlog.1]
  have hmle4 : m ≤ 4 := by
    by_contra h
    have hm5 : 5 ≤ m := by omega
    have hlog5_le : Real.log 5 ≤ Real.log (m : ℝ) := by
      apply (Real.log_le_log_iff (by norm_num) hmpos).2
      exact_mod_cast hm5
    linarith [hlog.2]
  omega

theorem nat_eq_two_of_integrand_ne_zero_v1
    {gᵢ gⱼ : ℝ → ℂ} {aᵢ aⱼ y : ℝ} {m : ℕ}
    (hm : 2 ≤ m) (hy : 0 < y)
    (hᵢ : WeilLogWindowV1 gᵢ aᵢ WeilPrimeWindowWidthV1)
    (hⱼ : WeilLogWindowV1 gⱼ aⱼ WeilPrimeWindowWidthV1)
    (hcenter : aᵢ - aⱼ = Real.log 2)
    (hprod : gᵢ ((m : ℝ) * y) * star (gⱼ y) ≠ 0) :
    m = 2 := by
  have hm0 : 0 < m := lt_of_lt_of_le (by omega) hm
  have hmr : (0 : ℝ) < (m : ℝ) := by exact_mod_cast hm0
  have hmem :=
    log_mem_difference_window_of_integrand_ne_zero
      hmr hy hᵢ hⱼ hprod
  apply nat_eq_two_of_log_mem_two_window_v1 hm
  constructor <;> linarith [hmem.1, hmem.2, hcenter]

theorem nat_eq_four_of_integrand_ne_zero_v1
    {gᵢ gⱼ : ℝ → ℂ} {aᵢ aⱼ y : ℝ} {m : ℕ}
    (hm : 2 ≤ m) (hy : 0 < y)
    (hᵢ : WeilLogWindowV1 gᵢ aᵢ WeilPrimeWindowWidthV1)
    (hⱼ : WeilLogWindowV1 gⱼ aⱼ WeilPrimeWindowWidthV1)
    (hcenter : aᵢ - aⱼ = Real.log 4)
    (hprod : gᵢ ((m : ℝ) * y) * star (gⱼ y) ≠ 0) :
    m = 4 := by
  have hm0 : 0 < m := lt_of_lt_of_le (by omega) hm
  have hmr : (0 : ℝ) < (m : ℝ) := by exact_mod_cast hm0
  have hmem :=
    log_mem_difference_window_of_integrand_ne_zero
      hmr hy hᵢ hⱼ hprod
  apply nat_eq_four_of_log_mem_four_window_v1 hm
  constructor <;> linarith [hmem.1, hmem.2, hcenter]

#print axioms log_mem_difference_window_of_integrand_ne_zero
#print axioms weil_prime_window_width_lt_log_two_v1
#print axioms weil_narrow_log_window_integrand_zero_v1
#print axioms weil_autocorrelation_zero_of_narrow_log_window_v1
#print axioms weil_autocorrelation_inv_zero_of_narrow_log_window_v1
#print axioms weil_prime_term_zero_of_narrow_log_window_v1
#print axioms weil_prime_sum_zero_of_narrow_log_window_v1
#print axioms nat_eq_two_of_log_mem_two_window_v1
#print axioms nat_eq_four_of_log_mem_four_window_v1
#print axioms nat_eq_two_of_integrand_ne_zero_v1
#print axioms nat_eq_four_of_integrand_ne_zero_v1
