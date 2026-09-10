import Mathlib.NumberTheory.LSeries.Nonvanishing
import Mathlib.NumberTheory.LSeries.RiemannZeta

/-!
AEGIS Ω — zero-strip preboundary v1.

This lane proves only the non-integer half-plane exclusions needed before a full
critical-strip theorem can be stated. The negative-integer boundary remains open
and must be closed using pinned special-value results.

NEGATIVE_INTEGER_ZERO_CLASSIFICATION_OPEN
HEIGHT_TRUNCATION_EQUIVALENCE_OPEN
EXPLICIT_FORMULA_THEOREM_OPEN
RH_EQUIVALENCE_OPEN
-/

open Complex

/-- Any Riemann-zeta zero lies strictly to the left of `Re(s)=1`. -/
theorem riemann_zero_re_lt_one_v1 {s : ℂ} (hz : riemannZeta s = 0) :
    s.re < 1 := by
  by_contra hlt
  have hge : 1 ≤ s.re := le_of_not_gt hlt
  exact (riemannZeta_ne_zero_of_one_le_re hge) hz

/-- A zeta zero with `Re(s) ≤ 0` cannot be a point which avoids all negative
natural integers. This is the functional-equation part of left localization.
The negative-integer boundary is deliberately handled in a later lane. -/
theorem riemann_zero_not_left_halfplane_if_not_neg_nat_v1
    {s : ℂ} (hz : riemannZeta s = 0)
    (hnotneg : ∀ n : ℕ, s ≠ -n) :
    ¬ s.re ≤ 0 := by
  intro hle
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

/-- Conditional positive-real-part result: once the negative-integer boundary is
excluded, every zeta zero has positive real part. -/
theorem riemann_zero_re_pos_if_not_neg_nat_v1
    {s : ℂ} (hz : riemannZeta s = 0)
    (hnotneg : ∀ n : ℕ, s ≠ -n) :
    0 < s.re := by
  exact lt_of_not_ge
    (riemann_zero_not_left_halfplane_if_not_neg_nat_v1 hz hnotneg)

#check riemann_zero_re_lt_one_v1
#check riemann_zero_not_left_halfplane_if_not_neg_nat_v1
#check riemann_zero_re_pos_if_not_neg_nat_v1

#print axioms riemann_zero_re_lt_one_v1
#print axioms riemann_zero_not_left_halfplane_if_not_neg_nat_v1
#print axioms riemann_zero_re_pos_if_not_neg_nat_v1
