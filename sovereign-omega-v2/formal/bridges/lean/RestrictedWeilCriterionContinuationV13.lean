import RestrictedWeilCriterionResolventAnalyticV13
import Mathlib.Analysis.Analytic.Uniqueness
import Mathlib.Tactic

/-!
AEGIS Omega -- analytic continuation bridge for the restricted Weil criterion V13.

Under universal zero-quadratic nonnegativity, the V10 zero-kernel Laplace
transform is analytic on the full open right half-plane.  The V13 Cauchy
transform is analytic on the same half-plane with the centered zeta-zero set
removed.  They agree on the nonempty open sub-half-plane Re(w)>1/2, so the
identity theorem extends the equality over the entire punctured right
half-plane.

This is the analytic-continuation step only.  The pole contradiction and the
final RiemannHypothesis theorem are not asserted here.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set Filter Complex
open scoped BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RestrictedWeilCriterionContinuationV13

open AEGIS.RHMillenniumGateV10
open AEGIS.RestrictedWeilCriterionZeroKernelV10
open AEGIS.RestrictedWeilCriterionLaplaceV10
open AEGIS.RestrictedWeilCriterionTopologyV13
open AEGIS.RestrictedWeilCriterionResolventAnalyticV13

private def continuationBaseV13 : ℂ :=
  (1 : ℂ) + I

private theorem continuationBase_re_v13 :
    (continuationBaseV13).re = 1 := by
  simp [continuationBaseV13]

private theorem continuationBase_not_centered_zero_v13 :
    continuationBaseV13 ∉ CenteredRiemannZeroSetV13 := by
  intro hz
  have hzeta :
      riemannZeta ((1 / 2 : ℂ) - continuationBaseV13) = 0 :=
    mem_riemannZetaZeros.mp hz
  have hnontriv :
      ¬ ∃ n : ℕ,
        (1 / 2 : ℂ) - continuationBaseV13 =
          -(2 : ℂ) * (n + 1) := by
    rintro ⟨n, hn⟩
    have him := congrArg Complex.im hn
    simp [continuationBaseV13] at him
  have hstrip :=
    riemann_zeta_nontrivial_zero_critical_strip_v1 hzeta hnontriv
  have hre :
      (((1 / 2 : ℂ) - continuationBaseV13).re : ℝ) = -(1 / 2 : ℝ) := by
    simp [continuationBaseV13]
  rw [hre] at hstrip
  linarith

private theorem continuationBase_mem_domain_v13 :
    continuationBaseV13 ∈ RightHalfMinusCenteredZerosV13 := by
  constructor
  · rw [continuationBase_re_v13]
    norm_num
  · exact continuationBase_not_centered_zero_v13

private theorem eventually_laplace_eq_cauchy_at_base_v13
    (g : WeilCompactSmoothGV1) :
    ZeroKernelLaplaceV10 g =ᶠ[𝓝 continuationBaseV13]
      ZeroCauchyTransformV10 g := by
  have hopen : IsOpen {w : ℂ | (1 / 2 : ℝ) < w.re} :=
    Complex.continuous_re.isOpen_preimage (Ioi (1 / 2 : ℝ)) isOpen_Ioi
  have hmem : continuationBaseV13 ∈ {w : ℂ | (1 / 2 : ℝ) < w.re} := by
    change (1 / 2 : ℝ) < continuationBaseV13.re
    rw [continuationBase_re_v13]
    norm_num
  filter_upwards [hopen.mem_nhds hmem] with w hw
  exact zero_kernel_laplace_eq_cauchy_v10 g hw

theorem zero_kernel_laplace_eq_cauchy_on_punctured_right_half_v13
    (hU : UniversalZeroQuadraticNonnegativeV10)
    (g : WeilCompactSmoothGV1)
    (hm : WeilMomentConditionsV1 g) :
    Set.EqOn
      (ZeroKernelLaplaceV10 g)
      (ZeroCauchyTransformV10 g)
      RightHalfMinusCenteredZerosV13 := by
  have hLap0 :=
    zero_kernel_laplace_analyticOnNhd_v10 hU g hm
  have hLap :
      AnalyticOnNhd ℂ
        (ZeroKernelLaplaceV10 g)
        RightHalfMinusCenteredZerosV13 :=
    hLap0.mono (by
      intro w hw
      exact hw.1)
  have hCauchy :
      AnalyticOnNhd ℂ
        (ZeroCauchyTransformV10 g)
        RightHalfMinusCenteredZerosV13 :=
    zero_cauchy_transform_analyticOnNhd_v13 g
  exact
    hLap.eqOn_of_preconnected_of_eventuallyEq
      hCauchy
      right_half_minus_centered_zeros_preconnected_v13
      continuationBase_mem_domain_v13
      (eventually_laplace_eq_cauchy_at_base_v13 g)

end AEGIS.RestrictedWeilCriterionContinuationV13

#print axioms AEGIS.RestrictedWeilCriterionContinuationV13.zero_kernel_laplace_eq_cauchy_on_punctured_right_half_v13
