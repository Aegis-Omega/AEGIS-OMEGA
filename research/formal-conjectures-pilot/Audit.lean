/-
Copyright 2026 AEGIS Omega contributors.
Licensed under the Apache License, Version 2.0.
-/
import Mathlib.RingTheory.Algebraic.Integral
import FormalConjectures.Wikipedia.Pell
import FormalConjectures.GreensOpenProblems.«72»

/-!
Exact snapshot: google-deepmind/formal-conjectures@7a41db3d761324599812d6ca6cb6a9f311046dc7.
The two Pell theorem bodies are replaced without changing their declarations.
This separate theorem refutes one instance of Green72.allowedSetSize_le as formalized.
-/
namespace AegisBench

/-- The benchmark's predicate admits a singleton when k = N = 1. -/
@[category test, AMS 5 52]
theorem green72_singleton_allowed : Green72.AllowedSet 1 1 {(0, 0)} := by
  constructor
  · intro i hi
    simp only [Finset.mem_singleton] at hi
    subst i
    norm_num
  · intro t ht hc
    simpa using (collinear_singleton ℝ ((0 : ℝ), (0 : ℝ)))

/-- A concrete counterexample to the benchmark's universal textbook upper bound. -/
@[category test, AMS 5 52]
theorem green72_bound_counterexample :
    ¬ (Green72.AllowedSetSize 1 1 ≤ (1 - 1) * 1) := by
  have hb : BddAbove {r | ∃ s : Finset (ℕ × ℕ), r = s.card ∧ Green72.AllowedSet 1 1 s} := by
    refine ⟨1, ?_⟩
    rintro r ⟨s, rfl, hs⟩
    have hsub : s ⊆ {(0, 0)} := by
      intro i hi
      have h := hs.is_bounded i hi
      rcases i with ⟨x, y⟩
      have hx : x = 0 := by omega
      have hy : y = 0 := by omega
      simp [hx, hy]
    simpa using Finset.card_le_card hsub
  have hm : 1 ∈ {r | ∃ s : Finset (ℕ × ℕ), r = s.card ∧ Green72.AllowedSet 1 1 s} :=
    ⟨{(0, 0)}, by simp, green72_singleton_allowed⟩
  have hp : 1 ≤ Green72.AllowedSetSize 1 1 := le_csSup hb hm
  omega

/-- Algebraic bridge for the sum/product transcendence problem. -/
@[category test, AMS 11]
theorem transcendental_sum_or_product {a b : ℝ} (ha : Transcendental ℚ a) :
    Transcendental ℚ (a + b) ∨ Transcendental ℚ (a * b) := by
  classical
  by_contra h
  have hs : IsAlgebraic ℚ (a + b) := Classical.not_not.mp (not_or.mp h).1
  have hp : IsAlgebraic ℚ (a * b) := Classical.not_not.mp (not_or.mp h).2
  have heq : (a + b) ^ 2 - (4 : ℚ) • (a * b) = (a - b) ^ 2 := by
    norm_num [Algebra.smul_def]
    ring
  have hd2 : IsAlgebraic ℚ ((a - b) ^ 2) := by
    rw [← heq]
    exact (hs.pow 2).sub (hp.smul (4 : ℚ))
  have hd : IsAlgebraic ℚ (a - b) := IsAlgebraic.of_pow (by decide : 0 < (2 : ℕ)) hd2
  have heq2 : (1 / 2 : ℚ) • ((a + b) + (a - b)) = a := by
    norm_num [Algebra.smul_def]
    ring
  apply ha
  rw [← heq2]
  exact (hs.add hd).smul (1 / 2 : ℚ)

/-- The remaining premise is explicit; this is not the unconditional benchmark theorem. -/
@[category test, AMS 11]
theorem pi_exp_sum_or_product_of_transcendental_pi (hpi : Transcendental ℚ Real.pi) :
    Transcendental ℚ (Real.pi + Real.exp 1) ∨
      Transcendental ℚ (Real.pi * Real.exp 1) :=
  transcendental_sum_or_product hpi

end AegisBench

#print axioms PellNumbers.pellNumber_sq_add_pellNumber_succ_sq
#print axioms PellNumbers.coe_pellNumber_eq
#print axioms AegisBench.green72_bound_counterexample

#print axioms AegisBench.transcendental_sum_or_product
#print axioms AegisBench.pi_exp_sum_or_product_of_transcendental_pi

namespace AegisBench.Vega

/-- Edge order follows the variable indices in the published recurrence. -/
def edges : List (Fin 4 × Fin 4) := [(0, 1), (0, 2), (0, 3), (1, 2)]

def satisfies (a : Fin 4 → Bool) : Prop :=
  ∀ e ∈ edges, a e.1 ≠ a e.2

def forward (v : Fin 4) : ℤ := (edges.filter (fun e => e.1 == v)).length

def backward (v : Fin 4) : ℤ := (edges.filter (fun e => e.2 == v)).length

structure State where
  i : ℕ
  s : ℕ
  r : ℤ
  t : ℤ
  deriving DecidableEq

