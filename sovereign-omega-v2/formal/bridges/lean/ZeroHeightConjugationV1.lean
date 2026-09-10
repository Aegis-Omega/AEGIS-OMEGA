import Mathlib.NumberTheory.Harmonic.ZetaAsymp

/-!
AEGIS Ω — conjugation symmetry of the finite-height nontrivial zeta-zero carrier v1.

This lane proves only that the predicate

  zeta(rho) = 0, rho nontrivial, |Im(rho)| ≤ T

is invariant under complex conjugation. It does not assert invariance of analytic
multiplicity, pair the multiplicity-weighted finite sum, introduce a height limit,
prove an explicit formula, place zeros on the critical line, or prove RH.

HEIGHT_CARRIER_CONJUGATION_ONLY
MULTIPLICITY_CONJUGATION_OPEN
FINITE_SUM_CONJUGATION_PAIRING_OPEN
HEIGHT_LIMIT_EXISTENCE_OPEN
EXPLICIT_FORMULA_OPEN
CRITICAL_LINE_RE_HALF_OPEN
RH_EQUIVALENCE_OPEN
-/

open Complex

/-- Nontrivial Riemann-zeta zeros with imaginary height at most `T`. -/
def NontrivialZeroHeightSetV1 (T : ℝ) : Set ℂ :=
  {rho | riemannZeta rho = 0 ∧
         (¬ ∃ n : ℕ, rho = -(2 : ℂ) * (n + 1)) ∧
         |rho.im| ≤ T}

/-- Complex conjugation preserves the finite-height nontrivial zeta-zero carrier. -/
theorem nontrivial_zero_height_conj_mem_v1
    {T : ℝ} {rho : ℂ} (hrho : rho ∈ NontrivialZeroHeightSetV1 T) :
    conj rho ∈ NontrivialZeroHeightSetV1 T := by
  change riemannZeta rho = 0 ∧
      (¬ ∃ n : ℕ, rho = -(2 : ℂ) * (n + 1)) ∧ |rho.im| ≤ T at hrho
  rcases hrho with ⟨hz, hnontrivial, him⟩
  change riemannZeta (conj rho) = 0 ∧
      (¬ ∃ n : ℕ, conj rho = -(2 : ℂ) * (n + 1)) ∧ |(conj rho).im| ≤ T
  constructor
  · rw [riemannZeta_conj, hz]
    simp
  constructor
  · rintro ⟨n, hn⟩
    apply hnontrivial
    refine ⟨n, ?_⟩
    have hc := congrArg conj hn
    simpa using hc
  · simpa using him

/-- Membership in the finite-height carrier is exactly invariant under conjugation. -/
theorem nontrivial_zero_height_conj_iff_v1
    {T : ℝ} {rho : ℂ} :
    conj rho ∈ NontrivialZeroHeightSetV1 T ↔
      rho ∈ NontrivialZeroHeightSetV1 T := by
  constructor
  · intro h
    have hh := nontrivial_zero_height_conj_mem_v1 h
    simpa using hh
  · exact nontrivial_zero_height_conj_mem_v1

#check NontrivialZeroHeightSetV1
#check nontrivial_zero_height_conj_mem_v1
#check nontrivial_zero_height_conj_iff_v1
#print axioms nontrivial_zero_height_conj_mem_v1
#print axioms nontrivial_zero_height_conj_iff_v1
