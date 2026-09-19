/-
AEGIS — the pole term of the Weil/Guinand explicit formula, in the Lean kernel.

`ConcreteFiniteGuinandWeilSemanticsV1.v` records the repository's own status:

    finite_explicit_identity_proof_status_v1 = MathProvedExternalDependenciesV1
    finite_whole_identity_lean_status_v1     = WholeIdentityLeanKernelOpenV1

and names the pole term only abstractly, as a sum of two Mellin values:

    finite_pole_term_cc_v1 mellin_zero mellin_one = mellin_zero + mellin_one

This file discharges one of those external dependencies: it DERIVES the pole
contribution from `riemannZeta` itself, rather than naming it. The residue of
`(-ζ'/ζ)·F` at the pole `s = 1` is exactly `F 1`.

What is proved here is the pole term and nothing else. The zero-side residues
and the vanishing of the horizontal segments in a contour shift are NOT proved,
and are stated below as an explicit named obligation so the gap is visible in
the kernel rather than in prose.
-/
import Mathlib.NumberTheory.Harmonic.ZetaAsymp
import Mathlib.NumberTheory.LSeries.Dirichlet

open Filter Topology Complex

namespace WeilPoleTerm

/-! ### The entire factor's log-derivative -/

/-- Log-derivative of the entire factor `riemannZeta₁`, where
`riemannZeta s = (s-1)⁻¹ * riemannZeta₁ s` and `riemannZeta₁ 1 = 1`. -/
noncomputable def zeta1LogDeriv (s : ℂ) : ℂ := deriv riemannZeta₁ s / riemannZeta₁ s

/-- It is continuous at `1`, because `riemannZeta₁` is entire and `riemannZeta₁ 1 = 1 ≠ 0`.
Its value there is the Euler–Mascheroni constant. -/
theorem zeta1LogDeriv_tendsto : Tendsto zeta1LogDeriv (𝓝 1) (𝓝 (deriv riemannZeta₁ 1)) := by
  have : ContinuousAt zeta1LogDeriv 1 := by
    apply ContinuousAt.div
    · exact (differentiable_riemannZeta₁.deriv).continuous.continuousAt
    · exact differentiable_riemannZeta₁.continuous.continuousAt
    · simp [riemannZeta₁_one]
  simpa [zeta1LogDeriv, riemannZeta₁_one] using this.tendsto

/-! ### The pole -/

