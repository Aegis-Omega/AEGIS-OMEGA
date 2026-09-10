import Mathlib.Analysis.MellinTransform
import Mathlib.NumberTheory.LSeries.RiemannZeta

/-!
AEGIS Ω — Bombieri/Weil target capability probe v1.

This file does not state or prove the Bombieri–Weil positivity criterion and
proves neither the Riemann Hypothesis nor its negation. It machine-binds the
concrete Mathlib primitives required for the next semantic bridge:

* complex-valued smooth compactly-supported test functions on `(0, ∞)`;
* Mathlib's Mellin transform;
* Mathlib's analytically-continued `riemannZeta` and `RiemannHypothesis` target;
* the completed-zeta functional symmetry already present in Mathlib.
-/

open Set
open Complex
open scoped ContDiff

noncomputable section

/-- Complex-valued `C_c^∞(0,∞)` test functions, represented on `ℝ` with
    topological support contained in the positive half-line. -/
def BombieriTestFunctionV1 :=
  { f : ℝ → ℂ // ContDiff ℝ ∞ f ∧ HasCompactSupport f ∧ tsupport f ⊆ Set.Ioi 0 }

/-- The Mellin transform used by the concrete Bombieri/Weil target lane. -/
def BombieriMellinV1 (f : BombieriTestFunctionV1) : ℂ → ℂ :=
  mellin f.1

theorem bombieri_test_contDiff_v1 (f : BombieriTestFunctionV1) :
    ContDiff ℝ ∞ f.1 :=
  f.2.1

theorem bombieri_test_hasCompactSupport_v1 (f : BombieriTestFunctionV1) :
    HasCompactSupport f.1 :=
  f.2.2.1

theorem bombieri_test_tsupport_positive_v1 (f : BombieriTestFunctionV1) :
    tsupport f.1 ⊆ Set.Ioi 0 :=
  f.2.2.2

theorem bombieri_mellin_eq_mathlib_mellin_v1
    (f : BombieriTestFunctionV1) (s : ℂ) :
    BombieriMellinV1 f s = mellin f.1 s :=
  rfl

/-- Compact support away from zero makes the Mellin integral convergent for
    every complex exponent. -/
theorem bombieri_mellin_convergent_v1 (f : BombieriTestFunctionV1) (s : ℂ) :
    MellinConvergent f.1 s := by
  rw [MellinConvergent]
  let g : ℝ → ℂ := fun t => (t : ℂ) ^ (s - 1) * f.1 t
  have hg_cont_on : ContinuousOn g (Set.Ioi 0) := by
    intro t ht
    exact
      (continuousAt_ofReal_cpow_const _ _ (Or.inr <| ne_of_gt ht)).continuousWithinAt.mul
        (bombieri_test_contDiff_v1 f).continuous.continuousAt.continuousWithinAt
  have hg_tsupport : tsupport g ⊆ Set.Ioi 0 := by
    exact (tsupport_mul_subset_right _ _).trans (bombieri_test_tsupport_positive_v1 f)
  have hg_cont : Continuous g :=
    hg_cont_on.continuous_of_tsupport_subset isOpen_Ioi hg_tsupport
  have hg_compact : HasCompactSupport g := by
    exact (bombieri_test_hasCompactSupport_v1 f).mul_left
  simpa only [g, smul_eq_mul] using
    (hg_cont.integrable_of_hasCompactSupport hg_compact).integrableOn

/-- Exact unfolding of the pinned Mathlib RH target. -/
theorem pinned_mathlib_riemann_hypothesis_unfold_v1 :
    RiemannHypothesis ↔
      ∀ (s : ℂ) (_ : riemannZeta s = 0)
        (_ : ¬ ∃ n : ℕ, s = -2 * (n + 1)) (_ : s ≠ 1), s.re = 1 / 2 := by
  rfl

/-- Probe the completed-zeta functional symmetry used by explicit-formula routes. -/
theorem pinned_completed_zeta_symmetry_v1 (s : ℂ) :
    completedRiemannZeta₀ (1 - s) = completedRiemannZeta₀ s :=
  completedRiemannZeta₀_one_sub s

#print axioms bombieri_test_contDiff_v1
#print axioms bombieri_test_hasCompactSupport_v1
#print axioms bombieri_test_tsupport_positive_v1
#print axioms bombieri_mellin_eq_mathlib_mellin_v1
#print axioms bombieri_mellin_convergent_v1
#print axioms pinned_mathlib_riemann_hypothesis_unfold_v1
#print axioms pinned_completed_zeta_symmetry_v1
