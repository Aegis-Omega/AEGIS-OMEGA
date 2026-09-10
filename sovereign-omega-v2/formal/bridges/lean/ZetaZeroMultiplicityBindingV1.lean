import Mathlib.Analysis.Analytic.Order
import Mathlib.Analysis.Analytic.Uniqueness
import Mathlib.NumberTheory.LSeries.Nonvanishing
import Mathlib.NumberTheory.LSeries.RiemannZeta

/-!
AEGIS Ω — analytic multiplicity binding for Riemann-zeta zeros v1.

This lane binds a zeta zero to Mathlib's actual analytic vanishing order.
It proves that every point `s` satisfying `riemannZeta s = 0` has finite,
strictly positive natural analytic order.

The proof first excludes `s = 1`, obtains analyticity of `riemannZeta` at
`s`, and rules out infinite order using the analytic identity theorem on
the connected domain `{1}ᶜ`: local identically-zero behavior would force
`riemannZeta` to vanish at `2`, contradicting the pinned nonvanishing theorem.

No finite or infinite zero sum is defined here.

FINITE_MULTIPLICITY_BINDING_ONLY
HEIGHT_ZERO_SUM_OPEN
HEIGHT_LIMIT_EXISTENCE_OPEN
EXPLICIT_FORMULA_OPEN
CRITICAL_LINE_RE_HALF_OPEN
RH_EQUIVALENCE_OPEN
-/

open Complex Set Filter

noncomputable section

/-- Natural analytic vanishing order used as the multiplicity of a zeta zero. -/
def ZetaZeroMultiplicityV1 (s : ℂ) : ℕ :=
  analyticOrderNatAt riemannZeta s

private theorem riemann_zeta_zero_order_ne_top_v1
    {s : ℂ} (hz : riemannZeta s = 0) :
    analyticOrderAt riemannZeta s ≠ ⊤ := by
  have hs1 : s ≠ 1 := by
    intro hs
    subst s
    exact (riemannZeta_ne_zero_of_one_le_re (s := (1 : ℂ)) (by norm_num)) hz
  have hs_mem : s ∈ ({1}ᶜ : Set ℂ) := by
    simpa using hs1
  have ha : AnalyticAt ℂ riemannZeta s :=
    analyticOn_riemannZeta s hs_mem
  intro htop
  have hev : riemannZeta =ᶠ[𝓝 s] (fun _ : ℂ => 0) := by
    simpa using (analyticOrderAt_eq_top.mp htop)
  have hzero_an : AnalyticOnNhd ℂ (fun _ : ℂ => 0) ({1}ᶜ : Set ℂ) := by
    fun_prop
  have heq : EqOn riemannZeta (fun _ : ℂ => 0) ({1}ᶜ : Set ℂ) :=
    analyticOn_riemannZeta.eqOn_of_preconnected_of_eventuallyEq
      hzero_an
      (isConnected_compl_singleton_of_one_lt_rank (by simp) 1).isPreconnected
      hs_mem
      hev
  have htwo_mem : (2 : ℂ) ∈ ({1}ᶜ : Set ℂ) := by
    norm_num
  have hz2 : riemannZeta (2 : ℂ) = 0 := by
    simpa using heq htwo_mem
  exact (riemannZeta_ne_zero_of_one_le_re (s := (2 : ℂ)) (by norm_num)) hz2

/-- Every Riemann-zeta zero has strictly positive finite analytic multiplicity. -/
theorem riemann_zeta_zero_multiplicity_pos_v1
    {s : ℂ} (hz : riemannZeta s = 0) :
    0 < ZetaZeroMultiplicityV1 s := by
  have hs1 : s ≠ 1 := by
    intro hs
    subst s
    exact (riemannZeta_ne_zero_of_one_le_re (s := (1 : ℂ)) (by norm_num)) hz
  have hs_mem : s ∈ ({1}ᶜ : Set ℂ) := by
    simpa using hs1
  have ha : AnalyticAt ℂ riemannZeta s :=
    analyticOn_riemannZeta s hs_mem
  have htop : analyticOrderAt riemannZeta s ≠ ⊤ :=
    riemann_zeta_zero_order_ne_top_v1 hz
  have horder_ne : analyticOrderAt riemannZeta s ≠ 0 :=
    ha.analyticOrderAt_ne_zero.mpr hz
  have hcast := Nat.cast_analyticOrderNatAt (f := riemannZeta) (z₀ := s) htop
  have hnat_ne : analyticOrderNatAt riemannZeta s ≠ 0 := by
    intro hn
    apply horder_ne
    calc
      analyticOrderAt riemannZeta s = (analyticOrderNatAt riemannZeta s : ℕ∞) := hcast.symm
      _ = 0 := by simp [hn]
  exact Nat.pos_of_ne_zero hnat_ne

#check ZetaZeroMultiplicityV1
#check riemann_zeta_zero_multiplicity_pos_v1
#print axioms riemann_zeta_zero_multiplicity_pos_v1
