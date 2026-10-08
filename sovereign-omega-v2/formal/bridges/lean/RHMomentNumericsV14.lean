import RHMomentNumericsV13
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Series
import Mathlib.Tactic

/-!
AEGIS Ω — extend the certified moment-gain radius from 1/8 to 9/64.

The proof is deliberately rational and kernel-facing:
* fourth-order exp enclosure for q = exp(-9/64);
* exact algebraic reduction of the coth-tail combination;
* log(23/20) <= 3/20 and log 2 > 693/1000;
* exp(9/128) < 128/119;
* cosh(9/128)-1 < 1/400 via cosh x <= exp(x^2/2).

Together with the existing kappa bound this proves
  momentGain (9/64) <= -1/10.

No floating-point value is used as theorem authority.
AUTHORITY_EFFECT = NONE.
-/

open Set Complex
open scoped BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHMomentNumericsV14

open AEGIS.RHDyadicDiagonalV13
open AEGIS.WeilDiagonalKernelReductionV21
open AEGIS.WeilThreeBlockAnalyticConstantsV21
open AEGIS.RHMomentNumericsV13

theorem exp_neg_nine_over_64_bounds :
    (8687 / 10000 : ℝ) ≤ Real.exp (-(9 / 64 : ℝ)) ∧
      Real.exp (-(9 / 64 : ℝ)) ≤ (869 / 1000 : ℝ) := by
  have h := Real.exp_bound
    (x := -(9 / 64 : ℝ))
    (by rw [abs_neg, abs_of_pos (by norm_num)]; norm_num)
    (n := 4) (by norm_num)
  have h' := abs_le.mp h
  norm_num [Finset.sum_range_succ, Nat.factorial] at h'
  obtain ⟨h1, h2⟩ := h'
  constructor <;> linarith

theorem cothTail_combo_nine_over_64_le :
    cothTail (2 * (9 / 64)) - 2 * cothTail (9 / 64) ≤
      -(5 * Real.log 2) + 3 / 20 := by
  obtain ⟨hlo, hhi⟩ := exp_neg_nine_over_64_bounds
  set q := Real.exp (-(9 / 64 : ℝ)) with hqdef
  have hq2 : Real.exp (-(2 * (9 / 64 : ℝ))) = q ^ 2 := by
    rw [hqdef, sq, ← Real.exp_add]
    ring_nf
  have hqpos : 0 < q := Real.exp_pos _
  have hq1 : q < 1 := by linarith
  unfold cothTail
  rw [hq2]
  set X := (1 + q ^ 2) / (1 - q ^ 2) with hX
  set Y := (1 + q) / (1 - q) with hY
  have h1q : 0 < 1 - q := by linarith
  have h1q2 : 0 < 1 - q ^ 2 := by nlinarith
  have hXpos : 0 < X := div_pos (by positivity) h1q2
  have hYpos : 0 < Y := div_pos (by linarith) h1q
  have hA : (1 + q ^ 2) * (1 - q) ≤
      (1 + (869 / 1000 : ℝ) ^ 2) * (1 - (8687 / 10000 : ℝ)) := by
    apply mul_le_mul _ (by linarith) h1q.le (by positivity)
    nlinarith
  have hB : (1 + (8687 / 10000 : ℝ)) ^ 3 ≤ (1 + q) ^ 3 :=
    pow_le_pow_left₀ (by norm_num) (by linarith) 3
  have hpoly :
      32 * ((1 + q ^ 2) * (1 - q)) ≤ (23 / 20 : ℝ) * (1 + q) ^ 3 := by
    have hnum :
        32 * ((1 + (869 / 1000 : ℝ) ^ 2) * (1 - (8687 / 10000 : ℝ))) ≤
          (23 / 20 : ℝ) * (1 + (8687 / 10000 : ℝ)) ^ 3 := by
      norm_num
    calc
      32 * ((1 + q ^ 2) * (1 - q))
          ≤ 32 * ((1 + (869 / 1000 : ℝ) ^ 2) *
              (1 - (8687 / 10000 : ℝ))) := by
            exact mul_le_mul_of_nonneg_left hA (by norm_num)
      _ ≤ (23 / 20 : ℝ) * (1 + (8687 / 10000 : ℝ)) ^ 3 := hnum
      _ ≤ (23 / 20 : ℝ) * (1 + q) ^ 3 := by
            exact mul_le_mul_of_nonneg_left hB (by norm_num)
  have hXY : X ≤ (23 / 20 : ℝ) * Y ^ 2 / 2 ^ 5 := by
    rw [hX, hY, div_pow, div_le_iff₀ h1q2]
    have hsq : (1 - q ^ 2) = (1 - q) * (1 + q) := by ring
    rw [hsq]
    have hpos2 : 0 < (1 - q) ^ 2 := by positivity
    rw [show (23 / 20 : ℝ) * ((1 + q) ^ 2 / (1 - q) ^ 2) / 2 ^ 5 *
        ((1 - q) * (1 + q)) =
        (23 / 20 : ℝ) * (1 + q) ^ 3 / (32 * (1 - q)) by
          field_simp [ne_of_gt h1q]
          ring]
    rw [le_div_iff₀ (by positivity)]
    nlinarith
  have hlog : Real.log X ≤ Real.log ((23 / 20 : ℝ) * Y ^ 2 / 2 ^ 5) :=
    Real.log_le_log hXpos hXY
  have hR : Real.log ((23 / 20 : ℝ) * Y ^ 2 / 2 ^ 5)
      = Real.log (23 / 20) + 2 * Real.log Y - 5 * Real.log 2 := by
    rw [Real.log_div (by positivity) (by norm_num),
      Real.log_mul (by norm_num) (by positivity), Real.log_pow, Real.log_pow]
    push_cast
    ring
  rw [hR] at hlog
  have hc : Real.log (23 / 20 : ℝ) ≤ 3 / 20 := by
    have := Real.log_le_sub_one_of_pos (by norm_num : (0 : ℝ) < 23 / 20)
    linarith
  linarith

