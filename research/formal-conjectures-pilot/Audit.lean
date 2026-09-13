/-
Copyright 2026 AEGIS Omega contributors.
Licensed under the Apache License, Version 2.0.
-/
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

end AegisBench

#print axioms PellNumbers.pellNumber_sq_add_pellNumber_succ_sq
#print axioms PellNumbers.coe_pellNumber_eq
#print axioms AegisBench.green72_bound_counterexample
