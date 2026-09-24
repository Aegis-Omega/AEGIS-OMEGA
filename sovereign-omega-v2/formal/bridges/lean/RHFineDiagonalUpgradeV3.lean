import RHRationalNinePacketPrimeWindowV1
import RHNarrowDiagonalUpgradeV2
import Mathlib.Tactic

/-!
AEGIS Omega -- fine-support diagonal upgrade V3.

The existing gFine construction has actual log-support half-width 1/256.
Therefore its autocorrelation vanishes for u > 1/128, one full dyadic band
earlier than the V2 narrow theorem.

On (1/128, 1/64] the transformed Archimedean diagonal integrand is at most
-63 E. Together with the inherited (1/64, 1/32] bound -16 E, this improves
the rational diagonal coercivity from 32/25 to 5671/3200.

This is a finite-support diagonal theorem only. No off-diagonal, globalization,
universal Weil sign, or RH conclusion is asserted.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set MeasureTheory Complex
set_option autoImplicit false
noncomputable section

namespace AEGIS.RHFineDiagonalUpgradeV3

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilWidthArchCorrelationV25
open AEGIS.WeilWidthArchBudgetV26
open AEGIS.WeilWidthArchIntegralV27
open AEGIS.WeilWidthDiagonalArchFrontierV24
open AEGIS.WeilDiagonalKernelReductionV21
open AEGIS.WeilThreeBlockAnalyticConstantsV21
open AEGIS.WeilMixedAlgebraV2
open AEGIS.RHNarrowDiagonalUpgradeV2
open AEGIS.RHRationalNinePacketPrimeWindowV1

theorem fine_implies_width_one_sixty_four_v3
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WidthOneSixtyFourAt g a := by
  intro t ht
  have h := hw ht
  exact ⟨by linarith [h.1], by linarith [h.2]⟩

theorem fine_implies_retained_v3
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WidthOneThirtyTwoAt g a :=
  narrow_implies_retained_v2 g a (fine_implies_width_one_sixty_four_v3 g a hw)

theorem fine_autocorrelation_zero_v3
    (g : WeilCompactSmoothGV1) (a u : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hu : (1 / 128 : ℝ) < u) :
    WeilAutocorrelationV1 g (Real.exp u) = 0 := by
  have hcorr := logCorrelation_zero_of_fine_width_abs_v1
    g a u hw (by
      rw [abs_of_pos (by linarith)]
      exact hu)
  rw [logCorrelation_eq_autocorrelation_v25] at hcorr
  have he : (Real.exp (u / 2) : ℂ) ≠ 0 := by simp
  exact (mul_eq_zero.mp hcorr).resolve_left he

theorem sinh_one_over_64_upper_v3
    (u : ℝ) (hu : u ≤ (1 / 64 : ℝ)) :
    Real.sinh u ≤ (1 / 63 : ℝ) := by
  have he : Real.exp u ≤ (64 / 63 : ℝ) :=
    (Real.exp_le_exp.mpr hu).trans exp_one_over_64_upper.le
  have hn : (63 / 64 : ℝ) ≤ Real.exp (-u) := by
    linarith [Real.add_one_le_exp (-u)]
  rw [Real.sinh_eq]
  linarith

theorem fine_middle_pointwise_v3
    (g : WeilCompactSmoothGV1) (a u : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hu : u ∈ Ioc (1 / 128 : ℝ) (1 / 64 : ℝ)) :
    widthArchLogIntegrandV26 g u ≤ -63 * energy g.1 := by
  have hE := energy_nonnegative g.1
  have hp : 0 < Real.sinh u :=
    AEGIS.WeilArchimedeanCothTailV1.sinh_pos_of_pos (by linarith [hu.1])
  have hs := sinh_one_over_64_upper_v3 u hu.2
  have hm := mul_le_mul_of_nonneg_left hs hE
  unfold widthArchLogIntegrandV26
  rw [fine_autocorrelation_zero_v3 g a u hw hu.1]
  simp only [Complex.zero_re, mul_zero, zero_sub]
  apply (div_le_iff₀ hp).2
  nlinarith

