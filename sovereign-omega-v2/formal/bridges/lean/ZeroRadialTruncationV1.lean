/-!
AEGIS Ω — finite radial zero truncation v1.

This file is a proof fragment compiled immediately after the exact pinned
`ZeroMultiplicityV1.lean` parent source. It uses the verified pointwise
multiplicity weight and Mathlib's compact-zero finiteness to construct finite
radial partial sums.

Radial truncation is an internal exhaustion device only. This lane does not
claim that radial ordering is the summation convention used by Bombieri/Weil,
and it proves no infinite-limit convergence.

FINITE_RADIAL_ZERO_SUM_ONLY
SUMMATION_CONVENTION_EQ_BOMBIERI_OPEN
TRUNCATED_LIMIT_CONVERGENCE_OPEN
EXPLICIT_FORMULA_THEOREM_OPEN
RH_EQUIVALENCE_OPEN
-/

open Set

/-- Nontrivial zeta-zero indices whose complex norm is at most `R`. -/
def RiemannRadialZeroSetV1 (R : ℝ) : Set RiemannNontrivialZeroIndexV1 :=
  { rho | rho.1 ∈ Metric.closedBall (0 : ℂ) R }

/-- The radial set is finite because its values inject into the intersection of
    a compact closed ball with Mathlib's discrete Riemann-zeta zero set. -/
theorem riemann_radial_zero_set_finite_v1 (R : ℝ) :
    (RiemannRadialZeroSetV1 R).Finite := by
  let valEmbedding : RiemannNontrivialZeroIndexV1 ↪ ℂ :=
    ⟨Subtype.val, Subtype.val_injective⟩
  have hfiniteComplex :
      (Metric.closedBall (0 : ℂ) R ∩ riemannZetaZeros).Finite :=
    (isCompact_closedBall (0 : ℂ) R).inter_riemannZetaZeros_finite
  have hfinitePreimage := Set.Finite.preimage_embedding valEmbedding hfiniteComplex
  refine hfinitePreimage.subset ?_
  intro rho hrho
  exact ⟨hrho, nontrivial_zero_mem_mathlib_zero_set_v1 rho⟩

/-- Canonical finite radial index set. -/
noncomputable def RiemannRadialZeroFinsetV1 (R : ℝ) :
    Finset RiemannNontrivialZeroIndexV1 :=
  (riemann_radial_zero_set_finite_v1 R).toFinset

/-- Membership in the finite representation exactly matches radial-set membership. -/
theorem mem_riemann_radial_zero_finset_v1
    {R : ℝ} {rho : RiemannNontrivialZeroIndexV1} :
    rho ∈ RiemannRadialZeroFinsetV1 R ↔ rho ∈ RiemannRadialZeroSetV1 R := by
  simp [RiemannRadialZeroFinsetV1]

/-- Every nontrivial zero enters the radial exhaustion by radius equal to its norm. -/
theorem nontrivial_zero_mem_radial_at_norm_v1
    (rho : RiemannNontrivialZeroIndexV1) :
    rho ∈ RiemannRadialZeroFinsetV1 ‖rho.1‖ := by
  rw [mem_riemann_radial_zero_finset_v1]
  simp [RiemannRadialZeroSetV1, Metric.mem_closedBall]

/-- Radial index sets are monotone in the radius. -/
theorem riemann_radial_zero_finset_mono_v1
    {R S : ℝ} (hRS : R ≤ S) :
    RiemannRadialZeroFinsetV1 R ⊆ RiemannRadialZeroFinsetV1 S := by
  intro rho hrho
  rw [mem_riemann_radial_zero_finset_v1] at hrho ⊢
  change dist rho.1 0 ≤ R at hrho
  change dist rho.1 0 ≤ S
  exact hrho.trans hRS

/-- Finite, multiplicity-safe Mellin zero-side partial sum at radial cutoff `R`. -/
noncomputable def WeilRadialZeroSumV1 (f : ℝ → ℂ) (R : ℝ) : ℂ :=
  ∑ rho in RiemannRadialZeroFinsetV1 R, WeilZeroSummandV1 f rho

#check RiemannRadialZeroSetV1
#check riemann_radial_zero_set_finite_v1
#check RiemannRadialZeroFinsetV1
#check mem_riemann_radial_zero_finset_v1
#check nontrivial_zero_mem_radial_at_norm_v1
#check riemann_radial_zero_finset_mono_v1
#check WeilRadialZeroSumV1

#print axioms riemann_radial_zero_set_finite_v1
#print axioms mem_riemann_radial_zero_finset_v1
#print axioms nontrivial_zero_mem_radial_at_norm_v1
#print axioms riemann_radial_zero_finset_mono_v1
