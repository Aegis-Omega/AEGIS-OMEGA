/-
AEGIS — what a cyclic (roots-of-unity) dilation filter can and cannot annihilate.

`WeilMomentAnnihilatorV1` uses the filter f(x) − 3f(2x) + 2f(4x), whose Mellin
multiplier in u = 2^(−s) is

    M(u) = (1 − u)(1 − 2u),

so the two Weil moments are exactly the two roots
    u = 1    ↔ s = 0     (the reflection moment)
    u = 1/2  ↔ s = 1     (the moment at the POLE of ζ)

A "cyclic" / n-fold phase filter is f(x) − f(2^n x), multiplier u^n − 1, whose
roots are precisely the n-th roots of unity — the 6- or 12-cyclic ring structure,
with the +6 phase on a 12-cycle being u ↦ −u.

This file settles what that cyclic structure reaches.
-/
import Mathlib.Analysis.SpecialFunctions.Complex.Log

namespace CyclicFilter

/-- The multiplier of the n-fold cyclic dilation filter, in `u = 2 ^ (-s)`. -/
def cyclicMultiplier (n : ℕ) (u : ℂ) : ℂ := u ^ n - 1

/-- **A cyclic filter does annihilate the reflection moment** `s = 0`, i.e. `u = 1`,
because `1` is a root of unity. -/
theorem cyclic_annihilates_reflection_moment (n : ℕ) :
    cyclicMultiplier n 1 = 0 := by
  simp [cyclicMultiplier]

/-- `1/2` is not a root of unity. -/
theorem half_not_root_of_unity : ¬ ∃ n : ℕ, 0 < n ∧ ((1 : ℂ) / 2) ^ n = 1 := by
  rintro ⟨n, hn, h⟩
  have hnorm := congrArg norm h
  rw [norm_pow, norm_one] at hnorm
  have h2 : ‖(1 : ℂ) / 2‖ = 1 / 2 := by norm_num
  rw [h2] at hnorm
  have : (1 / 2 : ℝ) ^ n < 1 :=
    pow_lt_one₀ (by norm_num) (by norm_num) (by omega)
  linarith

/-- **A cyclic filter never annihilates the pole moment** `s = 1`, i.e. `u = 1/2`.
No number of phase steps, and no choice of cycle length, reaches it. -/
theorem cyclic_never_annihilates_pole_moment (n : ℕ) (hn : 0 < n) :
    cyclicMultiplier n (1 / 2) ≠ 0 := by
  intro h
  exact half_not_root_of_unity ⟨n, hn, by
    have := sub_eq_zero.mp h
    simpa [cyclicMultiplier] using this⟩

/-- The repository's actual annihilator does reach it — its second factor has the
root `1/2` exactly, and that factor is not cyclotomic. -/
theorem repository_multiplier_annihilates_pole_moment :
    (1 - (1 / 2 : ℂ)) * (1 - 2 * (1 / 2 : ℂ)) = 0 := by norm_num

/-- So the pole moment is reachable, but only by a non-cyclic factor: any product
of cyclic multipliers still misses it. -/
theorem product_of_cyclic_never_annihilates_pole_moment
    (l : List ℕ) (hl : ∀ n ∈ l, 0 < n) :
    (l.map (fun n => cyclicMultiplier n (1 / 2))).prod ≠ 0 := by
  induction l with
  | nil => simp
  | cons a t ih =>
      simp only [List.map_cons, List.prod_cons]
      exact mul_ne_zero
        (cyclic_never_annihilates_pole_moment a (hl a (List.mem_cons_self ..)))
        (ih fun n hn => hl n (List.mem_cons_of_mem a hn))

end CyclicFilter

#print axioms CyclicFilter.cyclic_annihilates_reflection_moment
#print axioms CyclicFilter.half_not_root_of_unity
#print axioms CyclicFilter.cyclic_never_annihilates_pole_moment
#print axioms CyclicFilter.repository_multiplier_annihilates_pole_moment
#print axioms CyclicFilter.product_of_cyclic_never_annihilates_pole_moment
