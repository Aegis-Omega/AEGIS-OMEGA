import WeilMellinInversionV1
import WeilAutocorrelationClosureV1
import Mathlib.Tactic

/-!
AEGIS Ω — Mellin endpoint aggregation for the Weil autocorrelation lane.

This module isolates the algebraic information-loss step at the two Mellin
endpoints.  It is deliberately narrower than the full autocorrelation Mellin
factorization proved mathematically in `WeilPairedHadamardIdentityV1.md`.

For endpoint values `a,b : ℂ`, the pole cross-aggregate

  a * conj b + b * conj a

is exactly twice the real part of one cross term.  Hence the aggregate loses
the complementary imaginary information: aggregate zero does not force
`a = 0` and `b = 0` separately.  The repository's legacy two-moment condition
is nevertheless sufficient to force this aggregate to vanish.

No explicit-formula identity, sign inequality, RH equivalence, admission, or
authority effect is asserted here.
-/

open Set MeasureTheory Complex
open scoped ComplexConjugate

set_option autoImplicit false

noncomputable section

/-- One oriented endpoint cross term. -/
def WeilEndpointCrossTermV1 (a b : ℂ) : ℂ :=
  a * conj b

/-- Symmetric endpoint aggregate seen by the autocorrelation pole term after
Mellin factorization. -/
def WeilEndpointPoleAggregateV1 (a b : ℂ) : ℂ :=
  WeilEndpointCrossTermV1 a b + WeilEndpointCrossTermV1 b a

/-- Swapping the two endpoint profiles conjugates the oriented cross term. -/
theorem weil_endpoint_cross_swap_eq_conj_v1 (a b : ℂ) :
    WeilEndpointCrossTermV1 b a = conj (WeilEndpointCrossTermV1 a b) := by
  simp [WeilEndpointCrossTermV1, mul_comm]

/-- The symmetric aggregate remembers only twice the real part of one cross
term.  This is the precise lossy projection. -/
theorem weil_endpoint_pole_aggregate_eq_two_re_v1 (a b : ℂ) :
    WeilEndpointPoleAggregateV1 a b =
      (((2 : ℝ) * (WeilEndpointCrossTermV1 a b).re : ℝ) : ℂ) := by
  rw [WeilEndpointPoleAggregateV1, weil_endpoint_cross_swap_eq_conj_v1]
  apply Complex.ext <;> simp

/-- If both endpoint profiles vanish, then their pole aggregate vanishes. -/
theorem weil_endpoint_pole_aggregate_zero_of_endpoints_zero_v1
    {a b : ℂ} (ha : a = 0) (hb : b = 0) :
    WeilEndpointPoleAggregateV1 a b = 0 := by
  simp [ha, hb, WeilEndpointPoleAggregateV1, WeilEndpointCrossTermV1]

/-- Concrete collision: two nonzero endpoint profiles can have zero aggregate. -/
theorem weil_endpoint_pole_aggregate_zero_collision_v1 :
    WeilEndpointPoleAggregateV1 (1 : ℂ) Complex.I = 0 := by
  simp [WeilEndpointPoleAggregateV1, WeilEndpointCrossTermV1]

/-- Therefore aggregate zero cannot recover the two endpoint profiles. -/
theorem weil_endpoint_pole_aggregate_zero_not_force_zero_profiles_v1 :
    ∃ a b : ℂ,
      a ≠ 0 ∧ b ≠ 0 ∧ WeilEndpointPoleAggregateV1 a b = 0 := by
  refine ⟨1, Complex.I, ?_, ?_, weil_endpoint_pole_aggregate_zero_collision_v1⟩
  · norm_num
  · simp

/-- The repository's first zero-moment integral is exactly the Mellin endpoint
at `s = 0`. -/
theorem weil_mellin_zero_eq_moment0_v1 (g : WeilCompactSmoothGV1) :
    mellin g.1 0 =
      ∫ x in Ioi (0 : ℝ), g.1 x / (x : ℂ) := by
  unfold mellin
  apply setIntegral_congr_fun measurableSet_Ioi
  intro x hx
  simp [Complex.cpow_neg_one, div_eq_mul_inv, mul_comm]

/-- The repository's second zero-moment integral is exactly the Mellin endpoint
at `s = 1`. -/
theorem weil_mellin_one_eq_moment1_v1 (g : WeilCompactSmoothGV1) :
    mellin g.1 1 =
      ∫ x in Ioi (0 : ℝ), g.1 x := by
  unfold mellin
  apply setIntegral_congr_fun measurableSet_Ioi
  intro x hx
  simp

/-- The existing two-moment condition is a sufficient (but, by the collision
above, algebraically non-minimal) condition for vanishing endpoint aggregate. -/
theorem weil_moment_conditions_endpoint_pole_aggregate_zero_v1
    (g : WeilCompactSmoothGV1) (hm : WeilMomentConditionsV1 g) :
    WeilEndpointPoleAggregateV1 (mellin g.1 0) (mellin g.1 1) = 0 := by
  rcases hm with ⟨hm0, hm1⟩
  have h0 : mellin g.1 0 = 0 :=
    (weil_mellin_zero_eq_moment0_v1 g).trans hm0
  have h1 : mellin g.1 1 = 0 :=
    (weil_mellin_one_eq_moment1_v1 g).trans hm1
  exact weil_endpoint_pole_aggregate_zero_of_endpoints_zero_v1 h0 h1

end
