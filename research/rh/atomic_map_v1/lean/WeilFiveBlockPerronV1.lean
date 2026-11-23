import Mathlib.Algebra.BigOperators.Fin
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Fin.VecNotation
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.FinCases
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring
import Mathlib.Tactic.NormNum

set_option autoImplicit false
noncomputable section

namespace AEGIS.WeilFiveBlockPerronV1

/-- Rational ceilings for the four off-diagonal gaps. The diagonal is zero. -/
def ceiling (k : ℕ) : ℝ :=
  match k with
  | 1 => 501 / 1000
  | 2 => 357 / 1000
  | 3 => 256 / 1000
  | 4 => 184 / 1000
  | _ => 0

def cross (i j : Fin 5) : ℝ := ceiling (i.val - j.val + (j.val - i.val))

def weight (i : Fin 5) : ℝ := ![80, 95, 100, 95, 80] i

theorem cross_symm (i j : Fin 5) : cross i j = cross j i := by
  simp only [cross, Nat.add_comm]

theorem cross_self (i : Fin 5) : cross i i = 0 := by simp [cross, ceiling]

theorem cross_nonneg (i j : Fin 5) : 0 ≤ cross i j := by
  fin_cases i <;> fin_cases j <;> norm_num [cross, ceiling]

theorem weight_pos (i : Fin 5) : 0 < weight i := by
  fin_cases i <;> norm_num [weight]

theorem row_bound (i : Fin 5) :
    ∑ j : Fin 5, cross i j * (weight j / weight i) ≤ (153 / 100 : ℝ) := by
  fin_cases i <;> norm_num [Fin.sum_univ_succ, cross, ceiling, weight]

theorem quadratic_bound (x : Fin 5 → ℝ) :
    ∑ i : Fin 5, ∑ j : Fin 5, cross i j * x i * x j ≤
      (153 / 100 : ℝ) * ∑ i : Fin 5, x i ^ 2 := by
  let term : Fin 5 → Fin 5 → ℝ := fun i j => x i ^ 2 * (cross i j * (weight j / weight i))
  have pair (i j : Fin 5) :
      2 * (cross i j * x i * x j) ≤ term i j + term j i := by
    have hi := weight_pos i
    have hj := weight_pos j
    dsimp [term]
    rw [cross_symm j i]
    have he :
        x i ^ 2 * (cross i j * (weight j / weight i)) +
          x j ^ 2 * (cross i j * (weight i / weight j)) -
          2 * (cross i j * x i * x j) =
        (cross i j / (weight i * weight j)) *
          (weight j * x i - weight i * x j) ^ 2 := by
      field_simp [hi.ne', hj.ne']
      ring
    linarith [he, mul_nonneg (div_nonneg (cross_nonneg i j)
      (mul_nonneg hi.le hj.le)) (sq_nonneg (weight j * x i - weight i * x j))]
  have hterm :
      ∑ i : Fin 5, ∑ j : Fin 5, term i j ≤
        (153 / 100 : ℝ) * ∑ i : Fin 5, x i ^ 2 := by
    rw [Finset.mul_sum]
    refine Finset.sum_le_sum fun i _ => ?_
    simp only [term, ← Finset.mul_sum]
    rw [mul_comm (153 / 100 : ℝ)]
    exact mul_le_mul_of_nonneg_left (row_bound i) (sq_nonneg _)
  have hsum := Finset.sum_le_sum (s := Finset.univ) fun i (_ : i ∈ (Finset.univ : Finset (Fin 5))) =>
    Finset.sum_le_sum (s := Finset.univ) fun j (_ : j ∈ (Finset.univ : Finset (Fin 5))) => pair i j
  simp only [Finset.sum_add_distrib, ← Finset.mul_sum] at hsum
  rw [Finset.sum_comm (f := fun i j => term j i)] at hsum
  linarith

end AEGIS.WeilFiveBlockPerronV1

#print axioms AEGIS.WeilFiveBlockPerronV1.row_bound
#print axioms AEGIS.WeilFiveBlockPerronV1.quadratic_bound
