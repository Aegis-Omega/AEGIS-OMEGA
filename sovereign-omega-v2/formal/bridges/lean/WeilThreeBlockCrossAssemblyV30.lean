import WeilThreeBlockPrimeEvaluationV30
import WeilThreeBlockNormBridgeV21

/-!
Candidate conditional assembly, not yet kernel replayed.
The three actual Archimedean integral norm bounds are EXPLICIT hypotheses.
This file does not discharge them, assert universal positivity, or prove RH.
-/
open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators
set_option autoImplicit false
noncomputable section
namespace AEGIS.WeilThreeBlockCrossAssemblyV30
open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedClosureV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilThreeBlockCrossPrimeWindowV29
open AEGIS.WeilThreeBlockPrimeEvaluationV30
open AEGIS.WeilThreeBlockAnalyticConstantsV21
open AEGIS.WeilThreeBlockNormBridgeV21
open AEGIS.WeilWidthArchIntegralV27

theorem adjacent_rational_arch_margin :
    (75 / 9086 : ℝ) < 1 / 100 := by norm_num

theorem outer_rational_arch_margin :
    (15 / 13216 : ℝ) < 1 / 100 := by norm_num

private theorem mixed_bound_of_prime_and_arch
    (p q : WeilCompactSmoothGV1) (E c k : ℝ)
    (hE : 0 ≤ E) (hc : 0 ≤ c) (hck : c ≤ k)
    (hzero : mixed p q 1 = 0)
    (hprime : WeilPrimeSumV1 (mixed p q) = ((c * E : ℝ) : ℂ))
    (harch : ‖WeilArchimedeanIntegralV1 (mixed p q)‖ ≤ (1 / 100 : ℝ) * E) :
    ‖B p q‖ ≤ (k + 1 / 100) * E := by
  have hp : ‖WeilPrimeSumV1 (mixed p q)‖ = c * E := by
    rw [hprime, Complex.norm_real, Real.norm_eq_abs, abs_of_nonneg (mul_nonneg hc hE)]
  unfold B WeilExplicitRightSideV1
  rw [hzero, mul_zero, add_zero]
  calc
    ‖WeilPrimeSumV1 (mixed p q) + WeilArchimedeanIntegralV1 (mixed p q)‖
        ≤ ‖WeilPrimeSumV1 (mixed p q)‖ + ‖WeilArchimedeanIntegralV1 (mixed p q)‖ := norm_add_le _ _
    _ ≤ c * E + (1 / 100 : ℝ) * E := by rw [hp]; exact add_le_add_left harch _
    _ ≤ (k + 1 / 100) * E := by nlinarith [mul_le_mul_of_nonneg_right hck hE]

theorem three_cross_bounds_of_arch
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a)
    (harch01 : ‖WeilArchimedeanIntegralV1 (mixed (gMinus g) (gZero g))‖ ≤
      (1 / 100 : ℝ) * energy g.1)
    (harch02 : ‖WeilArchimedeanIntegralV1 (mixed (gMinus g) (gPlus g))‖ ≤
      (1 / 100 : ℝ) * energy g.1)
    (harch12 : ‖WeilArchimedeanIntegralV1 (mixed (gZero g) (gPlus g))‖ ≤
      (1 / 100 : ℝ) * energy g.1) :
    ‖B (gMinus g) (gZero g)‖ ≤ (51 / 100 : ℝ) * energy g.1 ∧
    ‖B (gMinus g) (gPlus g)‖ ≤ (9 / 25 : ℝ) * energy g.1 ∧
    ‖B (gZero g) (gPlus g)‖ ≤ (51 / 100 : ℝ) * energy g.1 := by
  have hE := energy_nonnegative g.1
  have hlog : 0 ≤ Real.log 2 := Real.log_nonneg (by norm_num)
  have h01zero : mixed (gMinus g) (gZero g) 1 = 0 := by
    simpa using adjacent_mixed_nat_zero_v29 g a hw 1 (by norm_num)
  have h02zero : mixed (gMinus g) (gPlus g) 1 = 0 := by
    simpa using outer_mixed_nat_zero_v29 g a hw 1 (by norm_num)
  have h12zero : mixed (gZero g) (gPlus g) 1 = 0 := by
    rw [adjacent_mixed_shift_eq g 1 (by norm_num)]
    exact h01zero
  constructor
  · convert mixed_bound_of_prime_and_arch (gMinus g) (gZero g) (energy g.1)
      (Real.log 2 / Real.sqrt 2) (1 / 2) hE
      (div_nonneg hlog (Real.sqrt_nonneg _)) prime_adjacent_scalar_upper.le
      h01zero (adjacent_prime_sum_exact g a hw) harch01 using 1 <;> norm_num
  constructor
  · convert mixed_bound_of_prime_and_arch (gMinus g) (gPlus g) (energy g.1)
      (Real.log 2 / 2) (7 / 20) hE (div_nonneg hlog (by norm_num))
      prime_outer_scalar_upper.le h02zero (outer_prime_sum_exact g a hw) harch02
      using 1 <;> norm_num
  · convert mixed_bound_of_prime_and_arch (gZero g) (gPlus g) (energy g.1)
      (Real.log 2 / Real.sqrt 2) (1 / 2) hE
      (div_nonneg hlog (Real.sqrt_nonneg _)) prime_adjacent_scalar_upper.le
      h12zero (right_adjacent_prime_sum_exact g a hw) harch12 using 1 <;> norm_num

