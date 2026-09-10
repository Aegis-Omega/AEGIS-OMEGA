import Mathlib.Analysis.Analytic.Uniqueness
import Mathlib.Analysis.Meromorphic.Divisor
import Mathlib.NumberTheory.LSeries.RiemannZeta

/-!
AEGIS Ω — bounded Riemann-zeta zero finiteness v1.

This lane proves a local/compact finiteness fact needed before any global sum over
nontrivial zeros can be represented. It deliberately does not enumerate all zeros,
choose a summation convention, or state an explicit-formula equality.

BOUNDED_ZERO_FINITE_SUPPORT_ONLY
GLOBAL_ZERO_ENUMERATION_OPEN
GLOBAL_ZERO_SUM_OPEN
EXPLICIT_FORMULA_THEOREM_OPEN
-/

open Set Filter Topology
open Complex

noncomputable section

/-- Riemann-zeta zeros lying in a declared region `K`. -/
def RiemannZeroSetOnV1 (K : Set ℂ) : Set ℂ :=
  { z | z ∈ K ∧ riemannZeta z = 0 }

/-- Outside the pole location `1`, the analytic order of `riemannZeta` is finite.

The proof is not an RH argument. If the analytic order were infinite, zeta would
vanish on a neighborhood. The identity principle on the connected set `{1}ᶜ`
would then force zeta to vanish at `0`, contradicting `riemannZeta_zero`.
-/
theorem riemannZeta_analyticOrderAt_ne_top_v1 {z : ℂ} (hz : z ≠ 1) :
    analyticOrderAt riemannZeta z ≠ ⊤ := by
  intro htop
  have hlocal : riemannZeta =ᶠ[𝓝 z] (fun _ : ℂ => 0) := by
    filter_upwards [analyticOrderAt_eq_top.mp htop] with w hw
    exact hw
  have hzU : z ∈ ({1}ᶜ : Set ℂ) := by
    simpa using hz
  have heq : Set.EqOn riemannZeta (fun _ : ℂ => 0) ({1}ᶜ : Set ℂ) :=
    analyticOn_riemannZeta.eqOn_of_preconnected_of_eventuallyEq
      analyticOnNhd_const
      (isConnected_compl_singleton_of_one_lt_rank (by simp) 1).isPreconnected
      hzU hlocal
  have hzero : riemannZeta (0 : ℂ) = 0 := by
    simpa using heq (by simp : (0 : ℂ) ∈ ({1}ᶜ : Set ℂ))
  rw [riemannZeta_zero] at hzero
  norm_num at hzero

/-- On every compact set avoiding the pole `1`, the set of Riemann-zeta zeros is finite.

This uses Mathlib's finite-support theorem for divisors on compact sets. The
`riemannZeta_analyticOrderAt_ne_top_v1` lemma excludes the only case in which a
zero could be erased by the divisor's `untop₀` representation.
-/
theorem riemann_zero_set_finite_on_compact_away_one_v1
    {K : Set ℂ} (hK : IsCompact K) (hK1 : K ⊆ ({1}ᶜ : Set ℂ)) :
    (RiemannZeroSetOnV1 K).Finite := by
  have hAn : AnalyticOnNhd ℂ riemannZeta K := analyticOn_riemannZeta.mono hK1
  have hDiv : (MeromorphicOn.divisor riemannZeta K).support.Finite :=
    hAn.meromorphicOn.divisor_support_finite_of_subset hK (Subset.rfl)
  refine hDiv.subset ?_
  intro z hz
  rcases hz with ⟨hzK, hzero⟩
  have hz1 : z ≠ 1 := by
    have hzU := hK1 hzK
    simpa using hzU
  have hne0 : analyticOrderAt riemannZeta z ≠ 0 :=
    (hAn z hzK).analyticOrderAt_ne_zero.mpr hzero
  have hnetop : analyticOrderAt riemannZeta z ≠ ⊤ :=
    riemannZeta_analyticOrderAt_ne_top_v1 hz1
  rw [Function.mem_support, hAn.divisor_apply hzK]
  simp [WithTop.untop₀_eq_zero, hne0, hnetop]

#check RiemannZeroSetOnV1
#check riemannZeta_analyticOrderAt_ne_top_v1
#check riemann_zero_set_finite_on_compact_away_one_v1

#print axioms riemannZeta_analyticOrderAt_ne_top_v1
#print axioms riemann_zero_set_finite_on_compact_away_one_v1
