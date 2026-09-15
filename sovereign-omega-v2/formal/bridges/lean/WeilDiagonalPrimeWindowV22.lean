import WeilThreeBlockAnalyticConstantsV21
import WeilAutocorrelationClosureV1
import Mathlib.Tactic

/-!
AEGIS Ω — diagonal prime-window vanishing V2.2

This module isolates the discrete part of the width-1/32 diagonal argument.
If the actual repository arithmetic test `f` has topological support inside
(exp(-1/32), exp(1/32)), then every positive-integer prime-power term vanishes
and hence `WeilPrimeSumV1 f = 0` exactly.

This is a finite/support statement about the repository prime sum. It does not
prove that a given autocorrelation has this support window; that support bridge
is a separate analytic obligation. It also does not prove the Archimedean
lower bound, global Weil positivity, or RH.
-/

open Set Complex
set_option autoImplicit false
noncomputable section

namespace AEGIS.WeilDiagonalPrimeWindowV22

open AEGIS.WeilThreeBlockAnalyticConstantsV21

theorem exp_width_upper_lt_two :
    Real.exp ((1 : ℝ) / 32) < 2 := by
  have hmono : Real.exp ((1 : ℝ) / 32) < Real.exp ((1 : ℝ) / 16) :=
    Real.exp_lt_exp.mpr (by norm_num)
  exact hmono.trans (exp_one_over_16_upper.trans (by norm_num))

theorem half_lt_exp_neg_width :
    (1 : ℝ) / 2 < Real.exp (-(1 : ℝ) / 32) := by
  rw [show (-(1 : ℝ) / 32) = -((1 : ℝ) / 32) by ring, Real.exp_neg]
  have h := one_div_lt_one_div_of_lt (Real.exp_pos ((1 : ℝ) / 32)) exp_width_upper_lt_two
  simpa [one_div] using h

theorem weil_prime_term_zero_of_tsupport_exp_window
    (f : ℝ → ℂ)
    (hsupp :
      tsupport f ⊆
        Ioo (Real.exp (-(1 : ℝ) / 32)) (Real.exp ((1 : ℝ) / 32)))
    (n : ℕ) :
    WeilPrimeTermV1 f n = 0 := by
  rcases n with _ | n
  · simp [WeilPrimeTermV1]
  · let m : ℕ := n + 2
    have hm2 : 2 ≤ m := by
      omega
    have hm2R : (2 : ℝ) ≤ (m : ℝ) := by
      exact_mod_cast hm2
    have hmnot : (m : ℝ) ∉ tsupport f := by
      intro hm
      have hu := (hsupp hm).2
      linarith [exp_width_upper_lt_two]
    have hminv : ((m : ℝ)⁻¹) ≤ (1 : ℝ) / 2 := by
      have h := one_div_le_one_div_of_le (by norm_num : (0 : ℝ) < 2) hm2R
      simpa [one_div] using h
    have hminvnot : ((m : ℝ)⁻¹) ∉ tsupport f := by
      intro hm
      have hl := (hsupp hm).1
      linarith [half_lt_exp_neg_width, hminv]
    have hfm : f (m : ℝ) = 0 := image_eq_zero_of_notMem_tsupport hmnot
    have hfmi : f ((m : ℝ)⁻¹) = 0 := image_eq_zero_of_notMem_tsupport hminvnot
    change
      ((ArithmeticFunction.vonMangoldt m : ℝ) : ℂ) *
        (f (m : ℝ) + (1 / (m : ℂ)) * f ((m : ℝ)⁻¹)) = 0
    rw [hfm, hfmi]
    simp

theorem weil_prime_sum_zero_of_tsupport_exp_window
    (f : ℝ → ℂ)
    (hsupp :
      tsupport f ⊆
        Ioo (Real.exp (-(1 : ℝ) / 32)) (Real.exp ((1 : ℝ) / 32))) :
    WeilPrimeSumV1 f = 0 := by
  unfold WeilPrimeSumV1
  apply tsum_eq_zero_of_not_summable
  by_cases hsum : Summable (WeilPrimeTermV1 f)
  · exfalso
    apply hsum
    simpa only [weil_prime_term_zero_of_tsupport_exp_window f hsupp] using summable_zero
  · exact hsum

/-- Specialized actual repository statement for an autocorrelation. -/
theorem diagonal_autocorrelation_prime_sum_zero
    (g : WeilCompactSmoothGV1)
    (hsupp :
      tsupport (WeilAutocorrelationV1 g) ⊆
        Ioo (Real.exp (-(1 : ℝ) / 32)) (Real.exp ((1 : ℝ) / 32))) :
    WeilPrimeSumV1 (WeilAutocorrelationV1 g) = 0 :=
  weil_prime_sum_zero_of_tsupport_exp_window (WeilAutocorrelationV1 g) hsupp

end AEGIS.WeilDiagonalPrimeWindowV22
