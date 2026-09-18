import WeilWidthArchBudgetV26
import Mathlib.Tactic

/-!
AEGIS Ω — mixed logarithmic Weil kernel core V2.7.

This module kernelizes the common analytic carrier underlying the off-diagonal
bounds from WEIL_CROSS_TERM_KERNEL_V1.

For compact-smooth packets a,b define
  R_ab(u) = ∫ h_a(v+u) conj(h_b(v)) dv,
where h_g(t) = exp(t/2) g(exp t).

It proves:
1. exact normalization
     R_ab(u) = exp(u/2) * mixed(a,b)(exp u);
2. absolute integrability of the mixed logarithmic correlation integrand;
3. the elementary energy bound
     ||R_ab(u)|| <= (energy(a)+energy(b))/2;
4. support-difference vanishing:
     supp(R_ab) ⊆ [alo-bhi, ahi-blo]
   whenever the two log supports lie in [alo,ahi] and [blo,bhi].

No prime-sample enumeration, separated Archimedean moment cancellation,
off-diagonal numerical bound, global Weil sign, or RH conclusion is asserted.
-/

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false

noncomputable section

namespace AEGIS.WeilMixedLogKernelV27

open AEGIS.WeilMixedClosureV2
open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilLogCoordinateIsometryV21
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilWidthArchCorrelationV25

def mixedLogCorrelationV27
    (a b : WeilCompactSmoothGV1) (u : ℝ) : ℂ :=
  ∫ v : ℝ, logLift a.1 (v + u) * conj (logLift b.1 v)

private theorem logLift_continuous_v27
    (g : WeilCompactSmoothGV1) :
    Continuous (logLift g.1) := by
  unfold logLift
  have hscalar : Continuous (fun t : ℝ =>
      (Real.exp (t / 2) : ℂ)) := by
    fun_prop
  have hpacket : Continuous (fun t : ℝ =>
      g.1 (Real.exp t)) :=
    g.2.1.continuous.comp Real.continuous_exp
  exact hscalar.mul hpacket

theorem mixedLogCorrelation_integrable_v27
    (a b : WeilCompactSmoothGV1) (u : ℝ) :
    Integrable
      (fun v : ℝ =>
        logLift a.1 (v + u) * conj (logLift b.1 v)) := by
  let M : ℝ → ℝ := fun v =>
    (1 / 2 : ℝ) *
      (‖logLift a.1 (v + u)‖ ^ 2 + ‖logLift b.1 v‖ ^ 2)
  have hM : Integrable M := by
    unfold M
    exact
      ((shifted_logLift_sq_integrable_v25 a u).add
        (logLift_sq_integrable_v25 b)).const_mul (1 / 2 : ℝ)
  have hmeas :
      AEStronglyMeasurable
        (fun v : ℝ =>
          logLift a.1 (v + u) * conj (logLift b.1 v)) := by
    exact
      ((logLift_continuous_v27 a).comp (by fun_prop)).aestronglyMeasurable.mul
        (continuous_conj.comp (logLift_continuous_v27 b)).aestronglyMeasurable
  refine hM.mono' hmeas (Filter.Eventually.of_forall fun v => ?_)
  have hab :
      ‖logLift a.1 (v + u)‖ * ‖logLift b.1 v‖ ≤
        (1 / 2 : ℝ) *
          (‖logLift a.1 (v + u)‖ ^ 2 +
            ‖logLift b.1 v‖ ^ 2) := by
    nlinarith [sq_nonneg
      (‖logLift a.1 (v + u)‖ - ‖logLift b.1 v‖)]
  simpa [M, norm_mul, norm_conj] using hab

/-- Exact multiplicative-to-additive normalization for the mixed repository
correlation with its dy measure. -/
theorem mixedLogCorrelation_eq_mixed_v27
    (a b : WeilCompactSmoothGV1) (u : ℝ) :
    mixedLogCorrelationV27 a b u =
      (Real.exp (u / 2) : ℂ) *
        mixed a b (Real.exp u) := by
  unfold mixedLogCorrelationV27 mixed
  rw [AEGIS.WeilThreeBlockTranslatedPacketsV22.integral_exp_substitution_complex]
  rw [← integral_const_mul]
  apply integral_congr_ae
  filter_upwards [] with v
  unfold logLift
  rw [Complex.star_def, map_mul]
  simp only [Complex.conj_ofReal, Complex.real_smul]
  have harg :
      Real.exp u * Real.exp v = Real.exp (v + u) := by
    rw [← Real.exp_add]
    congr 1
    ring
  rw [harg]
  have hscalar :
      (Real.exp (u / 2) : ℂ) * (Real.exp v : ℂ) =
        (Real.exp ((v + u) / 2) : ℂ) *
          (Real.exp (v / 2) : ℂ) := by
    norm_cast
    rw [← Real.exp_add, ← Real.exp_add]
    congr 1
    ring
  calc
    (Real.exp ((v + u) / 2) : ℂ) * a.1 (Real.exp (v + u)) *
        ((Real.exp (v / 2) : ℂ) * conj (b.1 (Real.exp v)))
        =
      ((Real.exp ((v + u) / 2) : ℂ) *
          (Real.exp (v / 2) : ℂ)) *
        (a.1 (Real.exp (v + u)) * conj (b.1 (Real.exp v))) := by
          ring
    _ =
      ((Real.exp (u / 2) : ℂ) * (Real.exp v : ℂ)) *
        (a.1 (Real.exp (v + u)) * conj (b.1 (Real.exp v))) := by
          rw [← hscalar]
    _ =
      (Real.exp (u / 2) : ℂ) *
        ((Real.exp v : ℂ) *
          (a.1 (Real.exp (v + u)) * conj (b.1 (Real.exp v)))) := by
            ring

