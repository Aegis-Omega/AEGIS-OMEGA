import ZeroCountingMellinSummabilityV1

/-!
AEGIS Ω — multiplicity-safe zero residues for the Guinand–Weil contour lane.

This module repairs two scope defects in the earlier contour obligation:

1. a residue of `-ζ'/ζ` at a nontrivial zero carries its analytic
   multiplicity, so the zero-side summand must be multiplicity weighted;
2. horizontal contour decay must be stated along a cofinal sequence of
   admissible/good heights, not as a limit through every real height (where
   the contour may meet or approach zero ordinates).

The only positive result here is the zero-side absolute summability already
supported by the multiplicity-safe Mellin theorem.  No good-height sequence,
horizontal decay, gamma/trivial-zero assembly, whole explicit formula, Weil
sign, or RH theorem is asserted.
-/

open Set Filter Topology
open Complex

noncomputable section

/-- Multiplicity-safe nontrivial-zero residue summand. -/
def WeilContourZeroResidueSummandV2
    (F : ℂ → ℂ) (rho : RiemannNontrivialZeroIndexV2) : ℂ :=
  (analyticOrderNatAt riemannZeta rho.1 : ℂ) * F rho.1

/-- Compact-smooth Mellin values give an absolutely summable contour zero side,
with analytic multiplicity retained exactly. -/
theorem weil_compact_smooth_contour_zero_residue_summable_v2
    (g : WeilCompactSmoothGV1) :
    Summable (WeilContourZeroResidueSummandV2 (mellin g.1)) := by
  simpa [WeilContourZeroResidueSummandV2, WeilZeroIndexSummandV1] using
    weil_compact_smooth_zero_summable_v1 g

/-- Norm summability of the same multiplicity-safe residue series. -/
theorem weil_compact_smooth_contour_zero_residue_norm_summable_v2
    (g : WeilCompactSmoothGV1) :
    Summable (fun rho =>
      ‖WeilContourZeroResidueSummandV2 (mellin g.1) rho‖) := by
  exact (weil_compact_smooth_contour_zero_residue_summable_v2 g).norm

/-- Corrected shape of the still-open contour-shift obligation.

The horizontal terms are left abstract on purpose: a raw-zeta contour still
requires explicit gamma/trivial-zero bookkeeping (or a switch to completed
`ξ`).  The structure records the mathematically correct good-height topology
and the multiplicity-safe zero-side requirement without pretending those
remaining analytic ingredients are already proved. -/
structure WeilGoodHeightContourShiftObligationV2
    (F : ℂ → ℂ)
    (horizontalTop horizontalBottom : ℝ → ℂ) : Prop where
  heights : ℕ → ℝ
  heights_pos : ∀ n, 0 < heights n
  heights_tendsto : Tendsto heights atTop atTop
  horizontal_top_vanishes :
    Tendsto (fun n => horizontalTop (heights n)) atTop (𝓝 0)
  horizontal_bottom_vanishes :
    Tendsto (fun n => horizontalBottom (heights n)) atTop (𝓝 0)
  zero_side_summable :
    Summable (WeilContourZeroResidueSummandV2 F)

#print axioms weil_compact_smooth_contour_zero_residue_summable_v2
#print axioms weil_compact_smooth_contour_zero_residue_norm_summable_v2
