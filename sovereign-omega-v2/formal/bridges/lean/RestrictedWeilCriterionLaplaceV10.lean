import RestrictedWeilCriterionZeroKernelV10
import WeilAutocorrelationMellinV11
import WeilAutocorrelationClosureV1
import Mathlib.Analysis.SpecialFunctions.ImproperIntegrals
import Mathlib.MeasureTheory.Integral.DominatedConvergence
import Mathlib.Tactic

/-!
AEGIS Ω — restricted Weil criterion Laplace/Cauchy bridge V10.

Let
  z_rho = 1/2 - rho
and
  a_rho(g) = m_rho * M(Autocorrelation g)(rho).

The translated zero kernel already proved in
`RestrictedWeilCriterionZeroKernelV10` is

  K_g(d) = sum_rho a_rho(g) exp(z_rho d).

This module takes its one-sided Laplace transform.  On Re(w)>1/2 every
individual term is absolutely integrable because all nontrivial zeros lie in
0<Re(rho)<1, hence Re(z_rho)<1/2.  Existing absolute zero-summability gives the
sum/integral exchange and therefore

  Laplace(K_g)(w)
    = sum_rho a_rho(g) / (w - z_rho).

This is the right-half-plane seed identity for the meromorphic continuation
and residue contradiction.  No RH conclusion is asserted here.

AUTHORITY_EFFECT = NONE.
-/

open Set Filter Complex MeasureTheory
open scoped BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RestrictedWeilCriterionLaplaceV10

open AEGIS.RestrictedWeilCriterionZeroKernelV10
open AEGIS.RestrictedWeilCriterionKernelBridgeV10
open AEGIS.WeilAutocorrelationMellinV11

/-- Multiplicity-weighted autocorrelation coefficient attached to a zero. -/
def ZeroCoefficientV10
    (g : WeilCompactSmoothGV1)
    (rho : RiemannNontrivialZeroIndexV2) : ℂ :=
  (analyticOrderNatAt riemannZeta rho.1 : ℂ) *
    mellin (WeilAutocorrelationV1 g) rho.1

/-- Centered Cauchy summand. -/
def ZeroCauchySummandV10
    (g : WeilCompactSmoothGV1) (w : ℂ)
    (rho : RiemannNontrivialZeroIndexV2) : ℂ :=
  ZeroCoefficientV10 g rho /
    (w - CenteredZeroExponentV10 rho)

/-- Canonical centered Cauchy transform. -/
def ZeroCauchyTransformV10
    (g : WeilCompactSmoothGV1) (w : ℂ) : ℂ :=
  ∑' rho : RiemannNontrivialZeroIndexV2,
    ZeroCauchySummandV10 g w rho

/-- One Laplace-transformed zero-kernel term before integration. -/
def LaplaceZeroTermV10
    (g : WeilCompactSmoothGV1) (w : ℂ)
    (rho : RiemannNontrivialZeroIndexV2) (d : ℝ) : ℂ :=
  Complex.exp (-(w * (d : ℂ))) *
    TranslatedZeroSummandV10 g d rho

/-- One-sided Laplace transform of the actual translated zero kernel. -/
def ZeroKernelLaplaceV10
    (g : WeilCompactSmoothGV1) (w : ℂ) : ℂ :=
  ∫ d : ℝ in Ioi (0 : ℝ),
    Complex.exp (-(w * (d : ℂ))) *
      TranslatedZeroKernelV10 g d

theorem centered_zero_re_lt_half_v10
    (rho : RiemannNontrivialZeroIndexV2) :
    (CenteredZeroExponentV10 rho).re < 1 / 2 := by
  have hstrip :=
    riemann_zeta_nontrivial_zero_critical_strip_v1
      rho.2.1 rho.2.2
  unfold CenteredZeroExponentV10
  simp
  linarith [hstrip.1]

theorem centered_zero_re_gt_neg_half_v10
    (rho : RiemannNontrivialZeroIndexV2) :
    -(1 / 2 : ℝ) < (CenteredZeroExponentV10 rho).re := by
  have hstrip :=
    riemann_zeta_nontrivial_zero_critical_strip_v1
      rho.2.1 rho.2.2
  unfold CenteredZeroExponentV10
  simp
  linarith [hstrip.2]

/-- The Laplace integrand of one zero is exactly one exponential with exponent
z_rho-w. -/
theorem laplace_zero_term_eq_v10
    (g : WeilCompactSmoothGV1) (w : ℂ)
    (rho : RiemannNontrivialZeroIndexV2) (d : ℝ) :
    LaplaceZeroTermV10 g w rho d =
      ZeroCoefficientV10 g rho *
        Complex.exp
          ((CenteredZeroExponentV10 rho - w) * (d : ℂ)) := by
  unfold LaplaceZeroTermV10 ZeroCoefficientV10
  rw [translated_zero_summand_eq_centered_exp_v10]
  rw [← Complex.exp_add]
  congr 1
  ring