theorem fine_inner_integral_upgrade_v3
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    (∫ u in Ioc (0 : ℝ) (1 / 32 : ℝ), widthArchLogIntegrandV26 g u) ≤
      energy g.1 * diagonalSmallV21 - (95 / 128 : ℝ) * energy g.1 := by
  let C : ℝ := energy g.1 * (Real.exp (1 / 64 : ℝ) / 2)
  have hE := energy_nonnegative g.1
  have hC : 0 ≤ C := by dsimp [C]; positivity
  have hfull := width_arch_log_integrableOn_v27 g
  have hA : IntegrableOn (widthArchLogIntegrandV26 g)
      (Ioc (0 : ℝ) (1 / 128 : ℝ)) :=
    hfull.mono_set (by intro u hu; exact hu.1)
  have hB : IntegrableOn (widthArchLogIntegrandV26 g)
      (Ioc (1 / 128 : ℝ) (1 / 64 : ℝ)) :=
    hfull.mono_set (by intro u hu; change 0 < u; linarith [hu.1])
  have hCint : IntegrableOn (widthArchLogIntegrandV26 g)
      (Ioc (1 / 64 : ℝ) (1 / 32 : ℝ)) :=
    hfull.mono_set (by intro u hu; change 0 < u; linarith [hu.1])
  have hAB : IntegrableOn (widthArchLogIntegrandV26 g)
      (Ioc (0 : ℝ) (1 / 64 : ℝ)) :=
    hfull.mono_set (by intro u hu; exact hu.1)

  have hleft :
      (∫ u in Ioc (0 : ℝ) (1 / 128 : ℝ), widthArchLogIntegrandV26 g u) ≤
        energy g.1 * diagonalSmallV21 := by
    calc
      _ ≤ ∫ _u in Ioc (0 : ℝ) (1 / 128 : ℝ), C := by
        apply setIntegral_mono_on hA continuous_const.integrableOn_Ioc measurableSet_Ioc
        intro u hu
        exact width_arch_log_inner_pointwise_v26 g hu.1 (by linarith [hu.2])
      _ = (1 / 128 : ℝ) * C := by
        rw [setIntegral_const, smul_eq_mul,
          Real.volume_real_Ioc_of_le (by norm_num : (0 : ℝ) ≤ 1 / 128)]
        ring
      _ ≤ energy g.1 * diagonalSmallV21 := by
        dsimp [C, diagonalSmallV21]
        have he : 0 ≤ Real.exp (1 / 64 : ℝ) := (Real.exp_pos _).le
        nlinarith [mul_nonneg hE he]

  have hmiddle :
      (∫ u in Ioc (1 / 128 : ℝ) (1 / 64 : ℝ), widthArchLogIntegrandV26 g u) ≤
        -(63 / 128 : ℝ) * energy g.1 := by
    calc
      _ ≤ ∫ _u in Ioc (1 / 128 : ℝ) (1 / 64 : ℝ), -63 * energy g.1 := by
        apply setIntegral_mono_on hB continuous_const.integrableOn_Ioc measurableSet_Ioc
        intro u hu
        exact fine_middle_pointwise_v3 g a u hw hu
      _ = _ := by
        rw [setIntegral_const, smul_eq_mul,
          Real.volume_real_Ioc_of_le
            (by norm_num : (1 / 128 : ℝ) ≤ 1 / 64)]
        ring

  have hright :
      (∫ u in Ioc (1 / 64 : ℝ) (1 / 32 : ℝ), widthArchLogIntegrandV26 g u) ≤
        -(1 / 4 : ℝ) * energy g.1 := by
    calc
      _ ≤ ∫ _u in Ioc (1 / 64 : ℝ) (1 / 32 : ℝ), -16 * energy g.1 := by
        apply setIntegral_mono_on hCint continuous_const.integrableOn_Ioc measurableSet_Ioc
        intro u hu
        exact narrow_middle_pointwise_v2 g a u
          (fine_implies_width_one_sixty_four_v3 g a hw) hu
      _ = _ := by
        rw [setIntegral_const, smul_eq_mul,
          Real.volume_real_Ioc_of_le
            (by norm_num : (1 / 64 : ℝ) ≤ 1 / 32)]
        ring

  have hABeq :
      Ioc (0 : ℝ) (1 / 128 : ℝ) ∪ Ioc (1 / 128 : ℝ) (1 / 64 : ℝ) =
        Ioc (0 : ℝ) (1 / 64 : ℝ) :=
    Set.Ioc_union_Ioc_eq_Ioc (by norm_num) (by norm_num)
  have hABdisj :
      Disjoint (Ioc (0 : ℝ) (1 / 128 : ℝ))
        (Ioc (1 / 128 : ℝ) (1 / 64 : ℝ)) := by
    rw [Set.disjoint_left]
    intro u h1 h2
    linarith [h1.2, h2.1]
  have hABint :
      (∫ u in Ioc (0 : ℝ) (1 / 64 : ℝ), widthArchLogIntegrandV26 g u) =
        (∫ u in Ioc (0 : ℝ) (1 / 128 : ℝ), widthArchLogIntegrandV26 g u) +
        ∫ u in Ioc (1 / 128 : ℝ) (1 / 64 : ℝ), widthArchLogIntegrandV26 g u := by
    rw [← hABeq, setIntegral_union hABdisj measurableSet_Ioc hA hB]

  have hFULL_eq :
      Ioc (0 : ℝ) (1 / 64 : ℝ) ∪ Ioc (1 / 64 : ℝ) (1 / 32 : ℝ) =
        Ioc (0 : ℝ) (1 / 32 : ℝ) :=
    Set.Ioc_union_Ioc_eq_Ioc (by norm_num) (by norm_num)
  have hFULL_disj :
      Disjoint (Ioc (0 : ℝ) (1 / 64 : ℝ))
        (Ioc (1 / 64 : ℝ) (1 / 32 : ℝ)) := by
    rw [Set.disjoint_left]
    intro u h1 h2
    linarith [h1.2, h2.1]
  rw [← hFULL_eq, setIntegral_union hFULL_disj measurableSet_Ioc hAB hCint,
      hABint]
  linarith

