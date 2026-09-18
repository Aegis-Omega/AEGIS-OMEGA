import WeilWidthArchCorrelationV25
import Mathlib.Analysis.SpecialFunctions.Trigonometric.DerivHyp
import Mathlib.Tactic

/-!
AEGIS Ω — width-1/32 actual Archimedean budget V2.6.

This child consumes only the V2.5 logarithmic correlation facts and the already
verified repository Archimedean convergence machinery.

For
  C_g(u) = ∫ h(v+u) conj(h(v)) dv,
  h(t) = exp(t/2) g(exp t),
the repository Archimedean integral is rewritten exactly as

  ∫_{u>0} (exp(u/2) Re C_g(u) - energy(g)) / sinh(u) du.

On 0 < u <= 1/32, the V2.5 energy bound controls Re C_g(u).
On u > 1/32, the width theorem makes C_g(u)=0, leaving exactly the
negative 1/sinh tail already kernelized in V2.4.

No off-diagonal estimate, global Weil positivity, RH conclusion, merge, or
authority effect is asserted here.
-/

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false

noncomputable section

namespace AEGIS.WeilWidthArchBudgetV26

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilDiagonalKernelReductionV21
open AEGIS.WeilWidthDiagonalArchFrontierV24
open AEGIS.WeilWidthArchCorrelationV25
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilArchimedeanCothTailV1

def archLogKernelV26 (g : WeilCompactSmoothGV1) (u : ℝ) : ℝ :=
  (Real.exp (u / 2) * (logCorrelationV25 g u).re - energy g.1) / Real.sinh u

private theorem autocorrelation_one_eq_energy_v26
    (g : WeilCompactSmoothGV1) :
    WeilAutocorrelationV1 g 1 = (energy g.1 : ℂ) := by
  apply Complex.ext
  · simpa using autocorrelation_one_re_eq_energy g
  · simpa using weil_autocorrelation_one_real_v1 g

private theorem correlation_re_v26
    (g : WeilCompactSmoothGV1) (u : ℝ) :
    (logCorrelationV25 g u).re =
      Real.exp (u / 2) * (WeilAutocorrelationV1 g (Real.exp u)).re := by
  rw [logCorrelation_eq_autocorrelation_v25]
  simp only [Complex.mul_re, Complex.ofReal_re, Complex.ofReal_im,
    zero_mul, sub_zero]

private theorem arch_log_kernel_pointwise_v26
    (g : WeilCompactSmoothGV1) {u : ℝ} (hu : 0 < u) :
    (Real.exp u •
      WeilArchimedeanIntegrandV1
        (WeilAutocorrelationV1 g) (Real.exp u)).re =
      archLogKernelV26 g u := by
  let A : ℂ := WeilAutocorrelationV1 g (Real.exp u)
  have hx : 0 < Real.exp u := Real.exp_pos u
  have hxC : ((Real.exp u : ℝ) : ℂ) ≠ 0 := by
    exact Complex.ofReal_ne_zero.mpr hx.ne'
  have hsinh : 0 < Real.sinh u := sinh_pos_of_pos hu
  have hsinhC : ((Real.sinh u : ℝ) : ℂ) ≠ 0 := by
    exact Complex.ofReal_ne_zero.mpr hsinh.ne'
  have hrec :=
    weil_autocorrelation_reciprocal_v1 g
      (x := Real.exp u) hx
  have hA1 := autocorrelation_one_eq_energy_v26 g
  have hCre := correlation_re_v26 g u
  have hhalf :
      Real.exp (u / 2) * Real.exp (u / 2) = Real.exp u := by
    rw [← Real.exp_add]
    congr 1
    ring
  have hhalfC :
      Complex.exp (u : ℂ) =
        Complex.exp ((u : ℂ) * (1 / 2 : ℂ)) ^ 2 := by
    rw [pow_two, ← Complex.exp_add]
    congr 1
    ring
  have hdenR :
      Real.exp u - (Real.exp u)⁻¹ = 2 * Real.sinh u := by
    rw [Real.sinh_eq, Real.exp_neg]
    ring
  have hdenC :
      ((Real.exp u : ℝ) : ℂ) - (((Real.exp u)⁻¹ : ℝ) : ℂ) =
        ((2 * Real.sinh u : ℝ) : ℂ) := by
    exact_mod_cast hdenR
  have hcomplex :
      (Real.exp u : ℂ) *
        WeilArchimedeanIntegrandV1
          (WeilAutocorrelationV1 g) (Real.exp u) =
        ((archLogKernelV26 g u : ℝ) : ℂ) := by
    unfold WeilArchimedeanIntegrandV1 archLogKernelV26
    rw [hrec, hA1, hdenC]
    simp only [Complex.ofReal_inv, Complex.ofReal_mul, Complex.ofReal_ofNat]
    simp [hxC, Complex.add_conj, hCre, hhalf, div_eq_mul_inv]
    field_simp [hxC, hsinhC]
    rw [hhalfC]
    ring
  have hre := congrArg Complex.re hcomplex
  simpa [Complex.real_smul] using hre

