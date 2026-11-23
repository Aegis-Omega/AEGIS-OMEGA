import WeilSeparatedArchBridgeV31
import WeilFiveBlockPerronV1

open Complex
open scoped ComplexConjugate
set_option autoImplicit false
noncomputable section

namespace AEGIS.WeilFiveBlockCrossV1

open WeilDisjointEnergyV2 WeilMixedClosureV2 WeilMixedAlgebraV2
open WeilThreeBlockTranslatedPacketsV22 WeilThreeBlockCrossPrimeV28
open WeilArchimedeanCothTailV1 WeilSeparatedArchBridgeV31 WeilFiveBlockPerronV1

private theorem nat_eq_of_log_window {m n : ℕ} (hm : 0 < m) (hn : 2 ≤ n)
    (hn16 : n ≤ 16) (hwin : |Real.log (m : ℝ) - Real.log (n : ℝ)| ≤ 1 / 32) :
    m = n := by
  have hmR : (0 : ℝ) < m := by exact_mod_cast hm
  have hnR : (0 : ℝ) < n := by exact_mod_cast (show 0 < n by omega)
  have hnR16 : (n : ℝ) ≤ 16 := by exact_mod_cast hn16
  obtain ⟨hlo, hup⟩ := abs_le.mp hwin
  have h₁ := Real.exp_le_exp.mpr
    (show Real.log (n : ℝ) + -(1 / 32 : ℝ) ≤ Real.log (m : ℝ) by linarith)
  have h₂ := Real.exp_le_exp.mpr
    (show Real.log (m : ℝ) ≤ Real.log (n : ℝ) + 1 / 32 by linarith)
  rw [Real.exp_add, Real.exp_log hnR, Real.exp_log hmR] at h₁
  rw [Real.exp_add, Real.exp_log hnR, Real.exp_log hmR] at h₂
  have hlow : (n : ℝ) - 1 < m := by
    nlinarith [mul_lt_mul_of_pos_left exp_neg_one_div_32_gt hnR]
  have hupp : (m : ℝ) < (n : ℝ) + 1 := by
    nlinarith [mul_lt_mul_of_pos_left exp_one_div_32_lt hnR]
  have hlow' : n < m + 1 := by exact_mod_cast (show (n : ℝ) < (m : ℝ) + 1 by linarith)
  have hupp' : m < n + 1 := by exact_mod_cast hupp
  omega

