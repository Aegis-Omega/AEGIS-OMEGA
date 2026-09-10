import ZetaDivisorLedgerV1
import ZetaDivisorExhaustionV1
import Mathlib.Analysis.Analytic.IsolatedZeros
import Mathlib.NumberTheory.LSeries.Dirichlet

/-!
AEGIS Ω — zeta-divisor support bridge v1.

This bridge connects three already-separated facts:
1. Mathlib's actual `riemannZeta` is analytic away from its pole at `1`;
2. its divisor support is finite on each admissible compact region;
3. the exhaustion grid covers every point distinct from `1`.

The new obligation is to show that an actual zeta zero has a finite, nonzero
meromorphic order and therefore belongs to the divisor support and the filtered
finite nontrivial-zero ledger.

This does not prove convergence of the global zero sum, the explicit formula,
or the Riemann Hypothesis.

GLOBAL_ZERO_SUM_CONVERGENCE_OPEN
EXPLICIT_FORMULA_IDENTITY_OPEN
RH_EQUIVALENCE_OPEN
-/

open Set
open Complex
open Filter

noncomputable section

/-- The zeta meromorphic order is finite at every point away from the pole.
    Otherwise zeta would vanish on a punctured neighbourhood; analytic uniqueness
    on the connected set `ℂ \ {1}` would force zeta to vanish at `2`, contradicting
    Mathlib's nonvanishing theorem on `re s > 1`. -/
theorem zeta_meromorphic_order_ne_top_v1 {s : ℂ} (hs : s ≠ 1) :
    meromorphicOrderAt riemannZeta s ≠ ⊤ := by
  intro htop
  have hevent : ∀ᶠ z in 𝓝[≠] s, riemannZeta z = 0 :=
    meromorphicOrderAt_eq_top_iff.mp htop
  have hfreq : ∃ᶠ z in 𝓝[≠] s, riemannZeta z = 0 :=
    Eventually.frequently hevent
  have hsU : s ∈ ({1}ᶜ : Set ℂ) := by
    simpa using hs
  have hpre : IsPreconnected ({1}ᶜ : Set ℂ) :=
    (isConnected_compl_singleton_of_one_lt_rank (by simp) (1 : ℂ)).isPreconnected
  have hzeroOn : Set.EqOn riemannZeta 0 ({1}ᶜ : Set ℂ) :=
    analyticOn_riemannZeta.eqOn_zero_of_preconnected_of_frequently_eq_zero
      hpre hsU hfreq
  have hz2 : riemannZeta (2 : ℂ) = 0 := by
    simpa using hzeroOn (by norm_num : (2 : ℂ) ∈ ({1}ᶜ : Set ℂ))
  exact (riemannZeta_ne_zero_of_one_lt_re (s := (2 : ℂ)) (by norm_num)) hz2

/-- A zeta zero inside an admissible compact has a nonzero divisor coefficient. -/
theorem zeta_zero_divisor_coeff_ne_zero_v1
    {K : Set ℂ} (hK : ZetaAdmissibleCompactV1 K)
    {s : ℂ} (hsK : s ∈ K) (hz : riemannZeta s = 0) :
    ZetaDivisorV1 K s ≠ 0 := by
  have hmer : MeromorphicOn riemannZeta K :=
    zeta_meromorphic_on_admissible_compact_v1 hK
  have han : AnalyticAt ℂ riemannZeta s :=
    zeta_analytic_on_admissible_compact_v1 hK s hsK
  have hsne : s ≠ 1 := by
    simpa using hK.2 hsK
  rw [ZetaDivisorV1, MeromorphicOn.divisor_apply hmer hsK]
  simp only [WithTop.untop₀_eq_zero, not_or]
  constructor
  · intro horder
    exact (han.meromorphicOrderAt_eq_zero_iff.mp horder) hz
  · exact zeta_meromorphic_order_ne_top_v1 hsne

/-- Therefore every zeta zero in the region belongs to the divisor support. -/
theorem zeta_zero_mem_divisor_support_v1
    {K : Set ℂ} (hK : ZetaAdmissibleCompactV1 K)
    {s : ℂ} (hsK : s ∈ K) (hz : riemannZeta s = 0) :
    s ∈ (ZetaDivisorV1 K).support := by
  exact Function.mem_support.mpr (zeta_zero_divisor_coeff_ne_zero_v1 hK hsK hz)

/-- A standard nontrivial zero in an admissible region is present in the
    filtered finite ledger. -/
theorem nontrivial_zero_mem_filtered_ledger_v1
    {K : Set ℂ} (hK : ZetaAdmissibleCompactV1 K)
    {s : ℂ} (hsK : s ∈ K) (hz : IsNontrivialZetaZeroV1 s) :
    s ∈ ZetaNontrivialDivisorSupportFinsetV1 K hK := by
  classical
  simp only [ZetaNontrivialDivisorSupportFinsetV1, Finset.mem_filter,
    Set.Finite.mem_toFinset]
  exact ⟨zeta_zero_mem_divisor_support_v1 hK hsK hz.1, hz⟩

/-- Every standard nontrivial zeta zero occurs in some finite divisor ledger
    arising from the compact exhaustion grid. -/
theorem nontrivial_zero_occurs_in_some_finite_ledger_v1
    {s : ℂ} (hz : IsNontrivialZetaZeroV1 s) :
    ∃ r k : ℕ,
      ∃ hK : ZetaAdmissibleCompactV1 (ZetaExhaustionRegionV1 r k),
        s ∈ ZetaNontrivialDivisorSupportFinsetV1
          (ZetaExhaustionRegionV1 r k) hK := by
  have hzShape : IsNontrivialZetaZeroShapeV1 s := by
    exact hz
  obtain ⟨r, k, hsK⟩ := nontrivial_zeta_zero_covered_by_exhaustion_v1 hzShape
  have hKshape := zeta_exhaustion_region_admissible_shape_v1 r k
  have hK : ZetaAdmissibleCompactV1 (ZetaExhaustionRegionV1 r k) := by
    exact hKshape
  refine ⟨r, k, hK, ?_⟩
  exact nontrivial_zero_mem_filtered_ledger_v1 hK hsK hz

#check riemannZeta_ne_zero_of_one_lt_re
#check AnalyticOnNhd.eqOn_zero_of_preconnected_of_frequently_eq_zero
#check meromorphicOrderAt_eq_top_iff
#check zeta_meromorphic_order_ne_top_v1
#check zeta_zero_divisor_coeff_ne_zero_v1
#check zeta_zero_mem_divisor_support_v1
#check nontrivial_zero_mem_filtered_ledger_v1
#check nontrivial_zero_occurs_in_some_finite_ledger_v1

#print axioms zeta_meromorphic_order_ne_top_v1
#print axioms zeta_zero_divisor_coeff_ne_zero_v1
#print axioms zeta_zero_mem_divisor_support_v1
#print axioms nontrivial_zero_mem_filtered_ledger_v1
#print axioms nontrivial_zero_occurs_in_some_finite_ledger_v1