theorem exp_nine_over_128_upper :
    Real.exp (9 / 128 : ℝ) < (128 / 119 : ℝ) := by
  calc
    Real.exp (9 / 128 : ℝ) < 1 / (1 - (9 / 128 : ℝ)) :=
      Real.exp_bound_div_one_sub_of_interval' (by norm_num) (by norm_num)
    _ = (128 / 119 : ℝ) := by norm_num

theorem cosh_nine_over_128_sub_one_upper :
    Real.cosh (9 / 128 : ℝ) - 1 < (1 / 400 : ℝ) := by
  let x : ℝ := 9 / 128
  let y : ℝ := x ^ 2 / 2
  have hc : Real.cosh x ≤ Real.exp y := by
    simpa [y] using Real.cosh_le_exp_half_sq x
  have hy0 : 0 < y := by
    dsimp [y, x]
    norm_num
  have hy1 : y < 1 := by
    dsimp [y, x]
    norm_num
  have he : Real.exp y < 1 / (1 - y) :=
    Real.exp_bound_div_one_sub_of_interval' hy0 hy1
  have hr : 1 / (1 - y) - 1 < (1 / 400 : ℝ) := by
    dsimp [y, x]
    norm_num
  dsimp [x] at hc ⊢
  linarith

theorem momentGain_nine_over_64 :
    momentGain (9 / 64) ≤ -(1 / 10) := by
  have hcombo := cothTail_combo_nine_over_64_le
  have hexp := exp_nine_over_128_upper
  have hcosh := cosh_nine_over_128_sub_one_upper
  have hk : diagonalKappaV21 < 633 / 250 + 29 / 50 := by
    unfold diagonalKappaV21
    linarith [log_four_pi_upper, euler_mascheroni_upper]
  have hl2 := log_two_lower
  have hhalf : (9 / 64 : ℝ) / 2 = 9 / 128 := by norm_num
  have hterm : (9 / 128 : ℝ) * Real.exp (9 / 128) ≤ 9 / 119 := by
    have hm := mul_le_mul_of_nonneg_left hexp.le (by norm_num : (0 : ℝ) ≤ 9 / 128)
    norm_num at hm ⊢
    exact hm
  unfold momentGain
  rw [hhalf]
  nlinarith

end AEGIS.RHMomentNumericsV14

#print axioms AEGIS.RHMomentNumericsV14.exp_neg_nine_over_64_bounds
#print axioms AEGIS.RHMomentNumericsV14.cothTail_combo_nine_over_64_le
#print axioms AEGIS.RHMomentNumericsV14.exp_nine_over_128_upper
#print axioms AEGIS.RHMomentNumericsV14.cosh_nine_over_128_sub_one_upper
#print axioms AEGIS.RHMomentNumericsV14.momentGain_nine_over_64
