import Std

namespace AEGIS.FiveBlockArithmetic

def indices : List Nat := [0, 1, 2, 3, 4]
def weights : List Nat := [80, 95, 100, 95, 80]
def numerators : List Nat := [0, 501, 357, 256, 184]

def weightedRowNumerator (i : Nat) : Nat :=
  (indices.map (fun j => numerators[i - j + (j - i)]! * weights[j]!)).sum

-- The integer form of the certificate Cw ≤ (153/100)w.
theorem perron_rows :
    indices.all (fun i => decide (weightedRowNumerator i ≤ 1530 * weights[i]!)) = true := by
  decide

-- The prior exp bounds 63/65 and 65/63 exclude both neighbouring integers.
theorem integer_isolation :
    [2, 4, 8, 16].all (fun n : Nat => decide ((n - 1) * 65 < 63 * n) &&
      decide (65 * n < (n + 1) * 63)) = true := by
  decide

-- Rational lower bounds for the square roots, with denominator 1000.
theorem square_root_floors :
    [(2, 1414), (4, 2000), (8, 2828), (16, 4000)].all
      (fun p : Nat × Nat => decide (p.2 ^ 2 ≤ p.1 * 1000 ^ 2)) = true := by
  decide

-- With log 2 < 694/1000, the ceiling also includes the E/100 Archimedean allowance.
theorem gap_ceilings :
    [(1, 1414), (2, 2000), (3, 2828), (4, 4000)].all
      (fun p : Nat × Nat => decide (694 * 1000 ≤ (numerators[p.1]! - 10) * p.2)) = true := by
  decide

theorem margin : 1700 - 1530 = 170 ∧ 100 ≤ (170 : Nat) := by decide

end AEGIS.FiveBlockArithmetic

#print axioms AEGIS.FiveBlockArithmetic.perron_rows
#print axioms AEGIS.FiveBlockArithmetic.integer_isolation
#print axioms AEGIS.FiveBlockArithmetic.square_root_floors
#print axioms AEGIS.FiveBlockArithmetic.gap_ceilings
#print axioms AEGIS.FiveBlockArithmetic.margin