theorem three_block_bound_of_arch
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a)
    (z0 z1 z2 : ℂ)
    (harch01 : ‖WeilArchimedeanIntegralV1 (mixed (gMinus g) (gZero g))‖ ≤
      (1 / 100 : ℝ) * energy g.1)
    (harch02 : ‖WeilArchimedeanIntegralV1 (mixed (gMinus g) (gPlus g))‖ ≤
      (1 / 100 : ℝ) * energy g.1)
    (harch12 : ‖WeilArchimedeanIntegralV1 (mixed (gZero g) (gPlus g))‖ ≤
      (1 / 100 : ℝ) * energy g.1) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1 (combo z0 z1 z2 (gMinus g) (gZero g) (gPlus g)))).re ≤
      -(1 / 10 : ℝ) * energy (combo z0 z1 z2 (gMinus g) (gZero g) (gPlus g)).1 := by
  obtain ⟨hd01, hd02, hd12⟩ := three_blocks_pairwise_disjoint g a hw
  obtain ⟨he0, he1, he2⟩ := three_blocks_energy g
  obtain ⟨hb01, hb02, hb12⟩ := three_cross_bounds_of_arch g a hw harch01 harch02 harch12
  have hw0 := translate_logSupportIn g (-Real.log 2) _ _ hw
  have hw1 := translate_logSupportIn g 0 _ _ hw
  have hw2 := translate_logSupportIn g (Real.log 2) _ _ hw
  have h0 : WidthOneThirtyTwoAt (gMinus g) (a - Real.log 2) := by
    change LogSupportIn (translatePacket g (-Real.log 2))
      (a - Real.log 2 - 1 / 64) (a - Real.log 2 + 1 / 64)
    convert hw0 using 1 <;> ring
  have h1 : WidthOneThirtyTwoAt (gZero g) a := by
    simpa [WidthOneThirtyTwoAt, gZero] using hw1
  have h2 : WidthOneThirtyTwoAt (gPlus g) (a + Real.log 2) := by
    change LogSupportIn (translatePacket g (Real.log 2))
      (a + Real.log 2 - 1 / 64) (a + Real.log 2 + 1 / 64)
    convert hw2 using 1 <;> ring
  have hl01 : l2 (gMinus g).1 * l2 (gZero g).1 = energy g.1 := by
    rw [l2, l2, he0, he1, ← pow_two, Real.sq_sqrt (energy_nonnegative g.1)]
  have hl02 : l2 (gMinus g).1 * l2 (gPlus g).1 = energy g.1 := by
    rw [l2, l2, he0, he2, ← pow_two, Real.sq_sqrt (energy_nonnegative g.1)]
  have hl12 : l2 (gZero g).1 * l2 (gPlus g).1 = energy g.1 := by
    rw [l2, l2, he1, he2, ← pow_two, Real.sq_sqrt (energy_nonnegative g.1)]
  apply actual_three_block_l2_bound z0 z1 z2 (gMinus g) (gZero g) (gPlus g)
      hd01 hd02 hd12
  · simpa [square_l2] using width_diagonal_103_over_100_v27 (gMinus g) _ h0
  · simpa [square_l2] using width_diagonal_103_over_100_v27 (gZero g) _ h1
  · simpa [square_l2] using width_diagonal_103_over_100_v27 (gPlus g) _ h2
  · simpa only [mul_assoc, hl01] using hb01
  · simpa only [mul_assoc, hl02] using hb02
  · simpa only [mul_assoc, hl12] using hb12

end AEGIS.WeilThreeBlockCrossAssemblyV30

#print axioms AEGIS.WeilThreeBlockCrossAssemblyV30.three_cross_bounds_of_arch
#print axioms AEGIS.WeilThreeBlockCrossAssemblyV30.three_block_bound_of_arch