/-- Transcription of the two transitions in P versus NP note v10, Theorem 2. -/
def step (st : State) (v : Fin 4) (b : Bool) : State :=
  if b then
    ⟨st.i + 1, st.s + 1, st.r + forward v, st.t - backward v⟩
  else
    ⟨st.i + 1, st.s, st.r - backward v, st.t + forward v⟩

def run (a : Fin 4 → Bool) : State :=
  (List.finRange 4).foldl (fun st v => step st v (a v)) ⟨0, 0, 0, 0⟩

def accepts (st : State) (k : ℕ) : Prop :=
  st.i = 4 ∧ 0 < st.s ∧ st.s ≤ k ∧ st.r = 0 ∧ st.t = 0

instance (st : State) (k : ℕ) : Decidable (accepts st k) :=
  by unfold accepts; infer_instance

def witness (v : Fin 4) : Bool := v == 1 || v == 2

/-- Exhaustive finite kernel computation: the XOR triangle has no solution. -/
theorem formula_unsatisfiable : ¬ ∃ a : Fin 4 → Bool, satisfies a := by
  unfold satisfies edges
  decide

/-- An actual path through the published recurrence reaches its accepting state. -/
theorem recurrence_accepts : run witness = ⟨4, 2, 0, 0⟩ := by
  decide

/-- The formalized recurrence accepts a genuinely unsatisfiable instance at k = 2. -/
theorem bfs_false_positive :
    accepts (run witness) 2 ∧ ¬ ∃ a : Fin 4 → Bool, satisfies a := by
  constructor
  · rw [recurrence_accepts]
    decide
  · exact formula_unsatisfiable

/-- A positive multiplicative increase does not supply an additive margin of one.
This refutes the abstract inference, not the prime-specific RH inequality. -/
theorem missing_margin_counterexample :
    ∃ A E : ℝ, 0 < A ∧ 1 < E ∧ A < E * A ∧ ¬ (1 + A < E * A) := by
  refine ⟨1, 3 / 2, ?_⟩
  norm_num

end AegisBench.Vega

#print axioms AegisBench.Vega.bfs_false_positive
#print axioms AegisBench.Vega.missing_margin_counterexample

namespace AegisBench.Vega

/-- Per-clause contribution after both endpoints have been processed. -/
def edgeR (e : Bool × Bool) : ℤ :=
  (if e.1 then 1 else 0) - (if e.2 then 0 else 1)

def balance (es : List (Bool × Bool)) : ℤ := (es.map edgeR).sum

/-- Global balance only equates the counts of the two kinds of violated clause. -/
theorem balance_counts (es : List (Bool × Bool)) :
    balance es = (es.countP (fun e => e.1 && e.2) : ℤ) -
      (es.countP (fun e => !e.1 && !e.2) : ℤ) := by
  induction es with
  | nil => simp [balance]
  | cons e es ih =>
    rcases e with ⟨u, v⟩
    cases u <;> cases v <;>
      simp_all [balance, edgeR, List.countP_cons] <;> omega

/-- Explicit binding to the already audited four-variable state machine. -/
theorem run_balance_binding : ∀ a : Fin 4 → Bool,
    (run a).r = balance (edges.map (fun e => (a e.1, a e.2))) ∧
    (run a).t = -balance (edges.map (fun e => (a e.1, a e.2))) := by
  decide

/-- Clause-by-clause validation prevents cancellation of different violations. -/
def checkClauses (es : List (Bool × Bool)) : Bool :=
  es.all (fun e => decide (e.1 ≠ e.2))

theorem checkClauses_correct (es : List (Bool × Bool)) :
    checkClauses es = true ↔ ∀ e ∈ es, e.1 ≠ e.2 := by
  simp [checkClauses, List.all_eq_true]

/-- Exact replacement for the invalid missing-margin inference. -/
theorem reciprocal_margin_iff {A E : ℝ} (hE : 1 < E) :
    1 / (E - 1) < A ↔ 1 + A < E * A := by
  rw [div_lt_iff₀ (by linarith : 0 < E - 1)]
  constructor <;> intro h <;> nlinarith

end AegisBench.Vega

#print axioms AegisBench.Vega.balance_counts
#print axioms AegisBench.Vega.run_balance_binding
#print axioms AegisBench.Vega.checkClauses_correct
#print axioms AegisBench.Vega.reciprocal_margin_iff


namespace AegisBench.Vega

/-- Number of true variables, including variables not incident to any clause. -/
def trueCount {n : ℕ} (a : Fin n → Bool) : ℕ :=
  (Finset.univ.filter (fun v => a v = true)).card

/-- Full witness validation: each XOR clause and the at-most-k bound. -/
def checkAssignment {n : ℕ} (es : List (Fin n × Fin n))
    (k : ℕ) (a : Fin n → Bool) : Bool :=
  es.all (fun e => decide (a e.1 ≠ a e.2)) && decide (trueCount a ≤ k)

