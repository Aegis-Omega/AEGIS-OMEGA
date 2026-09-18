import WeilThreeBlockCrossPrimeWindowV29

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators
set_option autoImplicit false
noncomputable section

open AEGIS.WeilMixedClosureV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilThreeBlockCrossPrimeWindowV29

example (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    (m : ℕ) (hm : 0 < m) :
    mixed (gMinus g) (gZero g) (m : ℝ) = 0 :=
  adjacent_mixed_nat_zero_v29 g a hw m hm

example (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    (m : ℕ) (hm : 0 < m) (hne : m ≠ 2) :
    mixed (gMinus g) (gZero g) ((m : ℝ)⁻¹) = 0 :=
  adjacent_mixed_inv_nat_zero_v29 g a hw m hm hne

example (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    (m : ℕ) (hm : 0 < m) :
    mixed (gMinus g) (gPlus g) (m : ℝ) = 0 :=
  outer_mixed_nat_zero_v29 g a hw m hm

example (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    (m : ℕ) (hm : 0 < m) (hne : m ≠ 4) :
    mixed (gMinus g) (gPlus g) ((m : ℝ)⁻¹) = 0 :=
  outer_mixed_inv_nat_zero_v29 g a hw m hm hne
