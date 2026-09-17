import WeilMellinWeightedFixedLineV2

open Complex MeasureTheory

set_option autoImplicit false

noncomputable section

/-- Freeze the missing A1 input from the #490 fixed-line proof:
the first absolute vertical moment is integrable on every real Mellin line. -/
example (f : WeilCompactSmoothGV1) (σ : ℝ) :
    Integrable (fun γ : ℝ =>
      |γ| * ‖mellin f.1 ((σ : ℂ) + (γ : ℂ) * Complex.I)‖) :=
  weil_compact_smooth_mellin_vertical_abs_moment_one_v2 f σ

end
