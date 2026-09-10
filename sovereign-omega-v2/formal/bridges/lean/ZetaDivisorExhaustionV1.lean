import Mathlib.NumberTheory.LSeries.RiemannZeta
import Mathlib.Topology.MetricSpace.ProperSpace

/-!
AEGIS Ω — zeta-divisor exhaustion geometry v1.

This file proves only the geometric exhaustion needed to pass from local compact
zeta-divisor ledgers toward a global limiting problem. The region indexed by
`(r, k)` is a closed ball about `0` with an open ball around the pole `1`
removed. Every complex point distinct from `1` lies in some such region.

This does not yet prove that every zeta zero belongs to the divisor support
finset, does not prove convergence of any global zero sum, and does not prove
the explicit formula or the Riemann Hypothesis.

DIVISOR_SUPPORT_MEMBERSHIP_BRIDGE_OPEN
GLOBAL_ZERO_SUM_CONVERGENCE_OPEN
EXPLICIT_FORMULA_IDENTITY_OPEN
-/

open Set
open Complex

noncomputable section

/-- Compact exhaustion grid: radius grows with `r`, while the deleted
    neighbourhood of the pole may shrink with `k`. -/
def ZetaExhaustionRegionV1 (r k : ℕ) : Set ℂ :=
  Metric.closedBall 0 (r : ℝ) \ Metric.ball 1 (1 / (k + 1 : ℝ))

/-- Structural shape matching the admissible compact regions used by the
    finite zeta-divisor ledger. -/
def ZetaExhaustionAdmissibleShapeV1 (K : Set ℂ) : Prop :=
  IsCompact K ∧ K ⊆ ({1}ᶜ : Set ℂ)

/-- Standard nontrivial-zero predicate, repeated here only to keep this
    geometric lane independently compilable. -/
def IsNontrivialZetaZeroShapeV1 (s : ℂ) : Prop :=
  riemannZeta s = 0 ∧
  (¬ ∃ n : ℕ, s = -2 * (n + 1)) ∧
  s ≠ 1

theorem zeta_exhaustion_exclusion_pos_v1 (k : ℕ) :
    0 < (1 / (k + 1 : ℝ)) := by
  positivity

/-- Every exhaustion region is compact. -/
theorem zeta_exhaustion_region_compact_v1 (r k : ℕ) :
    IsCompact (ZetaExhaustionRegionV1 r k) := by
  exact (isCompact_closedBall (0 : ℂ) (r : ℝ)).diff Metric.isOpen_ball

/-- The deleted ball ensures that the pole `1` is never in an exhaustion region. -/
theorem zeta_exhaustion_region_avoids_one_v1 (r k : ℕ) :
    ZetaExhaustionRegionV1 r k ⊆ ({1}ᶜ : Set ℂ) := by
  intro s hs
  change s ≠ 1
  intro h
  subst s
  exact hs.2 (Metric.mem_ball_self (zeta_exhaustion_exclusion_pos_v1 k))

/-- Therefore each grid region has exactly the compact/pole-avoiding shape
    required by the local divisor ledger. -/
theorem zeta_exhaustion_region_admissible_shape_v1 (r k : ℕ) :
    ZetaExhaustionAdmissibleShapeV1 (ZetaExhaustionRegionV1 r k) := by
  exact ⟨zeta_exhaustion_region_compact_v1 r k,
    zeta_exhaustion_region_avoids_one_v1 r k⟩

/-- Every complex point other than the pole occurs in some exhaustion region. -/
theorem zeta_exhaustion_covers_ne_one_v1 {s : ℂ} (hs : s ≠ 1) :
    ∃ r k : ℕ, s ∈ ZetaExhaustionRegionV1 r k := by
  obtain ⟨r, hr⟩ := exists_nat_gt ‖s‖
  obtain ⟨k, hk⟩ := exists_nat_one_div_lt (dist_pos.mpr hs)
  refine ⟨r, k, ?_⟩
  constructor
  · rw [Metric.mem_closedBall, dist_zero_right]
    exact le_of_lt hr
  · intro hball
    rw [Metric.mem_ball] at hball
    exact (not_lt_of_ge (le_of_lt hk)) hball

/-- In particular, every standard nontrivial zeta zero is geometrically covered.
    Membership in the divisor support is deliberately a later theorem. -/
theorem nontrivial_zeta_zero_covered_by_exhaustion_v1
    {s : ℂ} (hs : IsNontrivialZetaZeroShapeV1 s) :
    ∃ r k : ℕ, s ∈ ZetaExhaustionRegionV1 r k :=
  zeta_exhaustion_covers_ne_one_v1 hs.2.2

#check exists_nat_gt
#check exists_nat_one_div_lt
#check isCompact_closedBall
#check Metric.isOpen_ball
#check zeta_exhaustion_region_compact_v1
#check zeta_exhaustion_region_avoids_one_v1
#check zeta_exhaustion_covers_ne_one_v1
#check nontrivial_zeta_zero_covered_by_exhaustion_v1

#print axioms zeta_exhaustion_exclusion_pos_v1
#print axioms zeta_exhaustion_region_compact_v1
#print axioms zeta_exhaustion_region_avoids_one_v1
#print axioms zeta_exhaustion_region_admissible_shape_v1
#print axioms zeta_exhaustion_covers_ne_one_v1
#print axioms nontrivial_zeta_zero_covered_by_exhaustion_v1
