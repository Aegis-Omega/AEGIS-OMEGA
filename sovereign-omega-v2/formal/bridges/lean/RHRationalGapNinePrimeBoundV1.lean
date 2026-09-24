import RHFineDiagonalUpgradeV3
import RHRationalNinePacketPrimeWindowV1
import Mathlib.NumberTheory.ArithmeticFunction.VonMangoldt
import Mathlib.Tactic

/-!
AEGIS Omega -- first non-void rational spacing gap bound V1.

For q = 33/16 and the verified fine support radius 1/256, gap k=9 has
reciprocal integer window 671..680. The only prime-power samples are the
primes 673 and 677. Each prime term is bounded by 7/25 E using:
- log p < 7,
- 25 <= sqrt p,
- the exact translated log-correlation transport,
- ||logCorrelation|| <= E.

Thus the prime side costs at most 14/25 E and the inherited separated
Archimedean lane costs 1/100 E, giving

  ||B(g, T_{log(q^9)} g)|| <= 57/100 E.

No larger gap, larger packet family, globalization, or RH claim is made.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHRationalGapNinePrimeBoundV1

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedClosureV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilThreeBlockCrossPrimeV28
open AEGIS.WeilWidthArchCorrelationV25
open AEGIS.WeilSeparatedArchBridgeV31
open AEGIS.WeilThreeBlockAnalyticConstantsV21
open AEGIS.RHRationalNinePacketPrimeWindowV1

def gapNineV1 : ℝ := Real.log (qNineV1 ^ 9)

theorem gapNine_pos_v1 : (1 / 128 : ℝ) < gapNineV1 := by
  unfold gapNineV1
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  have he : Real.exp (1 / 128 : ℝ) < (128 / 127 : ℝ) :=
    exp_one_over_128_upper_v1
  exact he.trans (by norm_num [qNineV1])

theorem log_two_le_gapNine_v1 : Real.log 2 ≤ gapNineV1 := by
  unfold gapNineV1
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

theorem gap_nine_candidate_range_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - gapNineV1| ≤ (1 / 128 : ℝ)) :
    671 ≤ m ∧ m ≤ 680 := by
  have h := nat_envelope_of_log_window_v1 hm
    (by norm_num [qNineV1] : 0 < qNineV1 ^ 9) (by simpa [gapNineV1] using hw)
  have hlo : (670 : ℝ) < (m : ℝ) := by
    exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 681 := by
    exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : (670 : ℕ) < m := by exact_mod_cast hlo
  have hhiN : m < 681 := by exact_mod_cast hhi
  omega

private theorem vm_zero_of_not_prime_pow_671 :
    ArithmeticFunction.vonMangoldt 671 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 671).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_of_not_prime_pow_672 :
    ArithmeticFunction.vonMangoldt 672 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 672).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_of_not_prime_pow_674 :
    ArithmeticFunction.vonMangoldt 674 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 674).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_of_not_prime_pow_675 :
    ArithmeticFunction.vonMangoldt 675 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 675).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_of_not_prime_pow_676 :
    ArithmeticFunction.vonMangoldt 676 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 676).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_of_not_prime_pow_678 :
    ArithmeticFunction.vonMangoldt 678 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 678).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_of_not_prime_pow_679 :
    ArithmeticFunction.vonMangoldt 679 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 679).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_of_not_prime_pow_680 :
    ArithmeticFunction.vonMangoldt 680 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 680).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem prime_673_v1 : Nat.Prime 673 := by norm_num
private theorem prime_677_v1 : Nat.Prime 677 := by norm_num

