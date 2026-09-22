import WeilArchTailIntegralV1

/-!
AEGIS Ω — the tail weight carries the sign: dual of the weighted Gram integral.

`weil_arch_weighted_tail_quadratic_nonnegative_v1` concludes
`0 ≤ WeilArchWeightedTailQuadraticV1 I L A B u w` from a NONNEGATIVE spectral
weight on `Icc A B`.  This module proves the exact dual: a NONPOSITIVE weight
on `Icc A B` forces `WeilArchWeightedTailQuadraticV1 I L A B u w ≤ 0`, by the
same fixed-T Gram positivity and the same nonresonance side condition.

CONSEQUENCE.  The sign of the conclusion is carried entirely by the weight
hypothesis, not by the Gram/PSD structure.  `hw` is therefore not a removable
technical assumption: on any window where the weight is nonpositive the
conclusion of the original theorem is the reverse inequality, and on a window
where the weight changes sign neither bound is available from this route.
Extending the tail theorem to a range on which the weight is negative is not
a strengthening of it; it contradicts this dual.

WHAT THIS DOES NOT DO.  It says nothing about the actual zeta Archimedean
weight `Re (digamma (1/4 + iT/2)) - log π`.  Deciding the sign of that weight
is a separate obligation, recorded as `ARCH_WEIGHT_SIGN_LOW_RANGE_OPEN`:
Mathlib at the pinned commit exposes `digamma` only through `digamma_zero`,
`digamma_one`, `digamma_one_half`, `digamma_apply_add_one` and
`meromorphic_digamma`; it has no value at `1/4`, no digamma on a real
argument, and no monotonicity, so the sign at low `T` is not derivable here.
Closing it needs (a) a real/complex bridge for `logDeriv Gamma`, and
(b) monotonicity of the derivative from `Real.convexOn_log_Gamma`.

No explicit-formula identity, Archimedean-term identification, global Weil
positivity, RH claim, repository admission, merge, or authority effect
follows.  AUTHORITY_EFFECT = NONE.
-/

open scoped BigOperators

set_option autoImplicit false

noncomputable section

/-- **Dual of the tail theorem.**  A nonpositive spectral weight reverses the
conclusion: the weighted Gram integral is nonpositive, under exactly the
hypotheses of `weil_arch_weighted_tail_quadratic_nonnegative_v1` with `hw`
replaced by its dual. -/
theorem weil_arch_weighted_tail_quadratic_nonpositive_v1
    (I : Finset ℤ) (L A B : ℝ) (u : ℤ → ℝ) (w : ℝ → ℝ)
    (hAB : A ≤ B)
    (hL : 0 < L)
    (hw : ∀ T ∈ Set.Icc A B, w T ≤ 0)
    (hden : ∀ T ∈ Set.Icc A B, ∀ n ∈ I,
      T ^ 2 - (WeilArchRhoV1 L * (n : ℝ)) ^ 2 ≠ 0) :
    WeilArchWeightedTailQuadraticV1 I L A B u w ≤ 0 := by
  unfold WeilArchWeightedTailQuadraticV1
  have key : (0:ℝ) ≤ ∫ T in A..B, -(w T * WeilArchFiniteQuadraticV1 I L T u) := by
    apply intervalIntegral.integral_nonneg hAB
    intro T hT
    have hQ : 0 ≤ WeilArchFiniteQuadraticV1 I L T u :=
      weil_arch_finite_quadratic_nonnegative_v1 I L T u hL
        (fun n hn => hden T hT n hn)
    have hwT : w T ≤ 0 := hw T hT
    have : w T * WeilArchFiniteQuadraticV1 I L T u ≤ 0 := mul_nonpos_of_nonpos_of_nonneg hwT hQ
    linarith
  rw [intervalIntegral.integral_neg] at key
  linarith

/-- CONTROL (the weight hypothesis is genuinely violable): a constant negative
weight fails `hw` on a nondegenerate window, so the original theorem's
hypothesis is not automatic. -/
theorem arch_tail_weight_hypothesis_violable_v1 :
    ¬ (∀ T ∈ Set.Icc (0:ℝ) 1, (0:ℝ) ≤ (fun _ : ℝ => (-1:ℝ)) T) := by
  intro h
  have := h 0 (by constructor <;> norm_num)
  norm_num at this

/-- CONTROL (both branches are inhabited): the zero weight satisfies the
nonnegative and the nonpositive hypothesis simultaneously, so neither branch
is vacuous. -/
theorem arch_tail_weight_zero_satisfies_both_v1 (A B : ℝ) :
    (∀ T ∈ Set.Icc A B, (0:ℝ) ≤ (fun _ : ℝ => (0:ℝ)) T) ∧
    (∀ T ∈ Set.Icc A B, (fun _ : ℝ => (0:ℝ)) T ≤ 0) :=
  ⟨fun _ _ => le_refl 0, fun _ _ => le_refl 0⟩

#print axioms weil_arch_weighted_tail_quadratic_nonpositive_v1
#print axioms arch_tail_weight_hypothesis_violable_v1
#print axioms arch_tail_weight_zero_satisfies_both_v1
