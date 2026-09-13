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