/-- Individual Laplace terms are integrable on Re(w)>1/2. -/
theorem laplace_zero_term_integrable_v10
    (g : WeilCompactSmoothGV1) {w : ℂ}
    (hw : 1 / 2 < w.re)
    (rho : RiemannNontrivialZeroIndexV2) :
    IntegrableOn
      (LaplaceZeroTermV10 g w rho)
      (Ioi (0 : ℝ)) := by
  have hrate :
      (CenteredZeroExponentV10 rho - w).re < 0 := by
    have hz := centered_zero_re_lt_half_v10 rho
    simp
    linarith
  have hexp :=
    integrableOn_exp_mul_complex_Ioi
      (a := CenteredZeroExponentV10 rho - w)
      hrate 0
  refine
    (hexp.const_mul (ZeroCoefficientV10 g rho)).congr_fun
      (fun d hd => ?_) measurableSet_Ioi
  rw [laplace_zero_term_eq_v10]
  ring

/-- Exact integral of one Laplace zero term. -/
theorem integral_laplace_zero_term_v10
    (g : WeilCompactSmoothGV1) {w : ℂ}
    (hw : 1 / 2 < w.re)
    (rho : RiemannNontrivialZeroIndexV2) :
    (∫ d : ℝ in Ioi (0 : ℝ),
      LaplaceZeroTermV10 g w rho d) =
      ZeroCauchySummandV10 g w rho := by
  have hrate :
      (CenteredZeroExponentV10 rho - w).re < 0 := by
    have hz := centered_zero_re_lt_half_v10 rho
    simp
    linarith
  have hneq :
      w - CenteredZeroExponentV10 rho ≠ 0 := by
    intro h
    have hre := congrArg Complex.re h
    simp at hre
    have hz := centered_zero_re_lt_half_v10 rho
    linarith
  rw [show
    (fun d : ℝ => LaplaceZeroTermV10 g w rho d) =
      (fun d : ℝ =>
        ZeroCoefficientV10 g rho *
          Complex.exp
            ((CenteredZeroExponentV10 rho - w) * (d : ℂ))) by
              funext d
              exact laplace_zero_term_eq_v10 g w rho d,
    integral_const_mul,
    integral_exp_mul_complex_Ioi hrate 0]
  unfold ZeroCauchySummandV10
  simp
  field_simp [hneq]
  ring

/-- Existing compact-smooth zero summability gives summability of the
coefficient norms used in the Cauchy transform. -/
theorem zero_coefficient_norm_summable_v10
    (g : WeilCompactSmoothGV1) :
    Summable (fun rho : RiemannNontrivialZeroIndexV2 =>
      ‖ZeroCoefficientV10 g rho‖) := by
  have h :=
    weil_compact_smooth_zero_norm_summable_v1
      (WeilAutocorrelationCompactSmoothV1 g)
  simpa [ZeroCoefficientV10, WeilZeroIndexSummandV1] using h

