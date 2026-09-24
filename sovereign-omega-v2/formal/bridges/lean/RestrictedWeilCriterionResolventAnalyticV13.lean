import RestrictedWeilCriterionTopologyV13
import RestrictedWeilCriterionLaplaceV10
import Mathlib.Analysis.Calculus.SmoothSeries
import Mathlib.Tactic

/-!
AEGIS Omega -- local analyticity of the restricted-Weil zero resolvent V13.

For a fixed repository packet g, the V10 Cauchy transform is

  sum_rho a_rho(g) / (w - (1/2-rho)).

The coefficient norms are already summable. At any point of the open
right-half-plane away from the centered Mathlib zeta-zero set, choose a ball
contained in that punctured domain. Every denominator on the half-radius
ball is then uniformly separated from zero, giving summable majorants for
both the terms and their derivatives. Mathlib's smooth-series derivative
theorem yields local holomorphy.

No sign theorem and no RH conclusion is asserted here.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set Complex
open scoped BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RestrictedWeilCriterionResolventAnalyticV13

open AEGIS.RestrictedWeilCriterionTopologyV13
open AEGIS.RestrictedWeilCriterionZeroKernelV10
open AEGIS.RestrictedWeilCriterionLaplaceV10

private theorem centered_nontrivial_zero_mem_all_centered_v13
    (rho : RiemannNontrivialZeroIndexV2) :
    CenteredZeroExponentV10 rho ∈ CenteredRiemannZeroSetV13 := by
  change
    (1 / 2 : ℂ) - CenteredZeroExponentV10 rho ∈ riemannZetaZeros
  have hz : rho.1 ∈ riemannZetaZeros :=
    mem_riemannZetaZeros.mpr rho.2.1
  simpa [CenteredZeroExponentV10] using hz

private theorem centered_nontrivial_zero_not_mem_domain_v13
    (rho : RiemannNontrivialZeroIndexV2) :
    CenteredZeroExponentV10 rho ∉ RightHalfMinusCenteredZerosV13 := by
  intro h
  exact h.2 (centered_nontrivial_zero_mem_all_centered_v13 rho)

private theorem zeroCauchySummand_hasDerivAt_v13
    (g : WeilCompactSmoothGV1)
    (rho : RiemannNontrivialZeroIndexV2)
    {w : ℂ}
    (hw : w ≠ CenteredZeroExponentV10 rho) :
    HasDerivAt
      (fun z : ℂ => ZeroCauchySummandV10 g z rho)
      (-(ZeroCoefficientV10 g rho) /
        (w - CenteredZeroExponentV10 rho) ^ 2)
      w := by
  unfold ZeroCauchySummandV10
  have hnum :
      HasDerivAt
        (fun _ : ℂ => ZeroCoefficientV10 g rho)
        0 w :=
    hasDerivAt_const w _
  have hden :
      HasDerivAt
        (fun z : ℂ => z - CenteredZeroExponentV10 rho)
        1 w := by
    simpa using
      (hasDerivAt_id w).sub
        (hasDerivAt_const w (CenteredZeroExponentV10 rho))
  convert hnum.div hden (sub_ne_zero.mpr hw) using 1 <;> ring

private theorem centered_distance_ge_radius_v13
    {w : ℂ} {r : ℝ}
    (hr : 0 < r)
    (hball :
      Metric.ball w r ⊆ RightHalfMinusCenteredZerosV13)
    (rho : RiemannNontrivialZeroIndexV2) :
    r ≤ dist w (CenteredZeroExponentV10 rho) := by
  have hnot :
      CenteredZeroExponentV10 rho ∉ Metric.ball w r := by
    intro hmem
    exact centered_nontrivial_zero_not_mem_domain_v13 rho
      (hball hmem)
  simpa [Metric.mem_ball, not_lt] using hnot