/-- The mixed logarithmic correlation obeys the arithmetic-mean L2 bound.
For equal-energy translated packets this is exactly one packet energy. -/
theorem norm_mixedLogCorrelation_le_mean_energy_v27
    (a b : WeilCompactSmoothGV1) (u : ℝ) :
    ‖mixedLogCorrelationV27 a b u‖ ≤
      (1 / 2 : ℝ) * (energy a.1 + energy b.1) := by
  let q : ℝ → ℂ := fun v =>
    logLift a.1 (v + u) * conj (logLift b.1 v)
  let M : ℝ → ℝ := fun v =>
    (1 / 2 : ℝ) *
      (‖logLift a.1 (v + u)‖ ^ 2 + ‖logLift b.1 v‖ ^ 2)
  have hq : Integrable q := by
    simpa [q] using mixedLogCorrelation_integrable_v27 a b u
  have hM : Integrable M := by
    unfold M
    exact
      ((shifted_logLift_sq_integrable_v25 a u).add
        (logLift_sq_integrable_v25 b)).const_mul (1 / 2 : ℝ)
  have hpoint : ∀ v : ℝ, ‖q v‖ ≤ M v := by
    intro v
    have hab :
        ‖logLift a.1 (v + u)‖ * ‖logLift b.1 v‖ ≤
          (1 / 2 : ℝ) *
            (‖logLift a.1 (v + u)‖ ^ 2 +
              ‖logLift b.1 v‖ ^ 2) := by
      nlinarith [sq_nonneg
        (‖logLift a.1 (v + u)‖ - ‖logLift b.1 v‖)]
    simpa [q, M, norm_mul, norm_conj] using hab
  calc
    ‖mixedLogCorrelationV27 a b u‖
        = ‖∫ v : ℝ, q v‖ := by rfl
    _ ≤ ∫ v : ℝ, ‖q v‖ := norm_integral_le_integral_norm _
    _ ≤ ∫ v : ℝ, M v := integral_mono hq.norm hM hpoint
    _ = (1 / 2 : ℝ) *
        ((∫ v : ℝ, ‖logLift a.1 (v + u)‖ ^ 2) +
          ∫ v : ℝ, ‖logLift b.1 v‖ ^ 2) := by
      unfold M
      rw [integral_const_mul, integral_add
        (shifted_logLift_sq_integrable_v25 a u)
        (logLift_sq_integrable_v25 b)]
    _ = (1 / 2 : ℝ) * (energy a.1 + energy b.1) := by
      rw [shifted_logLift_sq_integral_v25,
        logLift_energy_eq_packet_energy]

/-- If log supports lie in finite intervals, the mixed logarithmic
correlation vanishes outside their difference interval. -/
theorem mixedLogCorrelation_zero_outside_v27
    (a b : WeilCompactSmoothGV1)
    {alo ahi blo bhi u : ℝ}
    (ha : LogSupportIn a alo ahi)
    (hb : LogSupportIn b blo bhi)
    (hu : u < alo - bhi ∨ ahi - blo < u) :
    mixedLogCorrelationV27 a b u = 0 := by
  unfold mixedLogCorrelationV27
  apply integral_eq_zero_of_ae
  filter_upwards [] with v
  by_cases hb0 : logLift b.1 v = 0
  · simp [hb0]
  · by_cases ha0 : logLift a.1 (v + u) = 0
    · simp [ha0]
    · have hbm : v ∈ tsupport (logLift b.1) :=
        subset_tsupport _ hb0
      have ham : v + u ∈ tsupport (logLift a.1) :=
        subset_tsupport _ ha0
      have hbI := hb hbm
      have haI := ha ham
      exfalso
      rcases hu with hlow | hhigh
      · linarith [haI.1, hbI.2]
      · linarith [haI.2, hbI.1]

end AEGIS.WeilMixedLogKernelV27

#print axioms AEGIS.WeilMixedLogKernelV27.mixedLogCorrelation_integrable_v27
#print axioms AEGIS.WeilMixedLogKernelV27.mixedLogCorrelation_eq_mixed_v27
#print axioms AEGIS.WeilMixedLogKernelV27.norm_mixedLogCorrelation_le_mean_energy_v27
#print axioms AEGIS.WeilMixedLogKernelV27.mixedLogCorrelation_zero_outside_v27
