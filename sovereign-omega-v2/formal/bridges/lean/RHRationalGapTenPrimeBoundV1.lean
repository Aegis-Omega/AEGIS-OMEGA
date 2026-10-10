import RHRationalGapNinePrimeBoundV1
import RHRationalNinePacketPrimeWindowV1
import Mathlib.NumberTheory.ArithmeticFunction.VonMangoldt
import Mathlib.Tactic

/-!
AEGIS Omega -- second non-void rational spacing gap bound V1.

For q = 33/16 and the fine support radius 1/256, gap k=10 has reciprocal
integer window 1383..1403. The only prime-power sample is the prime 1399.

The prime term is bounded conservatively using:
- log 1399 < 8;
- 37 <= sqrt 1399;
- the exact translated log-correlation transport;
- ||logCorrelation|| <= E.

Thus the prime side costs at most 8/37 E. The inherited separated
Archimedean lane costs 1/100 E, giving

  ||B(g, T_{log(q^10)} g)|| <= 837/3700 E.

No 11-packet assembly, larger gap, globalization, or RH claim is made.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHRationalGapTenPrimeBoundV1

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedClosureV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilThreeBlockCrossPrimeV28
open AEGIS.WeilWidthArchCorrelationV25
open AEGIS.WeilSeparatedArchBridgeV31
open AEGIS.WeilThreeBlockAnalyticConstantsV21
open AEGIS.RHRationalNinePacketPrimeWindowV1

def gapTenV1 : ℝ := Real.log (qNineV1 ^ 10)

theorem gapTen_pos_v1 : (1 / 128 : ℝ) < gapTenV1 := by
  unfold gapTenV1
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

theorem log_two_le_gapTen_v1 : Real.log 2 ≤ gapTenV1 := by
  unfold gapTenV1
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

theorem gap_ten_candidate_range_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - gapTenV1| ≤ (1 / 128 : ℝ)) :
    1383 ≤ m ∧ m ≤ 1403 := by
  have h := nat_envelope_of_log_window_v1 hm
    (by norm_num [qNineV1] : 0 < qNineV1 ^ 10)
    (by simpa [gapTenV1] using hw)
  have hlo : (1382 : ℝ) < (m : ℝ) := by
    exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 1404 := by
    exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : (1382 : ℕ) < m := by exact_mod_cast hlo
  have hhiN : m < 1404 := by exact_mod_cast hhi
  omega

private theorem vm_zero_1383_v1 :
    ArithmeticFunction.vonMangoldt 1383 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1383).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1384_v1 :
    ArithmeticFunction.vonMangoldt 1384 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1384).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1385_v1 :
    ArithmeticFunction.vonMangoldt 1385 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1385).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1386_v1 :
    ArithmeticFunction.vonMangoldt 1386 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1386).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1387_v1 :
    ArithmeticFunction.vonMangoldt 1387 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1387).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1388_v1 :
    ArithmeticFunction.vonMangoldt 1388 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1388).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1389_v1 :
    ArithmeticFunction.vonMangoldt 1389 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1389).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1390_v1 :
    ArithmeticFunction.vonMangoldt 1390 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1390).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1391_v1 :
    ArithmeticFunction.vonMangoldt 1391 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1391).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1392_v1 :
    ArithmeticFunction.vonMangoldt 1392 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1392).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1393_v1 :
    ArithmeticFunction.vonMangoldt 1393 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1393).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1394_v1 :
    ArithmeticFunction.vonMangoldt 1394 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1394).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1395_v1 :
    ArithmeticFunction.vonMangoldt 1395 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1395).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1396_v1 :
    ArithmeticFunction.vonMangoldt 1396 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1396).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1397_v1 :
    ArithmeticFunction.vonMangoldt 1397 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1397).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1398_v1 :
    ArithmeticFunction.vonMangoldt 1398 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1398).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1400_v1 :
    ArithmeticFunction.vonMangoldt 1400 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1400).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1401_v1 :
    ArithmeticFunction.vonMangoldt 1401 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1401).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1402_v1 :
    ArithmeticFunction.vonMangoldt 1402 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1402).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem vm_zero_1403_v1 :
    ArithmeticFunction.vonMangoldt 1403 = 0 := by
  apply ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr
  intro hpp
  obtain ⟨k, hk, hkpos, heq⟩ :=
    (isPrimePow_nat_iff_bounded_log_minFac 1403).mp hpp
  norm_num at hk
  interval_cases k <;> norm_num at heq