private theorem centered_distance_ge_half_radius_v13
    {w y : ℂ} {r : ℝ}
    (hr : 0 < r)
    (hball :
      Metric.ball w r ⊆ RightHalfMinusCenteredZerosV13)
    (hy : y ∈ Metric.ball w (r / 2))
    (rho : RiemannNontrivialZeroIndexV2) :
    r / 2 ≤ dist y (CenteredZeroExponentV10 rho) := by
  have hwr :=
    centered_distance_ge_radius_v13 hr hball rho
  have hyw : dist y w < r / 2 := by
    simpa [Metric.mem_ball] using hy
  have htri :
      dist w (CenteredZeroExponentV10 rho) ≤
        dist w y + dist y (CenteredZeroExponentV10 rho) :=
    dist_triangle _ _ _
  have hwy : dist w y = dist y w := dist_comm _ _
  rw [hwy] at htri
  linarith

private theorem zeroCauchySummand_norm_at_center_le_v13
    (g : WeilCompactSmoothGV1)
    {w : ℂ} {r : ℝ}
    (hr : 0 < r)
    (hball :
      Metric.ball w r ⊆ RightHalfMinusCenteredZerosV13)
    (rho : RiemannNontrivialZeroIndexV2) :
    ‖ZeroCauchySummandV10 g w rho‖ ≤
      ‖ZeroCoefficientV10 g rho‖ * (1 / r) := by
  have hd :
      r ≤ ‖w - CenteredZeroExponentV10 rho‖ := by
    simpa [dist_eq_norm] using
      centered_distance_ge_radius_v13 hr hball rho
  unfold ZeroCauchySummandV10
  rw [norm_div]
  calc
    ‖ZeroCoefficientV10 g rho‖ /
        ‖w - CenteredZeroExponentV10 rho‖
      ≤ ‖ZeroCoefficientV10 g rho‖ / r := by
        gcongr
    _ = ‖ZeroCoefficientV10 g rho‖ * (1 / r) := by
        rw [div_eq_mul_inv, one_div]

private theorem zeroCauchySummand_deriv_norm_le_v13
    (g : WeilCompactSmoothGV1)
    {w y : ℂ} {r : ℝ}
    (hr : 0 < r)
    (hball :
      Metric.ball w r ⊆ RightHalfMinusCenteredZerosV13)
    (hy : y ∈ Metric.ball w (r / 2))
    (rho : RiemannNontrivialZeroIndexV2) :
    ‖(-(ZeroCoefficientV10 g rho) /
        (y - CenteredZeroExponentV10 rho) ^ 2)‖ ≤
      ‖ZeroCoefficientV10 g rho‖ * (4 / r ^ 2) := by
  have hd :
      r / 2 ≤ ‖y - CenteredZeroExponentV10 rho‖ := by
    simpa [dist_eq_norm] using
      centered_distance_ge_half_radius_v13 hr hball hy rho
  rw [norm_div, norm_neg, norm_pow]
  calc
    ‖ZeroCoefficientV10 g rho‖ /
        ‖y - CenteredZeroExponentV10 rho‖ ^ 2
      ≤ ‖ZeroCoefficientV10 g rho‖ / (r / 2) ^ 2 := by
        gcongr
    _ = ‖ZeroCoefficientV10 g rho‖ * (4 / r ^ 2) := by
        field_simp
        <;> ring