theorem gap_nine_prime_term_zero_outside_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    {n : ℕ} (h672 : n ≠ 672) (h676 : n ≠ 676) :
    WeilPrimeTermV1
      (mixed (translatePacket g 0) (translatePacket g gapNineV1)) n = 0 := by
  have hm : 0 < n + 1 := by omega
  have hp := mixed_nat_zero_of_positive_gap_v1
    g a 0 gapNineV1 hw (by simpa only [sub_zero] using gapNine_pos_v1) (n + 1) hm
  by_cases hwin :
      |Real.log ((n + 1 : ℕ) : ℝ) - gapNineV1| ≤ (1 / 128 : ℝ)
  · have hr := gap_nine_candidate_range_v1 hm hwin
    have hnlo : 670 ≤ n := by omega
    have hnhi : n ≤ 679 := by omega
    interval_cases n <;>
      simp_all [WeilPrimeTermV1,
        vm_zero_of_not_prime_pow_671, vm_zero_of_not_prime_pow_672,
        vm_zero_of_not_prime_pow_674, vm_zero_of_not_prime_pow_675,
        vm_zero_of_not_prime_pow_676, vm_zero_of_not_prime_pow_678,
        vm_zero_of_not_prime_pow_679, vm_zero_of_not_prime_pow_680]
  · have hfar :
        (1 / 128 : ℝ) <
          |Real.log ((n + 1 : ℕ) : ℝ) - gapNineV1| :=
      lt_of_not_ge hwin
    have hi := mixed_inv_nat_zero_outside_gap_v1
      g a 0 gapNineV1 hw (n + 1) hm (by simpa only [sub_zero] using hfar)
    unfold WeilPrimeTermV1
    dsimp
    rw [hp, hi]
    simp

theorem gap_nine_prime_sum_two_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0) (translatePacket g gapNineV1)) =
      WeilPrimeTermV1
        (mixed (translatePacket g 0) (translatePacket g gapNineV1)) 672 +
      WeilPrimeTermV1
        (mixed (translatePacket g 0) (translatePacket g gapNineV1)) 676 := by
  unfold WeilPrimeSumV1
  rw [tsum_eq_sum (s := {672, 676})]
  · norm_num
  · intro n hn
    simp only [Finset.mem_insert, Finset.mem_singleton, not_or] at hn
    exact gap_nine_prime_term_zero_outside_v1 g a hw hn.1 hn.2