private theorem prime_1399_v1 : Nat.Prime 1399 := by norm_num

theorem gap_ten_prime_term_zero_outside_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    {n : ℕ} (h1398 : n ≠ 1398) :
    WeilPrimeTermV1
      (mixed (translatePacket g 0) (translatePacket g gapTenV1)) n = 0 := by
  have hm : 0 < n + 1 := by omega
  have hp := mixed_nat_zero_of_positive_gap_v1
    g a 0 gapTenV1 hw (by simpa only [sub_zero] using gapTen_pos_v1)
      (n + 1) hm
  by_cases hwin :
      |Real.log ((n + 1 : ℕ) : ℝ) - gapTenV1| ≤ (1 / 128 : ℝ)
  · have hr := gap_ten_candidate_range_v1 hm hwin
    have hnlo : 1382 ≤ n := by omega
    have hnhi : n ≤ 1402 := by omega
    interval_cases n <;>
      simp_all [WeilPrimeTermV1, vm_zero_1383_v1, vm_zero_1384_v1, vm_zero_1385_v1, vm_zero_1386_v1, vm_zero_1387_v1, vm_zero_1388_v1, vm_zero_1389_v1, vm_zero_1390_v1, vm_zero_1391_v1, vm_zero_1392_v1, vm_zero_1393_v1, vm_zero_1394_v1, vm_zero_1395_v1, vm_zero_1396_v1, vm_zero_1397_v1, vm_zero_1398_v1, vm_zero_1400_v1, vm_zero_1401_v1, vm_zero_1402_v1, vm_zero_1403_v1]
  · have hfar :
        (1 / 128 : ℝ) <
          |Real.log ((n + 1 : ℕ) : ℝ) - gapTenV1| :=
      lt_of_not_ge hwin
    have hi := mixed_inv_nat_zero_outside_gap_v1
      g a 0 gapTenV1 hw (n + 1) hm
        (by simpa only [sub_zero] using hfar)
    unfold WeilPrimeTermV1
    dsimp
    rw [hp, hi]
    simp

theorem gap_ten_prime_sum_single_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0) (translatePacket g gapTenV1)) =
      WeilPrimeTermV1
        (mixed (translatePacket g 0) (translatePacket g gapTenV1)) 1398 := by
  unfold WeilPrimeSumV1
  apply tsum_eq_single 1398
  intro n hn
  exact gap_ten_prime_term_zero_outside_v1 g a hw hn

