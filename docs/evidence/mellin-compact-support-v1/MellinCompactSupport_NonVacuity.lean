import Mathlib.Analysis.MellinTransform

open MeasureTheory Set Filter Asymptotics TopologicalSpace
open Real
open Complex hiding exp log
open scoped Topology

/-- A continuous tent supported on `Icc 1 3`, nonzero at `2`. -/
noncomputable def witness : ℝ → ℂ := fun t => ((max 0 (1 - |t - 2|) : ℝ) : ℂ)

theorem witness_continuous : Continuous witness := by
  unfold witness; fun_prop

theorem witness_zero_outside : ∀ x ∉ Icc (1 : ℝ) 3, witness x = 0 := by
  intro x hx
  simp only [mem_Icc, not_and_or, not_le] at hx
  have : 1 - |x - 2| ≤ 0 := by
    rcases hx with h | h
    · rw [abs_sub_comm, abs_of_nonneg (by linarith)]; linarith
    · rw [abs_of_nonneg (by linarith)]; linarith
  simp [witness, max_eq_left this]

theorem witness_hasCompactSupport : HasCompactSupport witness :=
  HasCompactSupport.intro isCompact_Icc witness_zero_outside

theorem witness_tsupport : tsupport witness ⊆ Ioi 0 := by
  have hsub : tsupport witness ⊆ Icc (1 : ℝ) 3 :=
    closure_minimal
      (fun x hx => by by_contra hc; exact hx (witness_zero_outside x hc)) isClosed_Icc
  intro x hx
  have hx' := hsub hx
  simp only [mem_Icc] at hx'
  simp only [mem_Ioi]
  linarith [hx'.1]

theorem witness_ne_zero : witness 2 ≠ 0 := by
  norm_num [witness]

-- The hypothesis set of `mellinConvergent_of_hasCompactSupport` is satisfiable
-- by a function that is not identically zero.
example (s : ℂ) : MellinConvergent witness s :=
  mellinConvergent_of_hasCompactSupport witness_continuous
    witness_hasCompactSupport witness_tsupport s