theorem archLogKernel_integrable_v26
    (g : WeilCompactSmoothGV1) :
    IntegrableOn (archLogKernelV26 g) (Ioi (0 : ℝ)) := by
  have harch :
      IntegrableOn
        (WeilArchimedeanIntegrandV1 (WeilAutocorrelationV1 g))
        (Ioi (1 : ℝ)) := by
    exact
      weil_compact_smooth_archimedean_integrable_v1
        (WeilAutocorrelationCompactSmoothV1 g)
  have hcomp :
      IntegrableOn
        (fun u : ℝ =>
          Real.exp u •
            WeilArchimedeanIntegrandV1
              (WeilAutocorrelationV1 g) (Real.exp u))
        (Ioi (0 : ℝ)) := by
    apply (integrableOn_comp_exp_Ioi
      (WeilArchimedeanIntegrandV1 (WeilAutocorrelationV1 g)) 0).2
    simpa using harch
  have hre :
      IntegrableOn
        (fun u : ℝ =>
          (Real.exp u •
            WeilArchimedeanIntegrandV1
              (WeilAutocorrelationV1 g) (Real.exp u)).re)
        (Ioi (0 : ℝ)) :=
    hcomp.re
  refine hre.congr_fun ?_ measurableSet_Ioi
  intro u hu
  exact arch_log_kernel_pointwise_v26 g hu

