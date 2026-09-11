import ZeroShellAnalyticSynthesisV1
import Lc.LiCriterion.HadamardSummabilityBridge
import Lc.LiCriterion.XiGrowth
import Hadamard.OrderOne.TailEstimates
import Mathlib.Analysis.SpecialFunctions.Pow.Real

/-!
AEGIS Ω — multiplicity-aware quantitative zero counting v1.

This lane is RH-independent.  It reuses the canonical AEGIS nontrivial-zero
carrier and analytic-order multiplicity, while pinning an independently
compiled Jensen/Hadamard provider for the entire Riemann xi function.

The first production checkpoint proves two provider-facing facts:

* the analytic multiplicity of `LiCriterion.riemannXi` equals the analytic
  multiplicity of `riemannZeta` at every nontrivial zero;
* the cumulative multiplicity of nontrivial zeros in centered norm balls is
  `O(r^2)`, obtained from the provider's order-`≤ 1` theorem with `ε = 1`.

The final AEGIS shell theorem is added only after these helpers compile under
the exact AEGIS Lean/Mathlib pins.

ZERO_COUNTING_QUADRATIC_BOUND_V1
RH_INDEPENDENT_ZERO_COUNTING
CRITICAL_LINE_RE_HALF_OPEN
EXPLICIT_FORMULA_OPEN
RH_EQUIVALENCE_OPEN
-/

open Set Filter Topology
open Complex

noncomputable section

/-- A deliberately coarse but sufficient shell-counting certificate.  The
quadratic exponent is paired downstream with quartic Mellin decay to recover
the existing quadratic shell-mass certificate. -/
def HasQuadraticShellMultiplicityBoundV1 : Prop :=
  ∃ A : ℝ, 0 ≤ A ∧
    ∀ n : ℕ,
      ZeroHeightShellMultiplicityMassV1 n ≤
        A * (((n : ℝ) + 1) ^ 2)

private theorem li_nontrivial_zero_ne_zero_v1
    (rho : LiCriterion.NontrivialZero) : rho.1 ≠ 0 := by
  intro h
  have hre := rho.2.2.1
  rw [h] at hre
  norm_num at hre

private theorem li_nontrivial_zero_ne_one_v1
    (rho : LiCriterion.NontrivialZero) : rho.1 ≠ 1 := by
  intro h
  have hre := rho.2.2.2
  rw [h] at hre
  norm_num at hre

private theorem li_analyticAt_completedRiemannZeta_v1
    (rho : LiCriterion.NontrivialZero) :
    AnalyticAt ℂ completedRiemannZeta rho.1 := by
  let U : Set ℂ := {0}ᶜ ∩ {1}ᶜ
  have hUopen : IsOpen U := isOpen_compl_singleton.inter isOpen_compl_singleton
  have hrhoU : rho.1 ∈ U := by
    exact ⟨by simpa using li_nontrivial_zero_ne_zero_v1 rho,
      by simpa using li_nontrivial_zero_ne_one_v1 rho⟩
  apply DifferentiableOn.analyticAt (s := U) _ (hUopen.mem_nhds hrhoU)
  intro z hz
  exact (differentiableAt_completedZeta
    (by simpa [U] using hz.1) (by simpa [U] using hz.2)).differentiableWithinAt

private theorem li_analyticOrderAt_zeta_eq_completed_v1
    (rho : LiCriterion.NontrivialZero) :
    analyticOrderAt riemannZeta rho.1 =
      analyticOrderAt completedRiemannZeta rho.1 := by
  let inverseGamma : ℂ → ℂ := fun z => (Complex.Gammaℝ z)⁻¹
  have hinverseAnalytic : AnalyticAt ℂ inverseGamma rho.1 := by
    exact Complex.differentiable_Gammaℝ_inv.analyticAt rho.1
  have hGammaNe : Complex.Gammaℝ rho.1 ≠ 0 :=
    Complex.Gammaℝ_ne_zero_of_re_pos rho.2.2.1
  have hinverseOrder : analyticOrderAt inverseGamma rho.1 = 0 := by
    exact hinverseAnalytic.analyticOrderAt_eq_zero.mpr (inv_ne_zero hGammaNe)
  have heq :
      riemannZeta =ᶠ[nhds rho.1]
        fun z => completedRiemannZeta z * inverseGamma z := by
    filter_upwards [eventually_ne_nhds (li_nontrivial_zero_ne_zero_v1 rho)] with z hz
    rw [riemannZeta_def_of_ne_zero hz, div_eq_mul_inv]
  calc
    analyticOrderAt riemannZeta rho.1 =
        analyticOrderAt
          (fun z => completedRiemannZeta z * inverseGamma z) rho.1 :=
      analyticOrderAt_congr heq
    _ = analyticOrderAt completedRiemannZeta rho.1 +
        analyticOrderAt inverseGamma rho.1 :=
      analyticOrderAt_mul (li_analyticAt_completedRiemannZeta_v1 rho) hinverseAnalytic
    _ = analyticOrderAt completedRiemannZeta rho.1 := by
      rw [hinverseOrder, add_zero]

private theorem li_xi_eq_half_mul_completed_v1
    {s : ℂ} (hs0 : s ≠ 0) (hs1 : s ≠ 1) :
    LiCriterion.riemannXi s =
      (1 / 2 : ℂ) * s * (s - 1) * completedRiemannZeta s := by
  simpa [LiCriterion.riemannXi, XiZeros.riemannXi] using
    (XiZeros.xi_eq_half_s_sm1_Lambda (s := s) hs0 hs1)