theorem reciprocal_mixed_norm_le_one_over_37_v1
    (g : WeilCompactSmoothGV1) (m : ℕ)
    (hm : 0 < m) (hm1369 : 1369 ≤ m) :
    ‖(1 / (m : ℂ)) *
      mixed (translatePacket g 0) (translatePacket g gapTenV1) ((m : ℝ)⁻¹)‖ ≤
      (1 / 37 : ℝ) * energy g.1 := by
  have hmpos : (0 : ℝ) < (m : ℝ) := by exact_mod_cast hm
  let α : ℝ := Real.exp (-Real.log (m : ℝ) / 2)
  have hsqrt : (37 : ℝ) ≤ Real.sqrt (m : ℝ) := by
    apply Real.le_sqrt_of_sq_le
    norm_num
    exact_mod_cast hm1369
  have hα : α ≤ (1 / 37 : ℝ) := by
    dsimp [α]
    rw [show -Real.log (m : ℝ) / 2 = -(Real.log (m : ℝ) / 2) by ring,
        Real.exp_neg, Real.exp_half, Real.exp_log hmpos]
    simpa [one_div] using
      (one_div_le_one_div_of_le (by norm_num : (0 : ℝ) < 37) hsqrt)
  have hα0 : 0 ≤ α := by dsimp [α]; positivity
  have ht := exp_half_mul_mixed_translate_v28
    g 0 gapTenV1 (-Real.log (m : ℝ))
  have ht' :
      (α : ℂ) *
          mixed (translatePacket g 0) (translatePacket g gapTenV1) ((m : ℝ)⁻¹) =
        logCorrelationV25 g (-Real.log (m : ℝ) + gapTenV1) := by
    dsimp [α]
    simpa only [Real.exp_neg, Real.exp_log hmpos, zero_sub, sub_zero] using ht
  have hnormeq := congrArg norm ht'
  have hnormα : ‖(α : ℂ)‖ = α := by
    rw [Complex.norm_real, Real.norm_eq_abs, abs_of_nonneg hα0]
  let M : ℝ := ‖mixed (translatePacket g 0)
    (translatePacket g gapTenV1) ((m : ℝ)⁻¹)‖
  have hnormeq' :
      α * M =
        ‖logCorrelationV25 g (-Real.log (m : ℝ) + gapTenV1)‖ := by
    dsimp [M]
    simpa only [norm_mul, hnormα] using hnormeq
  have hcorr := norm_logCorrelation_le_energy_v25
    g (-Real.log (m : ℝ) + gapTenV1)
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
  change (m : ℝ)⁻¹ * M ≤ (1 / 37 : ℝ) * energy g.1
  calc
    (m : ℝ)⁻¹ * M = α * (α * M) := by
      rw [hinv]
      ring
    _ ≤ α * energy g.1 := mul_le_mul_of_nonneg_left hprod hα0
    _ ≤ (1 / 37 : ℝ) * energy g.1 :=
      mul_le_mul_of_nonneg_right hα (energy_nonnegative g.1)

private theorem log_1399_lt_eight_v1 : Real.log 1399 < 8 := by
  calc
    Real.log 1399 < Real.log 2048 :=
      (Real.log_lt_log_iff (by norm_num) (by norm_num)).2 (by norm_num)
    _ = 11 * Real.log 2 := by
      rw [show (2048 : ℝ) = 2 ^ (11 : ℕ) by norm_num, Real.log_pow]
      norm_num
    _ < 8 := by nlinarith [log_two_upper]

