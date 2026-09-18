import WeilWidthArchBudgetV26

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators
set_option autoImplicit false
noncomputable section

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilWidthArchBudgetV26

example (g : WeilCompactSmoothGV1) (u : ℝ) :
    ‖WeilAutocorrelationV1 g (Real.exp u)‖ ≤
      Real.exp (-u / 2) * energy g.1 :=
  autocorrelation_exp_norm_le_v26 g u

example (g : WeilCompactSmoothGV1) {u : ℝ} (hu : 0 < u) :
    Real.exp u *
        (WeilArchimedeanIntegrandV1
          (WeilAutocorrelationV1 g) (Real.exp u)).re =
      widthArchLogIntegrandV26 g u :=
  exp_mul_archimedean_re_eq_log_v26 g hu

example (g : WeilCompactSmoothGV1) {u : ℝ}
    (hu0 : 0 < u) (huw : u ≤ (1 / 32 : ℝ)) :
    widthArchLogIntegrandV26 g u ≤
      energy g.1 * (Real.exp (1 / 64 : ℝ) / 2) :=
  width_arch_log_inner_pointwise_v26 g hu0 huw

example (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    {u : ℝ} (hu : (1 / 32 : ℝ) < u) :
    widthArchLogIntegrandV26 g u =
      -energy g.1 / Real.sinh u :=
  width_arch_log_tail_eq_v26 g a hw hu
