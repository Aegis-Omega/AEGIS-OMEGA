import Mathlib.NumberTheory.LSeries.HurwitzZetaValues
import Mathlib.NumberTheory.LSeries.Nonvanishing

/-!
AEGIS Ω — classification of Riemann-zeta zeros at nonpositive integers v1.

This lane proves only that if `ζ(-n)=0` for `n : ℕ`, then `n` is a strictly
positive even integer, equivalently `n = 2 * (m + 1)` for some `m`.
It does not yet derive the lower real-part bound for the nontrivial-zero class,
the full critical strip, an explicit formula, or RH.

NEGATIVE_INTEGER_ZERO_CLASSIFICATION_ONLY
LOWER_NONTRIVIAL_ZERO_LOCALIZATION_OPEN
FULL_CRITICAL_STRIP_OPEN
HEIGHT_TRUNCATION_EQUIVALENCE_OPEN
RH_EQUIVALENCE_OPEN
-/

open Complex

/-- Positive even-index Bernoulli numbers used by the zeta special-value
classification are nonzero.

Rather than assuming a separate Bernoulli nonvanishing theorem, this follows
from the pinned formula for `ζ(2k)` together with pinned nonvanishing on
`Re(s) ≥ 1`. -/
theorem bernoulli_two_mul_succ_ne_zero_v1 (m : ℕ) :
    bernoulli (2 * (m + 1)) ≠ 0 := by
  intro hB
  have hk : m + 1 ≠ 0 := by omega
  have hzeta_ne : riemannZeta (2 * (m + 1)) ≠ 0 := by
    apply riemannZeta_ne_zero_of_one_le_re
    norm_num
    omega
  apply hzeta_ne
  rw [riemannZeta_two_mul_nat (k := m + 1) hk, hB]
  simp

/-- The only zeros among the points `-n`, `n : ℕ`, are at strictly negative
even integers. The forward implication is all that is needed to eliminate the
closed left half-plane from the nontrivial-zero class. -/
theorem riemann_zeta_neg_nat_zero_is_trivial_index_v1
    {n : ℕ} (hz : riemannZeta (-n) = 0) :
    ∃ m : ℕ, n = 2 * (m + 1) := by
  rcases Nat.even_or_odd' n with ⟨m, rfl | rfl⟩
  · by_cases hm : m = 0
    · subst m
      norm_num [riemannZeta_zero] at hz
    · obtain ⟨j, rfl⟩ := Nat.exists_eq_succ_of_ne_zero hm
      exact ⟨j, rfl⟩
  · have hBq : bernoulli ((2 * m + 1) + 1) ≠ 0 := by
      convert bernoulli_two_mul_succ_ne_zero_v1 m using 1 <;> omega
    have hzeta_ne : riemannZeta (-(2 * m + 1)) ≠ 0 := by
      rw [riemannZeta_neg_nat_eq_bernoulli]
      apply div_ne_zero
      · apply mul_ne_zero
        · exact pow_ne_zero _ (by norm_num)
        · exact_mod_cast hBq
      · norm_num
    exact (hzeta_ne hz).elim

#check bernoulli_two_mul_succ_ne_zero_v1
#check riemann_zeta_neg_nat_zero_is_trivial_index_v1
#print axioms bernoulli_two_mul_succ_ne_zero_v1
#print axioms riemann_zeta_neg_nat_zero_is_trivial_index_v1