theorem fine_arch_budget_upgrade_v3
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    (WeilArchimedeanIntegralV1 (WeilAutocorrelationV1 g)).re ≤
      energy g.1 * (diagonalSmallV21 - diagonalTailV24) -
        (95 / 128 : ℝ) * energy g.1 := by
  rw [archimedean_real_eq_log_integral_v27, width_arch_log_split_v27,
    width_arch_tail_integral_eq_v27 g a (fine_implies_retained_v3 g a hw)]
  have hi := fine_inner_integral_upgrade_v3 g a hw
  linarith

theorem fine_diagonal_5671_over_3200_v3
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    (5671 / 3200 : ℝ) * energy g.1 ≤ -(B g g).re := by
  have hp := width_diagonal_prime_sum_zero_v24 g a
    (fine_implies_retained_v3 g a hw)
  have hE := energy_nonnegative g.1
  have hf :
      (103 / 100 : ℝ) ≤
        diagonalTailV24 - diagonalKappaV21 - diagonalSmallV21 := by
    have ht := diagonal_tail_gt_six_log_two_v24
    have hc := diagonal_constant_floor
    have hn := certificate_diagonal_threshold
    unfold diagonalKappaV21 diagonalSmallV21
    linarith
  have hm := mul_le_mul_of_nonneg_left hf hE
  have hb := fine_arch_budget_upgrade_v3 g a hw
  rw [actual_diagonal_rhs_decomposition g hp]
  nlinarith

end AEGIS.RHFineDiagonalUpgradeV3

#print axioms AEGIS.RHFineDiagonalUpgradeV3.fine_autocorrelation_zero_v3
#print axioms AEGIS.RHFineDiagonalUpgradeV3.sinh_one_over_64_upper_v3
#print axioms AEGIS.RHFineDiagonalUpgradeV3.fine_middle_pointwise_v3
#print axioms AEGIS.RHFineDiagonalUpgradeV3.fine_inner_integral_upgrade_v3
#print axioms AEGIS.RHFineDiagonalUpgradeV3.fine_arch_budget_upgrade_v3
#print axioms AEGIS.RHFineDiagonalUpgradeV3.fine_diagonal_5671_over_3200_v3
