import WeilWidthArchIntegralV27

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators
set_option autoImplicit false
noncomputable section

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilWidthArchBudgetV26
open AEGIS.WeilDiagonalKernelReductionV21
open AEGIS.WeilWidthDiagonalArchFrontierV24
open AEGIS.WeilWidthArchIntegralV27

example (g : WeilCompactSmoothGV1) :
    (WeilArchimedeanIntegralV1 (WeilAutocorrelationV1 g)).re =
      ∫ u in Ioi (0 : ℝ), widthArchLogIntegrandV26 g u :=
  archimedean_real_eq_log_integral_v27 g

example (g : WeilCompactSmoothGV1) :
    (∫ u in Ioc (0 : ℝ) (1 / 32 : ℝ),
      widthArchLogIntegrandV26 g u) ≤
      energy g.1 * diagonalSmallV21 :=
  width_arch_inner_integral_le_v27 g

example (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) :
    (∫ u in Ioi (1 / 32 : ℝ), widthArchLogIntegrandV26 g u) =
      -energy g.1 * diagonalTailV24 :=
  width_arch_tail_integral_eq_v27 g a hw

example (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) :
    (WeilArchimedeanIntegralV1 (WeilAutocorrelationV1 g)).re ≤
      energy g.1 * (diagonalSmallV21 - diagonalTailV24) :=
  width_archimedean_budget_v27 g a hw

example (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) :
    (103 / 100 : ℝ) * energy g.1 ≤ -(B g g).re :=
  width_diagonal_103_over_100_v27 g a hw