theorem mixed_prime_sum_single (g : WeilCompactSmoothGV1) (a d₁ d₂ : ℝ)
    (hw : WidthOneThirtyTwoAt g a) (n : ℕ) (hn : 2 ≤ n) (hn16 : n ≤ 16)
    (hd : d₂ - d₁ = Real.log (n : ℝ)) :
    WeilPrimeSumV1 (mixed (translatePacket g d₁) (translatePacket g d₂)) =
      ((ArithmeticFunction.vonMangoldt n / Real.sqrt (n : ℝ) * energy g.1 : ℝ) : ℂ) := by
  let f := mixed (translatePacket g d₁) (translatePacket g d₂)
  change WeilPrimeSumV1 f = _
  have hnR : (0 : ℝ) < n := by exact_mod_cast (show 0 < n by omega)
  have hgap : (1 / 32 : ℝ) < d₂ - d₁ := by
    rw [hd]
    refine log_two_gt_one_thirty_two.trans_le (Real.log_le_log (by norm_num) ?_)
    exact_mod_cast hn
  have pos_sample (m : ℕ) (hm : 0 < m) : f (m : ℝ) = 0 := by
    have hmR : (0 : ℝ) < m := by exact_mod_cast hm
    have hm1 : (1 : ℝ) ≤ m := by exact_mod_cast (show 1 ≤ m by omega)
    have hlog := Real.log_nonneg hm1
    have hfar : (1 / 32 : ℝ) < |Real.log (m : ℝ) + d₂ - d₁| := by
      rw [abs_of_pos (by linarith)]
      linarith
    simpa [f, Real.exp_log hmR] using
      mixed_translate_zero_of_width_v28 g a d₁ d₂ (Real.log (m : ℝ)) hw hfar
  have inv_sample (m : ℕ) (hm : 0 < m) (hne : m ≠ n) : f ((m : ℝ)⁻¹) = 0 := by
    have hmR : (0 : ℝ) < m := by exact_mod_cast hm
    have hfar : (1 / 32 : ℝ) < |Real.log (m : ℝ) - Real.log (n : ℝ)| :=
      lt_of_not_ge (fun h => hne (nat_eq_of_log_window hm hn hn16 h))
    have harg : -Real.log (m : ℝ) + d₂ - d₁ =
        -(Real.log (m : ℝ) - Real.log (n : ℝ)) := by linarith
    simpa [f, Real.exp_neg, Real.exp_log hmR] using
      mixed_translate_zero_of_width_v28 g a d₁ d₂ (-Real.log (m : ℝ)) hw
        (by rw [harg, abs_neg]; exact hfar)
  have hnIdx : n - 1 + 1 = n := by omega
  unfold WeilPrimeSumV1
  rw [tsum_eq_single (n - 1)]
  · have hroot : Real.exp (Real.log (n : ℝ) / 2) = Real.sqrt (n : ℝ) := by
      have he : Real.exp (Real.log (n : ℝ) / 2) ^ 2 = (n : ℝ) := by
        rw [pow_two, ← Real.exp_add, show Real.log (n : ℝ) / 2 +
          Real.log (n : ℝ) / 2 = Real.log (n : ℝ) by ring, Real.exp_log hnR]
      nlinarith [Real.sq_sqrt hnR.le, Real.exp_pos (Real.log (n : ℝ) / 2),
        Real.sqrt_nonneg (n : ℝ)]
    have hd' : d₁ - d₂ = -Real.log (n : ℝ) := by linarith
    have hc := mixed_translate_center_v28 g d₁ d₂
    rw [hd', neg_div, Real.exp_neg, hroot, Real.exp_neg, Real.exp_log hnR] at hc
    have hsR := Real.sqrt_pos.2 hnR
    have hs : (Real.sqrt (n : ℝ) : ℂ) ≠ 0 := by exact_mod_cast hsR.ne'
    have hnc : (n : ℂ) ≠ 0 := by exact_mod_cast hnR.ne'
    have hsq : (Real.sqrt (n : ℝ) : ℂ) ^ 2 = (n : ℂ) := by
      exact_mod_cast Real.sq_sqrt hnR.le
    have hcenter : f ((n : ℝ)⁻¹) = (Real.sqrt (n : ℝ) : ℂ) * (energy g.1 : ℂ) := by
      rw [Complex.ofReal_inv] at hc
      change (Real.sqrt (n : ℝ) : ℂ)⁻¹ * f ((n : ℝ)⁻¹) = _ at hc
      apply (inv_mul_eq_iff_eq_mul₀ hs).mp hc
    simp only [WeilPrimeTermV1, hnIdx, pos_sample n (by omega), hcenter, zero_add]
    push_cast
    have hscale : (Real.sqrt (n : ℝ) : ℂ) / (n : ℂ) =
        1 / (Real.sqrt (n : ℝ) : ℂ) := by
      apply (div_eq_div_iff hnc hs).2
      simpa [pow_two] using hsq
    calc
      _ = (ArithmeticFunction.vonMangoldt n : ℂ) *
          (((Real.sqrt (n : ℝ) : ℂ) / (n : ℂ)) * (energy g.1 : ℂ)) := by ring
      _ = _ := by rw [hscale]; ring
  · intro m hm
    simp only [WeilPrimeTermV1, pos_sample (m + 1) (by omega),
      inv_sample (m + 1) (by omega) (by omega), mul_zero, add_zero]

private theorem scalar_ceiling (k : ℕ) (hk : 1 ≤ k) (hk4 : k ≤ 4) :
    Real.log 2 / Real.sqrt ((2 ^ k : ℕ) : ℝ) + 1 / 100 ≤ ceiling k := by
  have hlog : Real.log 2 < (694 / 1000 : ℝ) := Real.log_two_lt_d9.trans (by norm_num)
  have bound (n r c : ℝ) (hr : 0 < r) (hs : r ^ 2 ≤ n)
      (hc : (694 / 1000 : ℝ) ≤ (c - 1 / 100) * r) (hc' : 0 ≤ c - 1 / 100) :
      Real.log 2 / Real.sqrt n + 1 / 100 ≤ c := by
    have hn : 0 < n := (sq_pos_of_pos hr).trans_le hs
    have hsqrt : r ≤ Real.sqrt n := by
      nlinarith [Real.sq_sqrt hn.le, Real.sqrt_nonneg n]
    have hmul := mul_le_mul_of_nonneg_left hsqrt hc'
    have hd := (div_le_iff₀ (Real.sqrt_pos.2 hn)).2 (hlog.le.trans (hc.trans hmul))
    linarith
  interval_cases k
  · exact bound 2 (1414 / 1000) _ (by norm_num) (by norm_num)
      (by norm_num [ceiling]) (by norm_num [ceiling])
  · exact bound 4 2 _ (by norm_num) (by norm_num)
      (by norm_num [ceiling]) (by norm_num [ceiling])
  · exact bound 8 (2828 / 1000) _ (by norm_num) (by norm_num)
      (by norm_num [ceiling]) (by norm_num [ceiling])
  · exact bound 16 4 _ (by norm_num) (by norm_num)
      (by norm_num [ceiling]) (by norm_num [ceiling])

theorem translated_cross_bound (g : WeilCompactSmoothGV1) (a d₁ d₂ : ℝ)
    (hw : WidthOneThirtyTwoAt g a) (hm : WeilMomentConditionsV1 g)
    (k : ℕ) (hk : 1 ≤ k) (hk4 : k ≤ 4) (hd : d₂ - d₁ = (k : ℝ) * Real.log 2) :
    ‖B (translatePacket g d₁) (translatePacket g d₂)‖ ≤ ceiling k * energy g.1 := by
  have hn : 2 ≤ (2 : ℕ) ^ k := by interval_cases k <;> decide
  have hn16 : (2 : ℕ) ^ k ≤ 16 := by interval_cases k <;> decide
  have hlog : 0 ≤ Real.log 2 := Real.log_nonneg (by norm_num)
  have hkR : (1 : ℝ) ≤ k := by exact_mod_cast hk
  have hgap : Real.log 2 ≤ d₂ - d₁ := by
    rw [hd]
    nlinarith [mul_le_mul_of_nonneg_right hkR hlog]
  have hprime := mixed_prime_sum_single g a d₁ d₂ hw (2 ^ k) hn hn16
    (by rw [Nat.cast_pow, Nat.cast_ofNat, Real.log_pow]; exact hd)
  rw [ArithmeticFunction.vonMangoldt_apply_pow (by omega : k ≠ 0),
    ArithmeticFunction.vonMangoldt_apply_prime (by decide : Nat.Prime 2)] at hprime
  simp only [Nat.cast_ofNat] at hprime
  have hzero : mixed (translatePacket g d₁) (translatePacket g d₂) 1 = 0 := by
    simpa using mixed_translate_zero_of_width_v28 g a d₁ d₂ 0 hw (by
      have hfar := log_two_gt_one_thirty_two.trans_le hgap
      rw [zero_add, abs_of_pos (lt_trans (by norm_num) hfar)]
      exact hfar)
  have harch := translated_arch_norm_bound g a d₁ d₂ hw hm hgap
  have hE := energy_nonnegative g.1
  unfold B WeilExplicitRightSideV1
  rw [hzero, mul_zero, add_zero]
  refine (norm_add_le _ _).trans ?_
  rw [hprime, Complex.norm_real, Real.norm_eq_abs,
    abs_of_nonneg (mul_nonneg (div_nonneg hlog (Real.sqrt_nonneg _)) hE)]
  calc
    _ ≤ (Real.log 2 / Real.sqrt ((2 ^ k : ℕ) : ℝ)) * energy g.1 +
        (1 / 100 : ℝ) * energy g.1 := add_le_add (le_refl _) harch
    _ = (Real.log 2 / Real.sqrt ((2 ^ k : ℕ) : ℝ) + 1 / 100) * energy g.1 := by ring
    _ ≤ _ := mul_le_mul_of_nonneg_right (scalar_ceiling k hk hk4) hE

end AEGIS.WeilFiveBlockCrossV1

#print axioms AEGIS.WeilFiveBlockCrossV1.mixed_prime_sum_single
#print axioms AEGIS.WeilFiveBlockCrossV1.translated_cross_bound