theorem prime_term_1399_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    ‖WeilPrimeTermV1
      (mixed (translatePacket g 0) (translatePacket g gapTenV1)) 1398‖ ≤
      (8 / 37 : ℝ) * energy g.1 := by
  have hp := mixed_nat_zero_of_positive_gap_v1
    g a 0 gapTenV1 hw (by simpa only [sub_zero] using gapTen_pos_v1)
      1399 (by norm_num)
  have hr := reciprocal_mixed_norm_le_one_over_37_v1
    g 1399 (by norm_num) (by norm_num)
  have hp' :
      mixed (translatePacket g 0) (translatePacket g gapTenV1) (1399 : ℝ) = 0 := by
    convert hp using 1 <;> norm_num
  have hr' :
      ‖(1 / (1399 : ℂ)) *
        mixed (translatePacket g 0) (translatePacket g gapTenV1)
          ((1399 : ℝ)⁻¹)‖ ≤
        (1 / 37 : ℝ) * energy g.1 := by
    convert hr using 1 <;> norm_num
  have hterm :
      WeilPrimeTermV1
        (mixed (translatePacket g 0) (translatePacket g gapTenV1)) 1398 =
      (Real.log (1399 : ℝ) : ℂ) *
        ((1 / (1399 : ℂ)) *
          mixed (translatePacket g 0) (translatePacket g gapTenV1)
            ((1399 : ℝ)⁻¹)) := by
    unfold WeilPrimeTermV1
    dsimp
    rw [ArithmeticFunction.vonMangoldt_apply_prime prime_1399_v1]
    change
      (Real.log (1399 : ℝ) : ℂ) *
          (mixed (translatePacket g 0) (translatePacket g gapTenV1) (1399 : ℝ) +
            (1 / (1399 : ℂ)) *
              mixed (translatePacket g 0) (translatePacket g gapTenV1)
                ((1399 : ℝ)⁻¹)) =
        (Real.log (1399 : ℝ) : ℂ) *
          ((1 / (1399 : ℂ)) *
            mixed (translatePacket g 0) (translatePacket g gapTenV1)
              ((1399 : ℝ)⁻¹))
    rw [hp']
    simp
  rw [hterm]
  rw [norm_mul, Complex.norm_real, Real.norm_eq_abs]
  rw [abs_of_nonneg (Real.log_nonneg (by norm_num))]
  calc
    Real.log 1399 *
        ‖(1 / (1399 : ℂ)) *
          mixed (translatePacket g 0) (translatePacket g gapTenV1)
            ((1399 : ℝ)⁻¹)‖
      ≤ 8 * ((1 / 37 : ℝ) * energy g.1) :=
        mul_le_mul (le_of_lt log_1399_lt_eight_v1) hr'
          (norm_nonneg _) (by positivity)
    _ = (8 / 37 : ℝ) * energy g.1 := by ring

theorem gap_ten_prime_sum_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    ‖WeilPrimeSumV1
      (mixed (translatePacket g 0) (translatePacket g gapTenV1))‖ ≤
      (8 / 37 : ℝ) * energy g.1 := by
  rw [gap_ten_prime_sum_single_v1 g a hw]
  exact prime_term_1399_norm_v1 g a hw

theorem gap_ten_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0) (translatePacket g gapTenV1)‖ ≤
      (837 / 3700 : ℝ) * energy g.1 := by
  have hprime := gap_ten_prime_sum_norm_v1 g a hw
  have harch := translated_arch_norm_bound
    g a 0 gapTenV1
    (fine_width_implies_width_one_thirty_two_v1 g a hw)
    hm (by simpa only [sub_zero] using log_two_le_gapTen_v1)
  have hzero :
      mixed (translatePacket g 0) (translatePacket g gapTenV1) 1 = 0 := by
    have hgap0 : 0 < gapTenV1 := by linarith [gapTen_pos_v1]
    have hfar : (1 / 128 : ℝ) < |(0 : ℝ) + gapTenV1 - 0| := by
      simpa only [zero_add, sub_zero, abs_of_pos hgap0] using gapTen_pos_v1
    have hz := mixed_translate_zero_of_fine_width_v1
      g a 0 gapTenV1 0 hw hfar
    simpa only [Real.exp_zero] using hz
  unfold B WeilExplicitRightSideV1
  rw [hzero]
  simp only [mul_zero, add_zero]
  calc
    ‖WeilPrimeSumV1
        (mixed (translatePacket g 0) (translatePacket g gapTenV1)) +
      WeilArchimedeanIntegralV1
        (mixed (translatePacket g 0) (translatePacket g gapTenV1))‖
      ≤ ‖WeilPrimeSumV1
          (mixed (translatePacket g 0) (translatePacket g gapTenV1))‖ +
        ‖WeilArchimedeanIntegralV1
          (mixed (translatePacket g 0) (translatePacket g gapTenV1))‖ :=
        norm_add_le _ _
    _ ≤ (837 / 3700 : ℝ) * energy g.1 := by
      nlinarith

end AEGIS.RHRationalGapTenPrimeBoundV1

#print axioms AEGIS.RHRationalGapTenPrimeBoundV1.gap_ten_candidate_range_v1
#print axioms AEGIS.RHRationalGapTenPrimeBoundV1.gap_ten_prime_sum_single_v1
#print axioms AEGIS.RHRationalGapTenPrimeBoundV1.reciprocal_mixed_norm_le_one_over_37_v1
#print axioms AEGIS.RHRationalGapTenPrimeBoundV1.prime_term_1399_norm_v1
#print axioms AEGIS.RHRationalGapTenPrimeBoundV1.gap_ten_prime_sum_norm_v1
#print axioms AEGIS.RHRationalGapTenPrimeBoundV1.gap_ten_B_norm_v1
