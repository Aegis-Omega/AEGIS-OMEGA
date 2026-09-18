import WeilWidthArchCorrelationV25

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators
set_option autoImplicit false
noncomputable section

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilWidthArchCorrelationV25

example (g : WeilCompactSmoothGV1) (u : ℝ) :
    ‖logCorrelationV25 g u‖ ≤ energy g.1 :=
  norm_logCorrelation_le_energy_v25 g u

example (g : WeilCompactSmoothGV1) (a u : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    (hu : (1 / 32 : ℝ) < u) :
    logCorrelationV25 g u = 0 :=
  logCorrelation_zero_of_width_v25 g a u hw hu
