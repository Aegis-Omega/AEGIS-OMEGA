import RestrictedWeilCriterionLaplaceV10
import RestrictedWeilCriterionPoleIsolationV10
import Mathlib.Analysis.Normed.Group.FunctionSeries
import Mathlib.Tactic

/-!
AEGIS Omega -- local centered-Cauchy remainder at an isolated zeta zero V13.

This module proves only the local analytic prerequisite needed by the
restricted-Weil pole contradiction.  It does not assert the universal final
sign and does not assert the Riemann hypothesis.

For a fixed nontrivial zero rho, remove rho's simple Cauchy summand from the
centered zero transform.  The existing discrete-zero isolation radius and
absolute summability of the zero coefficients give a uniform majorant on a
half-radius ball, hence continuity of the remainder at the pole.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set Filter Complex
open scoped BigOperators Topology

set_option autoImplicit false
noncomputable section

namespace AEGIS.RestrictedWeilCriterionMeromorphicV13

open AEGIS.RestrictedWeilCriterionLaplaceV10
open AEGIS.RestrictedWeilCriterionPoleIsolationV10

def ZeroCauchyRemainderV13
    (g : WeilCompactSmoothGV1)
    (rho : RiemannNontrivialZeroIndexV2)
    (w : ℂ) : ℂ :=
  ∑' sigma : RiemannNontrivialZeroIndexV2,
    if sigma = rho then 0 else ZeroCauchySummandV10 g w sigma

theorem zero_cauchy_remainder_continuousOn_ball_v13
    (g : WeilCompactSmoothGV1)
    (rho : RiemannNontrivialZeroIndexV2)
    {eps : ℝ}
    (heps : 0 < eps)
    (hsep : ∀ sigma : RiemannNontrivialZeroIndexV2,
      sigma ≠ rho →
      eps ≤ dist (CenteredZeroExponentV10 sigma)
        (CenteredZeroExponentV10 rho)) :
    ContinuousOn
      (ZeroCauchyRemainderV13 g rho)
      (Metric.ball (CenteredZeroExponentV10 rho) (eps / 2)) := by
  let F : RiemannNontrivialZeroIndexV2 → ℂ → ℂ := fun sigma w =>
    if sigma = rho then 0 else ZeroCauchySummandV10 g w sigma
  let u : RiemannNontrivialZeroIndexV2 → ℝ := fun sigma =>
    (2 / eps) * ‖ZeroCoefficientV10 g sigma‖
  have hu : Summable u := by
    dsimp [u]
    exact (zero_coefficient_norm_summable_v10 g).mul_left (2 / eps)
  have hFcont :
      ∀ sigma : RiemannNontrivialZeroIndexV2,
        ContinuousOn (F sigma)
          (Metric.ball (CenteredZeroExponentV10 rho) (eps / 2)) := by
    intro sigma
    by_cases hsr : sigma = rho
    · subst sigma
      simp [F]
    · simp only [F, hsr, if_false]
      unfold ZeroCauchySummandV10
      apply ContinuousOn.div (by fun_prop) (by fun_prop)
      intro w hw
      apply sub_ne_zero.mpr
      intro hEq
      have hwEq : w = CenteredZeroExponentV10 sigma := hEq
      have hball :
          dist (CenteredZeroExponentV10 sigma)
              (CenteredZeroExponentV10 rho) < eps / 2 := by
        simpa [hwEq] using (Metric.mem_ball.mp hw)
      have hs := hsep sigma hsr
      linarith
  have hFbound :
      ∀ sigma : RiemannNontrivialZeroIndexV2,
      ∀ w : ℂ,
        w ∈ Metric.ball (CenteredZeroExponentV10 rho) (eps / 2) →
        ‖F sigma w‖ ≤ u sigma := by
    intro sigma w hw
    by_cases hsr : sigma = rho
    · subst sigma
      simp [F, u, le_of_lt heps]
    · simp only [F, hsr, if_false]
      unfold ZeroCauchySummandV10
      have hs := hsep sigma hsr
      have hw' :
          dist w (CenteredZeroExponentV10 rho) < eps / 2 :=
        Metric.mem_ball.mp hw
      have htri :
          dist (CenteredZeroExponentV10 sigma)
              (CenteredZeroExponentV10 rho) ≤
            dist (CenteredZeroExponentV10 sigma) w +
              dist w (CenteredZeroExponentV10 rho) :=
        dist_triangle _ _ _
      have hden :
          eps / 2 < dist w (CenteredZeroExponentV10 sigma) := by
        rw [dist_comm]
        linarith
      have heps2 : 0 < eps / 2 := by linarith
      have hnormden :
          eps / 2 < ‖w - CenteredZeroExponentV10 sigma‖ := by
        simpa [dist_eq] using hden
      have hrecip :
          1 / ‖w - CenteredZeroExponentV10 sigma‖ ≤ 2 / eps := by
        calc
          1 / ‖w - CenteredZeroExponentV10 sigma‖
              ≤ 1 / (eps / 2) :=
            one_div_le_one_div_of_le heps2 hnormden.le
          _ = 2 / eps := by
            field_simp [ne_of_gt heps]
      rw [norm_div, div_eq_mul_one_div]
      exact mul_le_mul_of_nonneg_left hrecip (norm_nonneg _)
  have hcont :
      ContinuousOn (fun w : ℂ => ∑' sigma, F sigma w)
        (Metric.ball (CenteredZeroExponentV10 rho) (eps / 2)) :=
    continuousOn_tsum hFcont hu hFbound
  simpa [ZeroCauchyRemainderV13, F] using hcont

theorem zero_cauchy_remainder_continuousAt_pole_v13
    (g : WeilCompactSmoothGV1)
    (rho : RiemannNontrivialZeroIndexV2) :
    ContinuousAt
      (ZeroCauchyRemainderV13 g rho)
      (CenteredZeroExponentV10 rho) := by
  obtain ⟨eps, heps, hsep⟩ :=
    centered_zero_dist_ge_isolation_v10 rho
  have hcont :=
    zero_cauchy_remainder_continuousOn_ball_v13
      g rho heps hsep
  exact hcont.continuousAt
    (Metric.ball_mem_nhds _ (by linarith : 0 < eps / 2))

end AEGIS.RestrictedWeilCriterionMeromorphicV13

#print axioms AEGIS.RestrictedWeilCriterionMeromorphicV13.zero_cauchy_remainder_continuousOn_ball_v13
#print axioms AEGIS.RestrictedWeilCriterionMeromorphicV13.zero_cauchy_remainder_continuousAt_pole_v13
