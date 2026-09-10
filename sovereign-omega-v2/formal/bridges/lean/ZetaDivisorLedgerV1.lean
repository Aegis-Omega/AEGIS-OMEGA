import Mathlib.Analysis.Meromorphic.Divisor
import Mathlib.NumberTheory.LSeries.RiemannZeta

/-!
AEGIS Ω — finite zeta-divisor ledger v1.

This file works directly with Mathlib's analytically continued `riemannZeta` and
its meromorphic/analytic divisor machinery. It proves only a local finiteness
fact: on each compact set avoiding the pole `s = 1`, the zeta divisor has finite
support. This yields a finite, multiplicity-weighted ledger after filtering to
the standard nontrivial-zero predicate.

It does not enumerate all nontrivial zeros, prove convergence of the global zero
sum, prove the explicit formula, or prove/disprove the Riemann Hypothesis.

GLOBAL_ZERO_SUM_CONVERGENCE_OPEN
EXPLICIT_FORMULA_IDENTITY_OPEN
-/

open Set
open Complex

noncomputable section

/-- Compact regions on which `riemannZeta` is analytic: they avoid its pole at `1`. -/
def ZetaAdmissibleCompactV1 (K : Set ℂ) : Prop :=
  IsCompact K ∧ K ⊆ ({1}ᶜ : Set ℂ)

/-- The Mathlib meromorphic divisor of the actual Riemann zeta function on `K`. -/
def ZetaDivisorV1 (K : Set ℂ) :=
  MeromorphicOn.divisor riemannZeta K

/-- Standard nontrivial-zero predicate matching Mathlib's RH target boundary. -/
def IsNontrivialZetaZeroV1 (s : ℂ) : Prop :=
  riemannZeta s = 0 ∧
  (¬ ∃ n : ℕ, s = -2 * (n + 1)) ∧
  s ≠ 1

/-- Restrict Mathlib's zeta analyticity theorem to an admissible compact region. -/
theorem zeta_analytic_on_admissible_compact_v1
    {K : Set ℂ} (hK : ZetaAdmissibleCompactV1 K) :
    AnalyticOnNhd ℂ riemannZeta K :=
  analyticOn_riemannZeta.mono hK.2

/-- The same restricted region is therefore meromorphic. -/
theorem zeta_meromorphic_on_admissible_compact_v1
    {K : Set ℂ} (hK : ZetaAdmissibleCompactV1 K) :
    MeromorphicOn riemannZeta K :=
  (zeta_analytic_on_admissible_compact_v1 hK).meromorphicOn

/-- Machine-checked local finiteness of the actual zeta divisor. -/
theorem zeta_divisor_support_finite_v1
    {K : Set ℂ} (hK : ZetaAdmissibleCompactV1 K) :
    (ZetaDivisorV1 K).support.Finite := by
  exact
    (zeta_meromorphic_on_admissible_compact_v1 hK).divisor_support_finite_of_subset
      hK.1 (Subset.rfl)

/-- On the analytic region, the divisor coefficient is the analytic vanishing order. -/
theorem zeta_divisor_apply_eq_analytic_order_v1
    {K : Set ℂ} (hK : ZetaAdmissibleCompactV1 K)
    {s : ℂ} (hs : s ∈ K) :
    ZetaDivisorV1 K s = ((analyticOrderAt riemannZeta s).map (↑)).untop₀ := by
  simpa [ZetaDivisorV1] using
    (zeta_analytic_on_admissible_compact_v1 hK).divisor_apply hs

/-- Finite support of the zeta divisor, filtered to standard nontrivial zeros. -/
noncomputable def ZetaNontrivialDivisorSupportFinsetV1
    (K : Set ℂ) (hK : ZetaAdmissibleCompactV1 K) : Finset ℂ := by
  classical
  exact (zeta_divisor_support_finite_v1 hK).toFinset.filter IsNontrivialZetaZeroV1

/-- A finite multiplicity-weighted zero ledger for an arbitrary complex weight.
    Later explicit-formula work may instantiate `weight` with a Mellin transform. -/
noncomputable def ZetaNontrivialWeightedLedgerSumV1
    (K : Set ℂ) (hK : ZetaAdmissibleCompactV1 K)
    (weight : ℂ → ℂ) : ℂ := by
  classical
  exact ∑ s in ZetaNontrivialDivisorSupportFinsetV1 K hK,
    ((ZetaDivisorV1 K s : ℤ) : ℂ) * weight s

#check analyticOn_riemannZeta
#check MeromorphicOn.divisor
#check zeta_divisor_support_finite_v1
#check zeta_divisor_apply_eq_analytic_order_v1
#check ZetaNontrivialDivisorSupportFinsetV1
#check ZetaNontrivialWeightedLedgerSumV1
