import WeilThreeBlockCrossPrimeV28

open Set Function MeasureTheory Complex
open scoped ComplexConjugate BigOperators
set_option autoImplicit false
noncomputable section

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedClosureV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilWidthArchCorrelationV25
open AEGIS.WeilThreeBlockCrossPrimeV28

example (g : WeilCompactSmoothGV1) (d1 d2 u : ℝ) :
    (Real.exp (u / 2) : ℂ) *
        mixed (translatePacket g d1) (translatePacket g d2) (Real.exp u) =
      logCorrelationV25 g (u + d2 - d1) :=
  exp_half_mul_mixed_translate_v28 g d1 d2 u

example (g : WeilCompactSmoothGV1) (a u : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    (hu : (1 / 32 : ℝ) < |u|) :
    logCorrelationV25 g u = 0 :=
  logCorrelation_zero_of_width_abs_v28 g a u hw hu

example (g : WeilCompactSmoothGV1) (a d1 d2 u : ℝ)
    (hw : WidthOneThirtyTwoAt g a)
    (hu : (1 / 32 : ℝ) < |u + d2 - d1|) :
    mixed (translatePacket g d1) (translatePacket g d2) (Real.exp u) = 0 :=
  mixed_translate_zero_of_width_v28 g a d1 d2 u hw hu

example (g : WeilCompactSmoothGV1) (d1 d2 : ℝ) :
    (Real.exp ((d1 - d2) / 2) : ℂ) *
        mixed (translatePacket g d1) (translatePacket g d2)
          (Real.exp (d1 - d2)) =
      (energy g.1 : ℂ) :=
  mixed_translate_center_v28 g d1 d2
