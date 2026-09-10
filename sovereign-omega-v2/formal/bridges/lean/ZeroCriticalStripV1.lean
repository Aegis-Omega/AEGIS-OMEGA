import Mathlib.NumberTheory.LSeries.HurwitzZetaValues
import Mathlib.NumberTheory.LSeries.Nonvanishing
import Mathlib.NumberTheory.LSeries.RiemannZeta

/-!
AEGIS Ω — classical critical-strip localization v1.

This lane classifies the negative-integer zeros and then proves that every
nontrivial Riemann-zeta zero lies in the open critical strip. It does not place
nontrivial zeros on the critical line and therefore does not prove RH.

CRITICAL_STRIP_ONLY_NOT_CRITICAL_LINE
HEIGHT_TRUNCATION_EQUIVALENCE_OPEN
EXPLICIT_FORMULA_THEOREM_OPEN
RH_EQUIVALENCE_OPEN
-/

open Complex

/-- Even Bernoulli numbers of strictly positive even index are nonzero.

This is derived from Mathlib's exact formula for `ζ(2k)` together with its
nonvanishing theorem on `Re(s) ≥ 1`. -/
theorem bernoulli_two_mul_succ_ne_zero_v1 (m : ℕ) :
    bernoulli (2 * (m + 1)) ≠ 0 := by
  intro hb
  have hk : m + 1 ≠ 0 := by omega
  have hformula := riemannZeta_two_mul_nat (k := m + 1) hk
  have hz0 : riemannZeta (2 * (↑(m + 1) : ℂ)) = 0 := by
    rw [hformula]
    simp [hb]
  have hzne : riemannZeta (2 * (↑(m + 1) : ℂ)) ≠ 0 := by
    apply riemannZeta_ne_zero_of_one_le_re
    norm_num
    exact_mod_cast (show 1 ≤ 2 * (m + 1) by omega)
  exact hzne hz0

/-- Riemann zeta does not vanish at negative odd integers. -/
theorem riemannZeta_neg_odd_ne_zero_v1 (m : ℕ) :
    riemannZeta (-(↑(2 * m + 1) : ℂ)) ≠ 0 := by
  have hb : bernoulli (2 * (m + 1)) ≠ 0 :=
    bernoulli_two_mul_succ_ne_zero_v1 m
  rw [riemannZeta_neg_nat_eq_bernoulli]
  have hidx : 2 * m + 1 + 1 = 2 * (m + 1) := by omega
  rw [hidx]
  apply div_ne_zero
  · apply mul_ne_zero
    · simp
    · exact_mod_cast hb
  · exact_mod_cast (show 2 * m + 1 + 1 ≠ 0 by omega)

/-- Every zero of zeta at a negative natural integer is one of the classical
negative even zeros `-2(m+1)`. -/
theorem riemannZeta_neg_nat_zero_is_trivial_v1
    (n : ℕ) (hz : riemannZeta (-(n : ℂ)) = 0) :
    ∃ m : ℕ, n = 2 * (m + 1) := by
  obtain ⟨m, rfl | rfl⟩ := Nat.even_or_odd' n
  · cases m with
    | zero =>
        norm_num [riemannZeta_zero] at hz
    | succ m =>
        exact ⟨m, by simp⟩
  · exact (riemannZeta_neg_odd_ne_zero_v1 m hz).elim

/-- Every nontrivial Riemann-zeta zero lies in the classical open critical strip.

This is a localization theorem only. It does not assert the Riemann hypothesis. -/
theorem riemann_nontrivial_zero_in_critical_strip_v1
    {s : ℂ} (hz : riemannZeta s = 0)
    (hnottrivial : ¬ ∃ m : ℕ, s = -2 * (m + 1)) :
    0 < s.re ∧ s.re < 1 := by
  have hright : s.re < 1 := by
    by_contra hlt
    have hge : 1 ≤ s.re := le_of_not_gt hlt
    exact (riemannZeta_ne_zero_of_one_le_re hge) hz
  have hnotneg : ∀ n : ℕ, s ≠ -(n : ℂ) := by
    intro n hs
    have hzn : riemannZeta (-(n : ℂ)) = 0 := by
      simpa [hs] using hz
    obtain ⟨m, hn⟩ := riemannZeta_neg_nat_zero_is_trivial_v1 n hzn
    apply hnottrivial
    refine ⟨m, ?_⟩
    simp [hs, hn]
  have hleft : 0 < s.re := by
    by_contra hpos
    have hle : s.re ≤ 0 := le_of_not_gt hpos
    have hs1 : s ≠ 1 := by
      intro hs
      subst s
      norm_num at hle
    have hmirror_re : 1 ≤ (1 - s).re := by
      simp
      linarith
    have hmirror_ne : riemannZeta (1 - s) ≠ 0 :=
      riemannZeta_ne_zero_of_one_le_re hmirror_re
    have hfe := riemannZeta_one_sub hnotneg hs1
    have hmirror_zero : riemannZeta (1 - s) = 0 := by
      simpa [hz] using hfe
    exact hmirror_ne hmirror_zero
  exact ⟨hleft, hright⟩

#check bernoulli_two_mul_succ_ne_zero_v1
#check riemannZeta_neg_odd_ne_zero_v1
#check riemannZeta_neg_nat_zero_is_trivial_v1
#check riemann_nontrivial_zero_in_critical_strip_v1

#print axioms bernoulli_two_mul_succ_ne_zero_v1
#print axioms riemannZeta_neg_odd_ne_zero_v1
#print axioms riemannZeta_neg_nat_zero_is_trivial_v1
#print axioms riemann_nontrivial_zero_in_critical_strip_v1
