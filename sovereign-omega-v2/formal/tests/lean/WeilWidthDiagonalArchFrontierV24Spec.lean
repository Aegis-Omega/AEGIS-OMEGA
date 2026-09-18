import WeilWidthDiagonalArchFrontierV24

open Set MeasureTheory Complex
set_option autoImplicit false
noncomputable section

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilDiagonalKernelReductionV21
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilWidthDiagonalArchFrontierV24

example
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    (harch :
      (WeilArchimedeanIntegralV1 (WeilAutocorrelationV1 g)).re ≤
        energy g.1 * (diagonalSmallV21 - diagonalTailV24)) :
    (103 / 100 : ℝ) * energy g.1 ≤ -(B g g).re :=
  width_diagonal_103_over_100_of_arch_budget_v24 g a hw harch