theorem archimedean_log_coordinate_identity_v26
    (g : WeilCompactSmoothGV1) :
    (WeilArchimedeanIntegralV1 (WeilAutocorrelationV1 g)).re =
      ∫ u : ℝ in Ioi (0 : ℝ), archLogKernelV26 g u := by
  have harch :
      IntegrableOn
        (WeilArchimedeanIntegrandV1 (WeilAutocorrelationV1 g))
        (Ioi (1 : ℝ)) := by
    exact
      weil_compact_smooth_archimedean_integrable_v1
        (WeilAutocorrelationCompactSmoothV1 g)
  have hcomp :
      IntegrableOn
        (fun u : ℝ =>
          Real.exp u •
            WeilArchimedeanIntegrandV1
              (WeilAutocorrelationV1 g) (Real.exp u))
        (Ioi (0 : ℝ)) := by
    apply (integrableOn_comp_exp_Ioi
      (WeilArchimedeanIntegrandV1 (WeilAutocorrelationV1 g)) 0).2
    simpa using harch
  have hsub :=
    integral_comp_exp_Ioi
      (WeilArchimedeanIntegrandV1 (WeilAutocorrelationV1 g)) 0
  have hsub' :
      (∫ x : ℝ in Ioi (1 : ℝ),
        WeilArchimedeanIntegrandV1
          (WeilAutocorrelationV1 g) x) =
      ∫ u : ℝ in Ioi (0 : ℝ),
        Real.exp u •
          WeilArchimedeanIntegrandV1
            (WeilAutocorrelationV1 g) (Real.exp u) := by
    simpa using hsub.symm
  unfold WeilArchimedeanIntegralV1
  rw [hsub']
  rw [← RCLike.re_eq_complex_re]
  rw [← integral_re hcomp]
  apply setIntegral_congr_fun measurableSet_Ioi
  intro u hu
  exact arch_log_kernel_pointwise_v26 g hu

private theorem exp_half_sub_one_bound_v26
    {u : ℝ} (hu : 0 ≤ u) :
    Real.exp (u / 2) - 1 ≤ (u / 2) * Real.exp (u / 2) := by
  have h := Real.add_one_le_exp (-(u / 2))
  have hp : 0 ≤ Real.exp (u / 2) := (Real.exp_pos _).le
  have hm := mul_le_mul_of_nonneg_right h hp
  have hprod :
      Real.exp (-(u / 2)) * Real.exp (u / 2) = 1 := by
    rw [← Real.exp_add]
    have : -(u / 2) + u / 2 = 0 := by ring
    rw [this, Real.exp_zero]
  rw [hprod] at hm
  nlinarith

private theorem small_ratio_bound_v26
    {u : ℝ} (hu : 0 < u) (huw : u ≤ (1 / 32 : ℝ)) :
    (Real.exp (u / 2) - 1) / Real.sinh u ≤
      (1 / 2 : ℝ) * Real.exp (1 / 64) := by
  have hsinh : 0 < Real.sinh u := sinh_pos_of_pos hu
  have husinh : u ≤ Real.sinh u :=
    (Real.self_le_sinh_iff).2 hu.le
  have hexp :
      Real.exp (u / 2) ≤ Real.exp (1 / 64 : ℝ) :=
    Real.exp_le_exp.mpr (by linarith)
  have hsub := exp_half_sub_one_bound_v26 hu.le
  apply (div_le_iff₀ hsinh).2
  calc
    Real.exp (u / 2) - 1
        ≤ (u / 2) * Real.exp (u / 2) := hsub
    _ ≤ (u / 2) * Real.exp (1 / 64 : ℝ) := by
      exact mul_le_mul_of_nonneg_left hexp (by positivity)
    _ = ((1 / 2 : ℝ) * Real.exp (1 / 64 : ℝ)) * u := by ring
    _ ≤ ((1 / 2 : ℝ) * Real.exp (1 / 64 : ℝ)) * Real.sinh u := by
      exact mul_le_mul_of_nonneg_left husinh (by positivity)

private theorem archLogKernel_small_bound_v26
    (g : WeilCompactSmoothGV1) {u : ℝ}
    (hu : 0 < u) (huw : u ≤ (1 / 32 : ℝ)) :
    archLogKernelV26 g u ≤
      energy g.1 * ((1 / 2 : ℝ) * Real.exp (1 / 64 : ℝ)) := by
  have hE : 0 ≤ energy g.1 := energy_nonnegative g.1
  have hC :
      (logCorrelationV25 g u).re ≤ energy g.1 :=
    (Complex.re_le_norm _).trans (norm_logCorrelation_le_energy_v25 g u)
  have hnum :
      Real.exp (u / 2) * (logCorrelationV25 g u).re - energy g.1 ≤
        energy g.1 * (Real.exp (u / 2) - 1) := by
    have hm :=
      mul_le_mul_of_nonneg_left hC (Real.exp_pos (u / 2)).le
    nlinarith
  have hsinh : 0 < Real.sinh u := sinh_pos_of_pos hu
  have hinv : 0 ≤ (Real.sinh u)⁻¹ := inv_nonneg.mpr hsinh.le
  have hdiv := mul_le_mul_of_nonneg_right hnum hinv
  have hratio := small_ratio_bound_v26 hu huw
  calc
    archLogKernelV26 g u
        = (Real.exp (u / 2) * (logCorrelationV25 g u).re -
            energy g.1) * (Real.sinh u)⁻¹ := by
              rw [archLogKernelV26, div_eq_mul_inv]
    _ ≤ (energy g.1 * (Real.exp (u / 2) - 1)) *
          (Real.sinh u)⁻¹ := hdiv
    _ = energy g.1 *
          ((Real.exp (u / 2) - 1) / Real.sinh u) := by
            rw [div_eq_mul_inv]
            ring
    _ ≤ energy g.1 *
          ((1 / 2 : ℝ) * Real.exp (1 / 64 : ℝ)) :=
      mul_le_mul_of_nonneg_left hratio hE

private theorem archLogKernel_tail_eq_v26
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) {u : ℝ}
    (hu : (1 / 32 : ℝ) < u) :
    archLogKernelV26 g u =
      (-energy g.1) * (1 / Real.sinh u) := by
  have hz := logCorrelation_zero_of_width_v25 g a u hw hu
  unfold archLogKernelV26
  rw [hz]
  simp
  ring