/-- Analytic multiplicity is unchanged by passing from zeta to the provider's
entire xi function at a nontrivial zero. -/
theorem li_xi_zeta_multiplicity_eq_v1
    (rho : LiCriterion.NontrivialZero) :
    analyticOrderNatAt LiCriterion.riemannXi rho.1 =
      analyticOrderNatAt riemannZeta rho.1 := by
  let factor : ℂ → ℂ := fun z => (1 / 2 : ℂ) * z * (z - 1)
  have hfactorAnalytic : AnalyticAt ℂ factor rho.1 := by
    dsimp [factor]
    fun_prop
  have hfactorNe : factor rho.1 ≠ 0 := by
    dsimp [factor]
    exact mul_ne_zero
      (mul_ne_zero (by norm_num) (li_nontrivial_zero_ne_zero_v1 rho))
      (sub_ne_zero.mpr (li_nontrivial_zero_ne_one_v1 rho))
  have hfactorOrder : analyticOrderAt factor rho.1 = 0 :=
    hfactorAnalytic.analyticOrderAt_eq_zero.mpr hfactorNe
  have heq :
      LiCriterion.riemannXi =ᶠ[nhds rho.1]
        fun z => factor z * completedRiemannZeta z := by
    filter_upwards
      [eventually_ne_nhds (li_nontrivial_zero_ne_zero_v1 rho),
       eventually_ne_nhds (li_nontrivial_zero_ne_one_v1 rho)] with z hz0 hz1
    simpa [factor, mul_assoc] using li_xi_eq_half_mul_completed_v1 hz0 hz1
  have horder :
      analyticOrderAt LiCriterion.riemannXi rho.1 =
        analyticOrderAt riemannZeta rho.1 := by
    calc
      analyticOrderAt LiCriterion.riemannXi rho.1 =
          analyticOrderAt
            (fun z => factor z * completedRiemannZeta z) rho.1 :=
        analyticOrderAt_congr heq
      _ = analyticOrderAt factor rho.1 +
          analyticOrderAt completedRiemannZeta rho.1 :=
        analyticOrderAt_mul hfactorAnalytic
          (li_analyticAt_completedRiemannZeta_v1 rho)
      _ = analyticOrderAt completedRiemannZeta rho.1 := by
        rw [hfactorOrder, zero_add]
      _ = analyticOrderAt riemannZeta rho.1 :=
        (li_analyticOrderAt_zeta_eq_completed_v1 rho).symm
  simp only [analyticOrderNatAt, horder]

/-- Cumulative multiplicity of nontrivial zeta zeros in centered norm balls
is bounded quadratically for all sufficiently large radii.  This is the exact
provider output needed before converting to AEGIS height shells. -/
theorem li_zeta_cumulative_quadratic_multiplicity_bound_v1 :
    ∃ R0 C : ℝ, 0 ≤ C ∧
      ∀ r : ℝ, R0 ≤ r →
        (∑ᶠ rho : LiCriterion.NontrivialZero,
          if ‖rho.1‖ ≤ r then
            (analyticOrderNatAt riemannZeta rho.1 : ℝ)
          else 0) ≤ C * r ^ 2 := by
  let Z : Hadamard.ZeroSet LiCriterion.riemannXi := LiCriterion.xiZeroSet
  letI : Countable Z.Zero := by
    dsimp [Z, LiCriterion.xiZeroSet]
    infer_instance
  have hzeros :
      ∀ s : ℂ, LiCriterion.riemannXi s = 0 ↔
        ∃ rho : Z.Zero, s = Z.z rho := by
    intro s
    simpa [Z, LiCriterion.xiZeroSet] using
      (LiCriterion.xi_zeros_are_nontrivial_zeros (s := s))
  have hinj : Function.Injective Z.z := by
    intro rho sigma h
    exact Subtype.ext h
  have hne : ∀ rho : Z.Zero, Z.z rho ≠ 0 := by
    intro rho
    simpa [Z, LiCriterion.xiZeroSet] using rho.ne_zero
  obtain ⟨R0, C, hC, hbound⟩ :=
    Hadamard.OrderOne.sum_multiplicity_zeros_le_rpow_of_order_le
      (f := LiCriterion.riemannXi)
      LiCriterion.xi_entire
      LiCriterion.XiGrowth.riemannXi_hasFiniteOrder
      (lam := (1 : ℝ))
      LiCriterion.XiGrowth.riemannXi_order_le_one
      (by norm_num)
      Z hzeros hinj hne
      (1 : ℝ) (by norm_num)
  refine ⟨R0, C, hC, ?_⟩
  intro r hr
  have hb := hbound r hr
  dsimp [Z, LiCriterion.xiZeroSet] at hb
  have hmult :
      (∑ᶠ rho : LiCriterion.NontrivialZero,
        if ‖rho.1‖ ≤ r then
          (analyticOrderNatAt riemannZeta rho.1 : ℝ)
        else 0) =
      (∑ᶠ rho : LiCriterion.NontrivialZero,
        if ‖rho.1‖ ≤ r then
          (analyticOrderNatAt LiCriterion.riemannXi rho.1 : ℝ)
        else 0) := by
    apply finsum_congr
    intro rho
    split_ifs <;> simp [li_xi_zeta_multiplicity_eq_v1]
  rw [hmult]
  simpa [Real.rpow_two] using hb

#check HasQuadraticShellMultiplicityBoundV1
#check li_xi_zeta_multiplicity_eq_v1
#check li_zeta_cumulative_quadratic_multiplicity_bound_v1
#print axioms li_xi_zeta_multiplicity_eq_v1
#print axioms li_zeta_cumulative_quadratic_multiplicity_bound_v1