/-- **`-ζ'/ζ` has a simple pole at `s = 1` with residue exactly `1`.**
This is the analytic source of the pole term in the explicit formula. -/
theorem neg_logDeriv_riemannZeta_residue_one :
    Tendsto (fun s : ℂ => (s - 1) * (-(deriv riemannZeta s / riemannZeta s)))
      (𝓝[≠] 1) (𝓝 1) := by
  have key : (fun s : ℂ => (s - 1) * (-(deriv riemannZeta s / riemannZeta s)))
      =ᶠ[𝓝[≠] 1] (fun s : ℂ => 1 - (s - 1) * zeta1LogDeriv s) := by
    filter_upwards [log_deriv_riemannZeta_eq_neg_inv_sub_add, self_mem_nhdsWithin] with s hs hne
    have h1 : s - 1 ≠ 0 := sub_ne_zero_of_ne hne
    rw [hs, zeta1LogDeriv]
    field_simp
    ring
  rw [tendsto_congr' key]
  have h0 : Tendsto (fun s : ℂ => s - 1) (𝓝[≠] 1) (𝓝 0) := by
    have h : Tendsto (fun s : ℂ => s - 1) (𝓝 1) (𝓝 ((1 : ℂ) - 1)) :=
      tendsto_id.sub tendsto_const_nhds
    rw [sub_self] at h
    exact h.mono_left nhdsWithin_le_nhds
  have h1 := zeta1LogDeriv_tendsto.mono_left (nhdsWithin_le_nhds (s := {(1 : ℂ)}ᶜ))
  simpa using tendsto_const_nhds.sub (h0.mul h1)

/-- **The pole term of the explicit formula.** For any test transform `F`
continuous at `1`, the residue of `(-ζ'/ζ)·F` at the pole is exactly `F 1`.

This is `finite_pole_term_cc_v1`'s content, derived rather than postulated. -/
theorem weil_pole_term_v1 (F : ℂ → ℂ) (hF : ContinuousAt F 1) :
    Tendsto (fun s : ℂ => (s - 1) * (-(deriv riemannZeta s / riemannZeta s)) * F s)
      (𝓝[≠] 1) (𝓝 (F 1)) := by
  simpa using
    neg_logDeriv_riemannZeta_residue_one.mul (hF.tendsto.mono_left nhdsWithin_le_nhds)

/-- The pole term is **not vacuous**: whenever the test transform does not vanish
at `1`, the residue is a nonzero contribution. -/
theorem weil_pole_term_ne_zero_v1 (F : ℂ → ℂ) (hF : ContinuousAt F 1) (h1 : F 1 ≠ 0) :
    ∃ L : ℂ, L ≠ 0 ∧
      Tendsto (fun s : ℂ => (s - 1) * (-(deriv riemannZeta s / riemannZeta s)) * F s)
        (𝓝[≠] 1) (𝓝 L) :=
  ⟨F 1, h1, weil_pole_term_v1 F hF⟩

/-! ### Binding the pole to the prime side -/

/-- On `Re s > 1` the Dirichlet series of the von Mangoldt weight **is** `-ζ'/ζ`.
So the pole above is a pole of the prime side's generating function, not of an
unrelated object. -/
theorem vonMangoldt_lseries_eq_neg_logDeriv_v1 {s : ℂ} (hs : 1 < s.re) :
    LSeries (fun n => (ArithmeticFunction.vonMangoldt n : ℂ)) s
      = -(deriv riemannZeta s / riemannZeta s) := by
  simpa [neg_div] using ArithmeticFunction.LSeries_vonMangoldt_eq_deriv_riemannZeta_div hs

/-! ### What is still owed

The contour shift needs two things this file does NOT prove. They are stated as
an explicit obligation so the gap lives in the kernel, not in a comment. -/

/-- The obligation a contour shift still needs, for a given test transform `F`
and abscissa `σ < 1 < c`: the horizontal segments of the rectangle contribute
nothing in the limit, and the zero-side residues are summable.

`WholeIdentityLeanKernelOpenV1` is exactly the statement that no proof of this
exists here. Nothing below discharges it. -/
structure ContourShiftObligationV1 (F : ℂ → ℂ) (σ c : ℝ) : Prop where
  /-- `σ` is to the left of the pole, `c` to the right of the abscissa of convergence. -/
  strip : σ < 1 ∧ 1 < c
  /-- The horizontal segments of the rectangle vanish as the height grows.
  This is the `ζ'/ζ` growth bound; Mathlib has no zero-free region to supply it. -/
  horizontal_vanishes :
    Tendsto (fun T : ℝ => ∫ x in σ..c, (-(deriv riemannZeta (x + T * I) / riemannZeta (x + T * I)))
      * F (x + T * I)) atTop (𝓝 0)
  /-- The zero-side residues form a summable family. -/
  zero_side_summable :
    Summable (fun ρ : {z : ℂ // riemannZeta z = 0 ∧ z ≠ 1} => F ρ.1)

/-- The obligation is a genuine hypothesis, not something this file establishes:
it is quantified over, never constructed. -/
theorem contour_shift_is_assumed_not_proved_v1
    (F : ℂ → ℂ) (σ c : ℝ) (h : ContourShiftObligationV1 F σ c) : σ < 1 ∧ 1 < c :=
  h.strip

end WeilPoleTerm

#print axioms WeilPoleTerm.zeta1LogDeriv_tendsto
#print axioms WeilPoleTerm.neg_logDeriv_riemannZeta_residue_one
#print axioms WeilPoleTerm.weil_pole_term_v1
#print axioms WeilPoleTerm.weil_pole_term_ne_zero_v1
#print axioms WeilPoleTerm.vonMangoldt_lseries_eq_neg_logDeriv_v1
#print axioms WeilPoleTerm.contour_shift_is_assumed_not_proved_v1