theorem actual_archimedean_integral_budget_v26
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) :
    (WeilArchimedeanIntegralV1 (WeilAutocorrelationV1 g)).re ≤
      energy g.1 * (diagonalSmallV21 - diagonalTailV24) := by
  let w : ℝ := 1 / 32
  let K : ℝ := energy g.1 * ((1 / 2 : ℝ) * Real.exp (1 / 64 : ℝ))
  have hw0 : 0 ≤ w := by dsimp [w]; norm_num
  have hphi := archLogKernel_integrable_v26 g
  have hsmallInt :
      IntegrableOn (archLogKernelV26 g) (Ioc 0 w) :=
    hphi.mono_set Ioc_subset_Ioi_self
  have htailInt :
      IntegrableOn (archLogKernelV26 g) (Ioi w) :=
    hphi.mono_set (Ioi_subset_Ioi hw0)
  have hconstInt : IntegrableOn (fun _ : ℝ => K) (Ioc 0 w) :=
    continuous_const.integrableOn_Ioc
  have hsmall :
      (∫ u : ℝ in Ioc 0 w, archLogKernelV26 g u) ≤
        ∫ u : ℝ in Ioc 0 w, K := by
    refine setIntegral_mono_on hsmallInt hconstInt measurableSet_Ioc ?_
    intro u hu
    exact archLogKernel_small_bound_v26 g hu.1 (by simpa [w] using hu.2)
  have hconst :
      (∫ _u : ℝ in Ioc 0 w, K) =
        energy g.1 * diagonalSmallV21 := by
    dsimp [K, w]
    unfold diagonalSmallV21
    simp
    ring
  have htail :
      (∫ u : ℝ in Ioi w, archLogKernelV26 g u) =
        (-energy g.1) * diagonalTailV24 := by
    calc
      (∫ u : ℝ in Ioi w, archLogKernelV26 g u)
          =
        ∫ u : ℝ in Ioi w,
          (-energy g.1) * (1 / Real.sinh u) := by
            apply setIntegral_congr_fun measurableSet_Ioi
            intro u hu
            exact archLogKernel_tail_eq_v26 g a hw (by simpa [w] using hu)
      _ =
        (-energy g.1) *
          ∫ u : ℝ in Ioi w, 1 / Real.sinh u := by
            rw [integral_const_mul]
      _ = (-energy g.1) * diagonalTailV24 := by
            rfl
  have hsplit :
      (∫ u : ℝ in Ioi (0 : ℝ), archLogKernelV26 g u) =
        (∫ u : ℝ in Ioc 0 w, archLogKernelV26 g u) +
          ∫ u : ℝ in Ioi w, archLogKernelV26 g u := by
    rw [← Set.Ioc_union_Ioi_eq_Ioi hw0,
      setIntegral_union Set.Ioc_disjoint_Ioi_same measurableSet_Ioi]
    · exact hsmallInt
    · exact htailInt
  rw [archimedean_log_coordinate_identity_v26 g, hsplit, htail]
  calc
    (∫ u : ℝ in Ioc 0 w, archLogKernelV26 g u) +
          (-energy g.1) * diagonalTailV24
        ≤ energy g.1 * diagonalSmallV21 +
          (-energy g.1) * diagonalTailV24 := by
            have hs := hsmall.trans_eq hconst
            linarith
    _ = energy g.1 * (diagonalSmallV21 - diagonalTailV24) := by
      ring

/-- The formerly conditional V2.4 diagonal estimate is now discharged. -/
theorem width_diagonal_103_over_100_v26
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) :
    (103 / 100 : ℝ) * energy g.1 ≤ -(B g g).re := by
  exact
    width_diagonal_103_over_100_of_arch_budget_v24
      g a hw (actual_archimedean_integral_budget_v26 g a hw)

end AEGIS.WeilWidthArchBudgetV26

#print axioms AEGIS.WeilWidthArchBudgetV26.archLogKernel_integrable_v26
#print axioms AEGIS.WeilWidthArchBudgetV26.archimedean_log_coordinate_identity_v26
#print axioms AEGIS.WeilWidthArchBudgetV26.actual_archimedean_integral_budget_v26
#print axioms AEGIS.WeilWidthArchBudgetV26.width_diagonal_103_over_100_v26