def ValidAssignment {n : ℕ} (es : List (Fin n × Fin n))
    (k : ℕ) (a : Fin n → Bool) : Prop :=
  (∀ e ∈ es, a e.1 ≠ a e.2) ∧ trueCount a ≤ k

theorem checkAssignment_correct {n : ℕ} (es : List (Fin n × Fin n))
    (k : ℕ) (a : Fin n → Bool) :
    checkAssignment es k a = true ↔ ValidAssignment es k a := by
  simp [checkAssignment, ValidAssignment, List.all_eq_true]

/-- Reference decision procedure enumerating all 2^n assignments.
This is deliberately an exhaustive baseline, with no polynomial-time claim. -/
def solve {n : ℕ} (es : List (Fin n × Fin n)) (k : ℕ) : Bool :=
  decide ((Finset.univ.filter (fun a : Fin n → Bool =>
    checkAssignment es k a = true)).Nonempty)

/-- Soundness and completeness for any variable count, clause list and bound. -/
theorem solve_correct {n : ℕ} (es : List (Fin n × Fin n)) (k : ℕ) :
    solve es k = true ↔ ∃ a : Fin n → Bool, ValidAssignment es k a := by
  simp [solve, Finset.filter_nonempty_iff, checkAssignment_correct]

/-- The complete reference solver rejects the input accepted by Vega's recurrence. -/
theorem solve_rejects_vega : solve edges 2 = false := by
  decide

/-- Empty instances, zero budgets and ordinary satisfiable instances are covered. -/
theorem solve_boundary_examples :
    solve ([] : List (Fin 0 × Fin 0)) 0 = true ∧
    solve ([(0, 1)] : List (Fin 2 × Fin 2)) 0 = false ∧
    solve ([(0, 1)] : List (Fin 2 × Fin 2)) 1 = true := by
  decide

end AegisBench.Vega

#print axioms AegisBench.Vega.solve_correct
#print axioms AegisBench.Vega.solve_rejects_vega
#print axioms AegisBench.Vega.solve_boundary_examples

namespace AegisBench.Vega

/-- Incidence contribution of one edge to one vertex's terminal r increment. -/
def incidenceR {n : ℕ} (a : Fin n → Bool) (v : Fin n) (e : Fin n × Fin n) : ℤ :=
  (if e.1 = v then (if a v then 1 else 0) else 0) -
    (if e.2 = v then (if a v then 0 else 1) else 0)

/-- Algebraic terminal sum; this definition is independent of an operational fold. -/
def vertexSumR {n : ℕ} (es : List (Fin n × Fin n)) (a : Fin n → Bool) : ℤ :=
  ∑ v : Fin n, (es.map (incidenceR a v)).sum

theorem incidenceR_sum {n : ℕ} (a : Fin n → Bool) (e : Fin n × Fin n) :
    (∑ v : Fin n, incidenceR a v e) = edgeR (a e.1, a e.2) := by
  simp [incidenceR, Finset.sum_sub_distrib, edgeR]

/-- Every edge's two endpoint increments contribute exactly its clause balance. -/
theorem vertexSumR_balance {n : ℕ} (es : List (Fin n × Fin n)) (a : Fin n → Bool) :
    vertexSumR es a = balance (es.map (fun e => (a e.1, a e.2))) := by
  induction es with
  | nil => simp [vertexSumR, balance]
  | cons e es ih =>
    simp only [vertexSumR, List.map_cons, List.sum_cons, Finset.sum_add_distrib] at *
    rw [incidenceR_sum, ih]
    simp [balance]

/-- The incidence sum agrees with the manuscript's forward/backward degree increments. -/
theorem vertexSumR_degrees {n : ℕ} (es : List (Fin n × Fin n)) (a : Fin n → Bool) :
    vertexSumR es a = ∑ v : Fin n,
      if a v then ((es.filter (fun e => e.1 == v)).length : ℤ)
      else -((es.filter (fun e => e.2 == v)).length : ℤ) := by
  unfold vertexSumR
  apply Finset.sum_congr rfl
  intro v hv
  induction es with
  | nil => simp
  | cons e es ih =>
    by_cases h₁ : e.1 = v <;> by_cases h₂ : e.2 = v <;>
      cases ha : a v <;> simp_all [incidenceR] <;> omega

/-- For every finite graph, zero terminal balance can hide equal counts of 11 and 00. -/
theorem degree_balance_counts {n : ℕ} (es : List (Fin n × Fin n)) (a : Fin n → Bool) :
    (∑ v : Fin n,
      if a v then ((es.filter (fun e => e.1 == v)).length : ℤ)
      else -((es.filter (fun e => e.2 == v)).length : ℤ)) =
    ((es.map (fun e => (a e.1, a e.2))).countP (fun e => e.1 && e.2) : ℤ) -
      ((es.map (fun e => (a e.1, a e.2))).countP (fun e => !e.1 && !e.2) : ℤ) := by
  rw [← vertexSumR_degrees, vertexSumR_balance, balance_counts]

end AegisBench.Vega

#print axioms AegisBench.Vega.degree_balance_counts
