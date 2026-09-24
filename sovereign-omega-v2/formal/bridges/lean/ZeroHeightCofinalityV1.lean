import ZeroHeightFiniteSumV1

/-!
AEGIS Ω — cofinality of finite nontrivial zeta-zero sets inside height truncations v1.

This lane proves only that the verified height-bounded finite carriers are monotone
in the height parameter and cofinal for finite sets of genuine nontrivial
Riemann-zeta zeros.

It does not prove any infinite sum exists, any height limit exists, any explicit
formula, the critical-line statement, or RH.

HEIGHT_FAMILY_COFINAL_ONLY
HEIGHT_LIMIT_EXISTENCE_OPEN
ZERO_SUM_CONVERGENCE_OPEN
EXPLICIT_FORMULA_OPEN
CRITICAL_LINE_RE_HALF_OPEN
RH_EQUIVALENCE_OPEN
-/

open Set Filter Topology
open Complex
open scoped BigOperators

noncomputable section

/-- Increasing the height threshold can only enlarge the finite carrier. -/
theorem nontrivial_zero_height_finset_mono_v1
    {T U : ℝ} (hTU : T ≤ U) :
    NontrivialZeroHeightFinsetV1 T ⊆ NontrivialZeroHeightFinsetV1 U := by
  intro s hs
  have hsT : s ∈ NontrivialZeroHeightSetV1 T := by
    simpa [NontrivialZeroHeightFinsetV1] using hs
  rcases hsT with ⟨hz, hnontrivial, him⟩
  have hsU : s ∈ NontrivialZeroHeightSetV1 U :=
    ⟨hz, hnontrivial, him.trans hTU⟩
  simpa [NontrivialZeroHeightFinsetV1] using hsU

/-- Every finite set consisting entirely of genuine nontrivial zeta zeros is
contained in one of the verified height truncations.

The witness height is the finite sum of the absolute imaginary parts. This
choice avoids any ordering or enumeration of the zero set. -/
theorem finite_nontrivial_zero_subset_height_v1
    (S : Finset ℂ)
    (hS : ∀ s ∈ S,
      riemannZeta s = 0 ∧
      (¬ ∃ n : ℕ, s = -(2 : ℂ) * (n + 1))) :
    ∃ T : ℝ, S ⊆ NontrivialZeroHeightFinsetV1 T := by
  classical
  let T : ℝ := ∑ s in S, |s.im|
  refine ⟨T, ?_⟩
  intro s hs
  have him : |s.im| ≤ T := by
    dsimp [T]
    exact Finset.single_le_sum (fun z _hz => abs_nonneg z.im) hs
  have hsSet : s ∈ NontrivialZeroHeightSetV1 T :=
    ⟨(hS s hs).1, (hS s hs).2, him⟩
  simpa [NontrivialZeroHeightFinsetV1] using hsSet

#check nontrivial_zero_height_finset_mono_v1
#check finite_nontrivial_zero_subset_height_v1
#print axioms nontrivial_zero_height_finset_mono_v1
#print axioms finite_nontrivial_zero_subset_height_v1