theorem reciprocal_mixed_norm_le_one_over_25_v1
    (g : WeilCompactSmoothGV1) (m : ℕ)
    (hm : 0 < m) (hm625 : 625 ≤ m) :
    ‖(1 / (m : ℂ)) *
      mixed (translatePacket g 0) (translatePacket g gapNineV1) ((m : ℝ)⁻¹)‖ ≤
      (1 / 25 : ℝ) * energy g.1 := by
  have hmpos : (0 : ℝ) < (m : ℝ) := by exact_mod_cast hm
  let α : ℝ := Real.exp (-Real.log (m : ℝ) / 2)
  have hsqrt : (25 : ℝ) ≤ Real.sqrt (m : ℝ) := by
    apply Real.le_sqrt_of_sq_le
    norm_num
    exact_mod_cast hm625
  have hα : α ≤ (1 / 25 : ℝ) := by
    dsimp [α]
    rw [show -Real.log (m : ℝ) / 2 = -(Real.log (m : ℝ) / 2) by ring,
        Real.exp_neg, Real.exp_half, Real.exp_log hmpos]
    simpa [one_div] using
      (one_div_le_one_div_of_le (by norm_num : (0 : ℝ) < 25) hsqrt)
  have hα0 : 0 ≤ α := by dsimp [α]; positivity
  have ht := exp_half_mul_mixed_translate_v28
    g 0 gapNineV1 (-Real.log (m : ℝ))
  have ht' :
      (α : ℂ) *
          mixed (translatePacket g 0) (translatePacket g gapNineV1) ((m : ℝ)⁻¹) =
        logCorrelationV25 g (-Real.log (m : ℝ) + gapNineV1) := by
    dsimp [α]
    simpa only [Real.exp_neg, Real.exp_log hmpos, zero_sub, sub_zero] using ht
  have hnormeq := congrArg norm ht'
  have hnormα : ‖(α : ℂ)‖ = α := by
    rw [Complex.norm_real, Real.norm_eq_abs, abs_of_nonneg hα0]
  let M : ℝ := ‖mixed (translatePacket g 0)
    (translatePacket g gapNineV1) ((m : ℝ)⁻¹)‖
  have hnormeq' :
      α * M =
        ‖logCorrelationV25 g (-Real.log (m : ℝ) + gapNineV1)‖ := by
    dsimp [M]
    simpa only [norm_mul, hnormα] using hnormeq
  have hcorr := norm_logCorrelation_le_energy_v25
    g (-Real.log (m : ℝ) + gapNineV1)
  have hprod : α * M ≤ energy g.1 := by
    rw [hnormeq']
    exact hcorr
  have hinv : (m : ℝ)⁻¹ = α * α := by
    dsimp [α]
    rw [← Real.exp_add]
    have harg :
        -Real.log (m : ℝ) / 2 + -Real.log (m : ℝ) / 2 =
          -Real.log (m : ℝ) := by ring
    rw [harg, Real.exp_neg, Real.exp_log hmpos]
  rw [norm_mul]
  have hscalar : ‖(1 / (m : ℂ))‖ = (m : ℝ)⁻¹ := by
    simp [one_div]
  rw [hscalar]
  change (m : ℝ)⁻¹ * M ≤ (1 / 25 : ℝ) * energy g.1
  calc
    (m : ℝ)⁻¹ * M = α * (α * M) := by
      rw [hinv]
      ring
    _ ≤ α * energy g.1 := mul_le_mul_of_nonneg_left hprod hα0
    _ ≤ (1 / 25 : ℝ) * energy g.1 :=
      mul_le_mul_of_nonneg_right hα (energy_nonnegative g.1)

private theorem log_673_lt_seven_v1 : Real.log 673 < 7 := by
  calc
    Real.log 673 < Real.log 1024 :=
      (Real.log_lt_log_iff (by norm_num) (by norm_num)).2 (by norm_num)
    _ = 10 * Real.log 2 := by
      rw [show (1024 : ℝ) = 2 ^ (10 : ℕ) by norm_num, Real.log_pow]
      norm_num
    _ < 7 := by nlinarith [log_two_upper]

private theorem log_677_lt_seven_v1 : Real.log 677 < 7 := by
  calc
    Real.log 677 < Real.log 1024 :=
      (Real.log_lt_log_iff (by norm_num) (by norm_num)).2 (by norm_num)
    _ = 10 * Real.log 2 := by
      rw [show (1024 : ℝ) = 2 ^ (10 : ℕ) by norm_num, Real.log_pow]
      norm_num
    _ < 7 := by nlinarith [log_two_upper]

theorem prime_term_673_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    ‖WeilPrimeTermV1
      (mixed (translatePacket g 0) (translatePacket g gapNineV1)) 672‖ ≤
      (7 / 25 : ℝ) * energy g.1 := by
  have hp := mixed_nat_zero_of_positive_gap_v1
    g a 0 gapNineV1 hw (by simpa only [sub_zero] using gapNine_pos_v1) 673 (by norm_num)
  have hr := reciprocal_mixed_norm_le_one_over_25_v1 g 673 (by norm_num) (by norm_num)
  have hp' :
      mixed (translatePacket g 0) (translatePacket g gapNineV1) (673 : ℝ) = 0 := by
    convert hp using 1 <;> norm_num
  have hr' :
      ‖(1 / (673 : ℂ)) *
        mixed (translatePacket g 0) (translatePacket g gapNineV1)
          ((673 : ℝ)⁻¹)‖ ≤
        (1 / 25 : ℝ) * energy g.1 := by
    convert hr using 1 <;> norm_num
  have hterm :
      WeilPrimeTermV1
        (mixed (translatePacket g 0) (translatePacket g gapNineV1)) 672 =
      (Real.log (673 : ℝ) : ℂ) *
        ((1 / (673 : ℂ)) *
          mixed (translatePacket g 0) (translatePacket g gapNineV1)
            ((673 : ℝ)⁻¹)) := by
    unfold WeilPrimeTermV1
    dsimp
    rw [ArithmeticFunction.vonMangoldt_apply_prime prime_673_v1]
    change
      (Real.log (673 : ℝ) : ℂ) *
          (mixed (translatePacket g 0) (translatePacket g gapNineV1) (673 : ℝ) +
            (1 / (673 : ℂ)) *
              mixed (translatePacket g 0) (translatePacket g gapNineV1)
                ((673 : ℝ)⁻¹)) =
        (Real.log (673 : ℝ) : ℂ) *
          ((1 / (673 : ℂ)) *
            mixed (translatePacket g 0) (translatePacket g gapNineV1)
              ((673 : ℝ)⁻¹))
    rw [hp']
    simp
  rw [hterm]
  simp only [norm_mul, Complex.norm_real, Real.norm_eq_abs]
  rw [abs_of_nonneg (Real.log_nonneg (by norm_num))]
  calc
    Real.log 673 *
        ‖(1 / (673 : ℂ)) *
          mixed (translatePacket g 0) (translatePacket g gapNineV1) ((673 : ℝ)⁻¹)‖
      ≤ 7 * ((1 / 25 : ℝ) * energy g.1) :=
        mul_le_mul (le_of_lt log_673_lt_seven_v1) hr'
          (norm_nonneg _) (by positivity)
    _ = (7 / 25 : ℝ) * energy g.1 := by ring

theorem prime_term_677_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    ‖WeilPrimeTermV1
      (mixed (translatePacket g 0) (translatePacket g gapNineV1)) 676‖ ≤
      (7 / 25 : ℝ) * energy g.1 := by
  have hp := mixed_nat_zero_of_positive_gap_v1
    g a 0 gapNineV1 hw (by simpa only [sub_zero] using gapNine_pos_v1) 677 (by norm_num)
  have hr := reciprocal_mixed_norm_le_one_over_25_v1 g 677 (by norm_num) (by norm_num)
  have hp' :
      mixed (translatePacket g 0) (translatePacket g gapNineV1) (677 : ℝ) = 0 := by
    convert hp using 1 <;> norm_num
  have hr' :
      ‖(1 / (677 : ℂ)) *
        mixed (translatePacket g 0) (translatePacket g gapNineV1)
          ((677 : ℝ)⁻¹)‖ ≤
        (1 / 25 : ℝ) * energy g.1 := by
    convert hr using 1 <;> norm_num
  have hterm :
      WeilPrimeTermV1
        (mixed (translatePacket g 0) (translatePacket g gapNineV1)) 676 =
      (Real.log (677 : ℝ) : ℂ) *
        ((1 / (677 : ℂ)) *
          mixed (translatePacket g 0) (translatePacket g gapNineV1)
            ((677 : ℝ)⁻¹)) := by
    unfold WeilPrimeTermV1
    dsimp
    rw [ArithmeticFunction.vonMangoldt_apply_prime prime_677_v1]
    change
      (Real.log (677 : ℝ) : ℂ) *
          (mixed (translatePacket g 0) (translatePacket g gapNineV1) (677 : ℝ) +
            (1 / (677 : ℂ)) *
              mixed (translatePacket g 0) (translatePacket g gapNineV1)
                ((677 : ℝ)⁻¹)) =
        (Real.log (677 : ℝ) : ℂ) *
          ((1 / (677 : ℂ)) *
            mixed (translatePacket g 0) (translatePacket g gapNineV1)
              ((677 : ℝ)⁻¹))
    rw [hp']
    simp
  rw [hterm]
  simp only [norm_mul, Complex.norm_real, Real.norm_eq_abs]
  rw [abs_of_nonneg (Real.log_nonneg (by norm_num))]
  calc
    Real.log 677 *
        ‖(1 / (677 : ℂ)) *
          mixed (translatePacket g 0) (translatePacket g gapNineV1) ((677 : ℝ)⁻¹)‖
      ≤ 7 * ((1 / 25 : ℝ) * energy g.1) :=
        mul_le_mul (le_of_lt log_677_lt_seven_v1) hr'
          (norm_nonneg _) (by positivity)
    _ = (7 / 25 : ℝ) * energy g.1 := by ring

theorem gap_nine_prime_sum_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    ‖WeilPrimeSumV1
      (mixed (translatePacket g 0) (translatePacket g gapNineV1))‖ ≤
      (14 / 25 : ℝ) * energy g.1 := by
  rw [gap_nine_prime_sum_two_v1 g a hw]
  calc
    _ ≤ ‖WeilPrimeTermV1
          (mixed (translatePacket g 0) (translatePacket g gapNineV1)) 672‖ +
        ‖WeilPrimeTermV1
          (mixed (translatePacket g 0) (translatePacket g gapNineV1)) 676‖ :=
      norm_add_le _ _
    _ ≤ (14 / 25 : ℝ) * energy g.1 := by
      linarith [prime_term_673_norm_v1 g a hw, prime_term_677_norm_v1 g a hw]

theorem gap_nine_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0) (translatePacket g gapNineV1)‖ ≤
      (57 / 100 : ℝ) * energy g.1 := by
  have hprime := gap_nine_prime_sum_norm_v1 g a hw
  have harch := translated_arch_norm_bound
    g a 0 gapNineV1
    (fine_width_implies_width_one_thirty_two_v1 g a hw)
    hm (by simpa only [sub_zero] using log_two_le_gapNine_v1)
  have hzero :
      mixed (translatePacket g 0) (translatePacket g gapNineV1) 1 = 0 := by
    have hgap0 : 0 < gapNineV1 := by
      linarith [gapNine_pos_v1]
    have hfar : (1 / 128 : ℝ) < |(0 : ℝ) + gapNineV1 - 0| := by
      simpa only [zero_add, sub_zero, abs_of_pos hgap0] using gapNine_pos_v1
    have hz := mixed_translate_zero_of_fine_width_v1
      g a 0 gapNineV1 0 hw hfar
    simpa only [Real.exp_zero] using hz
  unfold B WeilExplicitRightSideV1
  rw [hzero]
  simp only [mul_zero, add_zero]
  calc
    ‖WeilPrimeSumV1
        (mixed (translatePacket g 0) (translatePacket g gapNineV1)) +
      WeilArchimedeanIntegralV1
        (mixed (translatePacket g 0) (translatePacket g gapNineV1))‖
      ≤ ‖WeilPrimeSumV1
          (mixed (translatePacket g 0) (translatePacket g gapNineV1))‖ +
        ‖WeilArchimedeanIntegralV1
          (mixed (translatePacket g 0) (translatePacket g gapNineV1))‖ :=
        norm_add_le _ _
    _ ≤ (57 / 100 : ℝ) * energy g.1 := by linarith

end AEGIS.RHRationalGapNinePrimeBoundV1

#print axioms AEGIS.RHRationalGapNinePrimeBoundV1.gap_nine_candidate_range_v1
#print axioms AEGIS.RHRationalGapNinePrimeBoundV1.gap_nine_prime_sum_two_v1
#print axioms AEGIS.RHRationalGapNinePrimeBoundV1.reciprocal_mixed_norm_le_one_over_25_v1
#print axioms AEGIS.RHRationalGapNinePrimeBoundV1.prime_term_673_norm_v1
#print axioms AEGIS.RHRationalGapNinePrimeBoundV1.prime_term_677_norm_v1
#print axioms AEGIS.RHRationalGapNinePrimeBoundV1.gap_nine_prime_sum_norm_v1
#print axioms AEGIS.RHRationalGapNinePrimeBoundV1.gap_nine_B_norm_v1