theorem zero_cauchy_transform_analyticAt_v13
    (g : WeilCompactSmoothGV1)
    {w : ℂ}
    (hw : w ∈ RightHalfMinusCenteredZerosV13) :
    AnalyticAt ℂ (ZeroCauchyTransformV10 g) w := by
  obtain ⟨r, hr, hball⟩ :
      ∃ r : ℝ, 0 < r ∧
        Metric.ball w r ⊆ RightHalfMinusCenteredZerosV13 :=
    Metric.isOpen_iff.mp
      right_half_minus_centered_zeros_open_v13 w hw

  have hcoef :=
    zero_coefficient_norm_summable_v10 g

  have hu :
      Summable
        (fun rho : RiemannNontrivialZeroIndexV2 =>
          ‖ZeroCoefficientV10 g rho‖ * (4 / r ^ 2)) :=
    hcoef.mul_right (4 / r ^ 2)

  have hsum0 :
      Summable
        (fun rho : RiemannNontrivialZeroIndexV2 =>
          ZeroCauchySummandV10 g w rho) := by
    have hmajor :
        Summable
          (fun rho : RiemannNontrivialZeroIndexV2 =>
            ‖ZeroCoefficientV10 g rho‖ * (1 / r)) :=
      hcoef.mul_right (1 / r)
    exact Summable.of_norm_bounded hmajor
      (fun rho =>
        zeroCauchySummand_norm_at_center_le_v13
          g hr hball rho)

  have hsmall : 0 < r / 2 := by positivity
  have hwball : w ∈ Metric.ball w (r / 2) :=
    Metric.mem_ball_self hsmall

  have htermDeriv :
      ∀ rho : RiemannNontrivialZeroIndexV2,
        ∀ y : ℂ, y ∈ Metric.ball w (r / 2) →
          HasDerivAt
            (fun z : ℂ => ZeroCauchySummandV10 g z rho)
            (-(ZeroCoefficientV10 g rho) /
              (y - CenteredZeroExponentV10 rho) ^ 2)
            y := by
    intro rho y hy
    have hd :=
      centered_distance_ge_half_radius_v13
        hr hball hy rho
    have hne :
        y ≠ CenteredZeroExponentV10 rho := by
      intro heq
      subst y
      simp at hd
      linarith
    exact zeroCauchySummand_hasDerivAt_v13 g rho hne

  have htermBound :
      ∀ rho : RiemannNontrivialZeroIndexV2,
        ∀ y : ℂ, y ∈ Metric.ball w (r / 2) →
          ‖(-(ZeroCoefficientV10 g rho) /
              (y - CenteredZeroExponentV10 rho) ^ 2)‖ ≤
            ‖ZeroCoefficientV10 g rho‖ * (4 / r ^ 2) := by
    intro rho y hy
    exact zeroCauchySummand_deriv_norm_le_v13
      g hr hball hy rho

  have hderiv :
      ∀ y : ℂ, y ∈ Metric.ball w (r / 2) →
        DifferentiableAt ℂ (ZeroCauchyTransformV10 g) y := by
    intro y hy
    have hd :=
      hasDerivAt_tsum_of_isPreconnected
        hu isOpen_ball (convex_ball w (r / 2)).isPreconnected
        htermDeriv htermBound hwball hsum0 hy
    simpa [ZeroCauchyTransformV10] using hd.differentiableAt

  have hdiff :
      DifferentiableOn ℂ
        (ZeroCauchyTransformV10 g)
        (Metric.ball w (r / 2)) := by
    intro y hy
    exact (hderiv y hy).differentiableWithinAt

  have hana :
      AnalyticOnNhd ℂ
        (ZeroCauchyTransformV10 g)
        (Metric.ball w (r / 2)) :=
    hdiff.analyticOnNhd isOpen_ball

  exact hana w hwball

theorem zero_cauchy_transform_analyticOnNhd_v13
    (g : WeilCompactSmoothGV1) :
    AnalyticOnNhd ℂ
      (ZeroCauchyTransformV10 g)
      RightHalfMinusCenteredZerosV13 :=
  fun w hw => zero_cauchy_transform_analyticAt_v13 g hw

end AEGIS.RestrictedWeilCriterionResolventAnalyticV13

#print axioms AEGIS.RestrictedWeilCriterionResolventAnalyticV13.zero_cauchy_transform_analyticAt_v13
#print axioms AEGIS.RestrictedWeilCriterionResolventAnalyticV13.zero_cauchy_transform_analyticOnNhd_v13
