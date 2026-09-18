import WeilWidthArchBudgetV26

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false

noncomputable section

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilWidthDiagonalArchFrontierV24
open AEGIS.WeilWidthArchBudgetV26

example
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) :
    (WeilArchimedeanIntegralV1 (WeilAutocorrelationV1 g)).re ≤
      energy g.1 * (diagonalSmallV21 - diagonalTailV24) :=
  actual_archimedean_integral_budget_v26 g a hw

example
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) :
    (103 / 100 : ℝ) * energy g.1 ≤ -(B g g).re :=
  width_diagonal_103_over_100_v26 g a hw