/-- Exact norm integral for one term. -/
theorem integral_norm_laplace_zero_term_v10
    (g : WeilCompactSmoothGV1) {w : ℂ}
    (hw : 1 / 2 < w.re)
    (rho : RiemannNontrivialZeroIndexV2) :
    (∫ d : ℝ in Ioi (0 : ℝ),
      ‖LaplaceZeroTermV10 g w rho d‖) =
      ‖ZeroCoefficientV10 g rho‖ /
        (w.re - (CenteredZeroExponentV10 rho).re) := by
  have hrate :
      (CenteredZeroExponentV10 rho).re - w.re < 0 := by
    have hz := centered_zero_re_lt_half_v10 rho
    linarith
  have hden :
      0 < w.re - (CenteredZeroExponentV10 rho).re := by
    linarith
  have hfun :
      (fun d : ℝ =>
        ‖LaplaceZeroTermV10 g w rho d‖) =
      (fun d : ℝ =>
        ‖ZeroCoefficientV10 g rho‖ *
          Real.exp
            (((CenteredZeroExponentV10 rho).re - w.re) * d)) := by
    funext d
    rw [laplace_zero_term_eq_v10]
    rw [norm_mul, Complex.norm_exp]
    congr 1
    simp
    ring
  rw [hfun, integral_const_mul,
    integral_exp_mul_Ioi hrate 0]
  simp
  field_simp [hden.ne']
  ring

/-- The integrals of term norms are summable uniformly on each fixed
right-half-plane point Re(w)>1/2. -/
theorem laplace_zero_term_integral_norm_summable_v10
    (g : WeilCompactSmoothGV1) {w : ℂ}
    (hw : 1 / 2 < w.re) :
    Summable (fun rho : RiemannNontrivialZeroIndexV2 =>
      ∫ d : ℝ in Ioi (0 : ℝ),
        ‖LaplaceZeroTermV10 g w rho d‖) := by
  let delta : ℝ := w.re - 1 / 2
  have hdelta : 0 < delta := by
    dsimp [delta]
    linarith
  have hcoef := zero_coefficient_norm_summable_v10 g
  have hmajor :
      Summable (fun rho : RiemannNontrivialZeroIndexV2 =>
        ‖ZeroCoefficientV10 g rho‖ * (1 / delta)) :=
    hcoef.mul_right (1 / delta)
  refine Summable.of_nonneg_of_le
    (fun rho => integral_nonneg (fun _ => norm_nonneg _))
    (fun rho => ?_) hmajor
  rw [integral_norm_laplace_zero_term_v10 g hw rho]
  have hz := centered_zero_re_lt_half_v10 rho
  have hden :
      delta ≤ w.re - (CenteredZeroExponentV10 rho).re := by
    dsimp [delta]
    linarith
  have hrecip :
      1 / (w.re - (CenteredZeroExponentV10 rho).re) ≤
        1 / delta :=
    one_div_le_one_div_of_le hdelta hden
  exact mul_le_mul_of_nonneg_left hrecip (norm_nonneg _)

/-- On Re(w)>1/2, sum/integral exchange is justified by absolute
integrability. -/
theorem laplace_zero_terms_hasSum_integral_v10
    (g : WeilCompactSmoothGV1) {w : ℂ}
    (hw : 1 / 2 < w.re) :
    HasSum
      (fun rho : RiemannNontrivialZeroIndexV2 =>
        ∫ d : ℝ in Ioi (0 : ℝ),
          LaplaceZeroTermV10 g w rho d)
      (∫ d : ℝ in Ioi (0 : ℝ),
        ∑' rho : RiemannNontrivialZeroIndexV2,
          LaplaceZeroTermV10 g w rho d) := by
  exact hasSum_integral_of_summable_integral_norm
    (fun rho => laplace_zero_term_integrable_v10 g hw rho)
    (laplace_zero_term_integral_norm_summable_v10 g hw)

/-- Pointwise, multiplying the translated kernel by the Laplace exponential
is the tsum of the individual Laplace terms. -/
theorem laplace_kernel_eq_tsum_terms_v10
    (g : WeilCompactSmoothGV1) (w : ℂ) (d : ℝ) :
    Complex.exp (-(w * (d : ℂ))) *
        TranslatedZeroKernelV10 g d =
      ∑' rho : RiemannNontrivialZeroIndexV2,
        LaplaceZeroTermV10 g w rho d := by
  unfold TranslatedZeroKernelV10 LaplaceZeroTermV10
  rw [tsum_mul_left]
  rfl

/-- Seed Cauchy identity: the Laplace transform of the translated zero kernel
equals its centered Cauchy transform on Re(w)>1/2. -/
theorem zero_kernel_laplace_eq_cauchy_v10
    (g : WeilCompactSmoothGV1) {w : ℂ}
    (hw : 1 / 2 < w.re) :
    ZeroKernelLaplaceV10 g w =
      ZeroCauchyTransformV10 g w := by
  have hsum :=
    laplace_zero_terms_hasSum_integral_v10 g hw
  unfold ZeroKernelLaplaceV10 ZeroCauchyTransformV10
  calc
    (∫ d : ℝ in Ioi (0 : ℝ),
      Complex.exp (-(w * (d : ℂ))) *
        TranslatedZeroKernelV10 g d)
      =
    ∫ d : ℝ in Ioi (0 : ℝ),
      ∑' rho : RiemannNontrivialZeroIndexV2,
        LaplaceZeroTermV10 g w rho d := by
          apply setIntegral_congr_fun measurableSet_Ioi
          intro d hd
          exact laplace_kernel_eq_tsum_terms_v10 g w d
    _ =
      ∑' rho : RiemannNontrivialZeroIndexV2,
        ∫ d : ℝ in Ioi (0 : ℝ),
          LaplaceZeroTermV10 g w rho d :=
      hsum.tsum_eq.symm
    _ =
      ∑' rho : RiemannNontrivialZeroIndexV2,
        ZeroCauchySummandV10 g w rho := by
          apply tsum_congr
          intro rho
          exact integral_laplace_zero_term_v10 g hw rho

end AEGIS.RestrictedWeilCriterionLaplaceV10

#print axioms AEGIS.RestrictedWeilCriterionLaplaceV10.integral_laplace_zero_term_v10
#print axioms AEGIS.RestrictedWeilCriterionLaplaceV10.laplace_zero_term_integral_norm_summable_v10
#print axioms AEGIS.RestrictedWeilCriterionLaplaceV10.zero_kernel_laplace_eq_cauchy_v10
