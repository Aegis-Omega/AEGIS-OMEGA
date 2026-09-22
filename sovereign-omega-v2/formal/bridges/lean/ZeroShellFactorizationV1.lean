import ZeroHeightShellMassV1

/-!
AEGIS Ω — multiplicity-weighted height-shell factorization v1.

This lane proves only a pointwise-to-shell factorization. The already verified
finite shell norm-mass of the multiplicity-weighted Mellin zero summand is
bounded by the product of two separate quantities:

  shellMass(f,n) ≤ weightedCount(n) * B(n)

where `weightedCount(n)` is the multiplicity-weighted number of nontrivial
zeros in the `n`-th canonical height shell and `B(n)` is any supplied uniform
bound on `‖mellin f rho‖` over that shell.

The lane does not bound the weighted zero count, does not prove any Mellin
decay estimate, and does not produce the quadratic shell certificate. Those
quantitative inputs remain separate open obligations.

MULTIPLICITY_WEIGHTED_SHELL_FACTORIZATION_ONLY
WEIGHTED_ZERO_COUNT_BOUND_OPEN
UNIFORM_MELLIN_DECAY_BOUND_OPEN
ACTUAL_QUADRATIC_SHELL_BOUND_OPEN
WEIL_CLASS_SHELL_MASS_SUMMABILITY_OPEN
EXPLICIT_FORMULA_OPEN
CRITICAL_LINE_RE_HALF_OPEN
RH_EQUIVALENCE_OPEN
-/

open Set Filter Topology
open Complex

noncomputable section

/-- Multiplicity-weighted number of nontrivial zeros in the `n`-th canonical
height shell. The expression is a `tsum` over a finite subtype; finiteness is
`zero_height_shell_finite_v1`. -/
def WeightedZeroShellCountV1 (n : ℕ) : ℝ :=
  ∑' rho : ZeroHeightShellSetV1 n, (analyticOrderNatAt riemannZeta rho.1.1 : ℝ)

/-- Certificate that `B n` bounds the Mellin transform uniformly over the
`n`-th shell. This is a definition, not an existence theorem. -/
def HasUniformMellinShellBoundV1 (f : ℝ → ℂ) (B : ℕ → ℝ) : Prop :=
  ∀ n : ℕ, ∀ rho : ZeroHeightShellSetV1 n, ‖mellin f rho.1.1‖ ≤ B n

/-- Shell factorization: under a supplied uniform Mellin shell bound, each
finite shell norm-mass is at most the multiplicity-weighted shell count times
that bound. This theorem does not construct the bound. -/
theorem zero_height_shell_mass_le_weighted_count_mul_v1
    {f : ℝ → ℂ} {B : ℕ → ℝ} (hB : HasUniformMellinShellBoundV1 f B) (n : ℕ) :
    ZeroHeightShellMassV1 f n ≤ WeightedZeroShellCountV1 n * B n := by
  let _ : Fintype (ZeroHeightShellSetV1 n) :=
    (zero_height_shell_finite_v1 n).fintype
  unfold ZeroHeightShellMassV1 WeightedZeroShellCountV1
  rw [tsum_fintype, tsum_fintype, Finset.sum_mul]
  apply Finset.sum_le_sum
  intro rho _
  have hnorm :
      ‖WeilZeroIndexSummandV1 f rho.1‖ =
        (analyticOrderNatAt riemannZeta rho.1.1 : ℝ) * ‖mellin f rho.1.1‖ := by
    unfold WeilZeroIndexSummandV1
    rw [norm_mul, Complex.norm_natCast]
  rw [hnorm]
  exact mul_le_mul_of_nonneg_left (hB n rho) (Nat.cast_nonneg _)

#check WeightedZeroShellCountV1
#check HasUniformMellinShellBoundV1
#check zero_height_shell_mass_le_weighted_count_mul_v1
#print axioms zero_height_shell_mass_le_weighted_count_mul_v1
