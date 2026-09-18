import WeilMixedLogKernelV27

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false

noncomputable section

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilMixedLogKernelV27

example
    (a b : WeilCompactSmoothGV1) (u : ℝ) :
    mixedLogCorrelationV27 a b u =
      (Real.exp (u / 2) : ℂ) *
        AEGIS.WeilMixedClosureV2.mixed a b (Real.exp u) :=
  mixedLogCorrelation_eq_mixed_v27 a b u

example
    (a b : WeilCompactSmoothGV1) (u : ℝ) :
    ‖mixedLogCorrelationV27 a b u‖ ≤
      (1 / 2 : ℝ) * (energy a.1 + energy b.1) :=
  norm_mixedLogCorrelation_le_mean_energy_v27 a b u

example
    (a b : WeilCompactSmoothGV1)
    {alo ahi blo bhi u : ℝ}
    (ha : LogSupportIn a alo ahi)
    (hb : LogSupportIn b blo bhi)
    (hu : u < alo - bhi ∨ ahi - blo < u) :
    mixedLogCorrelationV27 a b u = 0 :=
  mixedLogCorrelation_zero_outside_v27 a b ha hb hu
