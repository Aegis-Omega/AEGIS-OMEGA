import RHRationalNinePacketPrimeWindowV1
import RHNineBlockActualExpansionV1
import RHNarrowDiagonalUpgradeV2
import Mathlib.Tactic

/-!
AEGIS Omega -- concrete rational nine-packet coercivity candidate V1.

For the existing moment-zero packet class with actual log-support half-width
1/256, place nine translates on the lattice

  d_j = j * log(33/16), j = 0,...,8.

The prime-window module supplies all 36 off-diagonal B norm bounds by reducing
them to the first eight prime-void gaps. The inherited narrow diagonal theorem
supplies all nine diagonal bounds. The actual nine-block expansion and exact
SOS comparison then give coercivity margin 6/5.

This is a finite translated family theorem only. It is not a density theorem,
arbitrary-window theorem, universal Weil sign theorem, or RH proof.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHRationalNinePacketConcreteV1

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.RHNarrowDiagonalUpgradeV2
open AEGIS.RHFineMomentPacketV3
open AEGIS.RHRationalNinePacketPrimeWindowV1
open AEGIS.RHNineBlockComparisonV1
open AEGIS.RHNineBlockActualExpansionV1

theorem fine_width_implies_width_one_sixty_four_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WidthOneSixtyFourAt g a := by
  intro t ht
  have h := hw ht
  exact ⟨by linarith [h.1], by linarith [h.2]⟩

theorem translate_width_one_sixty_four_v1
    (g : WeilCompactSmoothGV1) (a d : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WidthOneSixtyFourAt (translatePacket g d) (a + d) := by
  have hs := translate_logSupportIn g d
    (a - 1 / 128) (a + 1 / 128)
    (fine_width_implies_width_one_sixty_four_v1 g a hw)
  change LogSupportIn (translatePacket g d)
    (a + d - 1 / 128) (a + d + 1 / 128)
  convert hs using 1 <;> ring

theorem translated_diagonal_nine_v1
    (g : WeilCompactSmoothGV1) (a d : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    (32 / 25 : ℝ) * energy g.1 ≤
      -(B (translatePacket g d) (translatePacket g d)).re := by
  have hd := narrow_diagonal_32_over_25_v2
    (translatePacket g d) (a + d)
    (translate_width_one_sixty_four_v1 g a d hw)
  rw [translate_energy] at hd
  exact hd

def ninePacketV1 (g : WeilCompactSmoothGV1)
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) : WeilCompactSmoothGV1 :=
  combo9 z0 z1 z2 z3 z4 z5 z6 z7 z8 (translatePacket g (qNineShiftV1 0)) (translatePacket g (qNineShiftV1 1)) (translatePacket g (qNineShiftV1 2)) (translatePacket g (qNineShiftV1 3)) (translatePacket g (qNineShiftV1 4)) (translatePacket g (qNineShiftV1 5)) (translatePacket g (qNineShiftV1 6)) (translatePacket g (qNineShiftV1 7)) (translatePacket g (qNineShiftV1 8))

theorem nine_packet_coercive_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g)
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (ninePacketV1 g z0 z1 z2 z3 z4 z5 z6 z7 z8))).re ≤
      -(6 / 5 : ℝ) * energy g.1 *
        energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
  have hE := energy_nonnegative g.1
  have h0 := translated_diagonal_nine_v1 g a (qNineShiftV1 0) hw
  have h1 := translated_diagonal_nine_v1 g a (qNineShiftV1 1) hw
  have h2 := translated_diagonal_nine_v1 g a (qNineShiftV1 2) hw
  have h3 := translated_diagonal_nine_v1 g a (qNineShiftV1 3) hw
  have h4 := translated_diagonal_nine_v1 g a (qNineShiftV1 4) hw
  have h5 := translated_diagonal_nine_v1 g a (qNineShiftV1 5) hw
  have h6 := translated_diagonal_nine_v1 g a (qNineShiftV1 6) hw
  have h7 := translated_diagonal_nine_v1 g a (qNineShiftV1 7) hw
  have h8 := translated_diagonal_nine_v1 g a (qNineShiftV1 8) hw
  have h01 : ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 1))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_one_B_norm_v1 g a hw hm 0
  have h02 : ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 2))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_two_B_norm_v1 g a hw hm 0
  have h03 : ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 3))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_three_B_norm_v1 g a hw hm 0
  have h04 : ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 4))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_four_B_norm_v1 g a hw hm 0
  have h05 : ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 5))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_five_B_norm_v1 g a hw hm 0
  have h06 : ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 6))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_six_B_norm_v1 g a hw hm 0
  have h07 : ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 7))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_seven_B_norm_v1 g a hw hm 0
  have h08 : ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 8))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_eight_B_norm_v1 g a hw hm 0
  have h12 : ‖B (translatePacket g (qNineShiftV1 1))
      (translatePacket g (qNineShiftV1 2))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_one_B_norm_v1 g a hw hm 1
  have h13 : ‖B (translatePacket g (qNineShiftV1 1))
      (translatePacket g (qNineShiftV1 3))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_two_B_norm_v1 g a hw hm 1
  have h14 : ‖B (translatePacket g (qNineShiftV1 1))
      (translatePacket g (qNineShiftV1 4))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_three_B_norm_v1 g a hw hm 1
  have h15 : ‖B (translatePacket g (qNineShiftV1 1))
      (translatePacket g (qNineShiftV1 5))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_four_B_norm_v1 g a hw hm 1
  have h16 : ‖B (translatePacket g (qNineShiftV1 1))
      (translatePacket g (qNineShiftV1 6))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_five_B_norm_v1 g a hw hm 1
  have h17 : ‖B (translatePacket g (qNineShiftV1 1))
      (translatePacket g (qNineShiftV1 7))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_six_B_norm_v1 g a hw hm 1
  have h18 : ‖B (translatePacket g (qNineShiftV1 1))
      (translatePacket g (qNineShiftV1 8))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_seven_B_norm_v1 g a hw hm 1
  have h23 : ‖B (translatePacket g (qNineShiftV1 2))
      (translatePacket g (qNineShiftV1 3))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_one_B_norm_v1 g a hw hm 2
  have h24 : ‖B (translatePacket g (qNineShiftV1 2))
      (translatePacket g (qNineShiftV1 4))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_two_B_norm_v1 g a hw hm 2
  have h25 : ‖B (translatePacket g (qNineShiftV1 2))
      (translatePacket g (qNineShiftV1 5))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_three_B_norm_v1 g a hw hm 2
  have h26 : ‖B (translatePacket g (qNineShiftV1 2))
      (translatePacket g (qNineShiftV1 6))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_four_B_norm_v1 g a hw hm 2
  have h27 : ‖B (translatePacket g (qNineShiftV1 2))
      (translatePacket g (qNineShiftV1 7))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_five_B_norm_v1 g a hw hm 2
  have h28 : ‖B (translatePacket g (qNineShiftV1 2))
      (translatePacket g (qNineShiftV1 8))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_six_B_norm_v1 g a hw hm 2
  have h34 : ‖B (translatePacket g (qNineShiftV1 3))
      (translatePacket g (qNineShiftV1 4))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_one_B_norm_v1 g a hw hm 3
  have h35 : ‖B (translatePacket g (qNineShiftV1 3))
      (translatePacket g (qNineShiftV1 5))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_two_B_norm_v1 g a hw hm 3
  have h36 : ‖B (translatePacket g (qNineShiftV1 3))
      (translatePacket g (qNineShiftV1 6))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_three_B_norm_v1 g a hw hm 3
  have h37 : ‖B (translatePacket g (qNineShiftV1 3))
      (translatePacket g (qNineShiftV1 7))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_four_B_norm_v1 g a hw hm 3
  have h38 : ‖B (translatePacket g (qNineShiftV1 3))
      (translatePacket g (qNineShiftV1 8))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_five_B_norm_v1 g a hw hm 3
  have h45 : ‖B (translatePacket g (qNineShiftV1 4))
      (translatePacket g (qNineShiftV1 5))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_one_B_norm_v1 g a hw hm 4
  have h46 : ‖B (translatePacket g (qNineShiftV1 4))
      (translatePacket g (qNineShiftV1 6))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_two_B_norm_v1 g a hw hm 4
  have h47 : ‖B (translatePacket g (qNineShiftV1 4))
      (translatePacket g (qNineShiftV1 7))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_three_B_norm_v1 g a hw hm 4
  have h48 : ‖B (translatePacket g (qNineShiftV1 4))
      (translatePacket g (qNineShiftV1 8))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_four_B_norm_v1 g a hw hm 4
  have h56 : ‖B (translatePacket g (qNineShiftV1 5))
      (translatePacket g (qNineShiftV1 6))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_one_B_norm_v1 g a hw hm 5
  have h57 : ‖B (translatePacket g (qNineShiftV1 5))
      (translatePacket g (qNineShiftV1 7))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_two_B_norm_v1 g a hw hm 5
  have h58 : ‖B (translatePacket g (qNineShiftV1 5))
      (translatePacket g (qNineShiftV1 8))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_three_B_norm_v1 g a hw hm 5
  have h67 : ‖B (translatePacket g (qNineShiftV1 6))
      (translatePacket g (qNineShiftV1 7))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_one_B_norm_v1 g a hw hm 6
  have h68 : ‖B (translatePacket g (qNineShiftV1 6))
      (translatePacket g (qNineShiftV1 8))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_two_B_norm_v1 g a hw hm 6
  have h78 : ‖B (translatePacket g (qNineShiftV1 7))
      (translatePacket g (qNineShiftV1 8))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
    simpa using shift_gap_one_B_norm_v1 g a hw hm 7
  unfold ninePacketV1
  exact actual_nine_block_bound_v1
    z0 z1 z2 z3 z4 z5 z6 z7 z8
    (translatePacket g (qNineShiftV1 0)) (translatePacket g (qNineShiftV1 1)) (translatePacket g (qNineShiftV1 2)) (translatePacket g (qNineShiftV1 3)) (translatePacket g (qNineShiftV1 4)) (translatePacket g (qNineShiftV1 5)) (translatePacket g (qNineShiftV1 6)) (translatePacket g (qNineShiftV1 7)) (translatePacket g (qNineShiftV1 8))
    (energy g.1) hE
    h0 h1 h2 h3 h4 h5 h6 h7 h8 h01 h02 h03 h04 h05 h06 h07 h08 h12 h13 h14 h15 h16 h17 h18 h23 h24 h25 h26 h27 h28 h34 h35 h36 h37 h38 h45 h46 h47 h48 h56 h57 h58 h67 h68 h78

theorem canonical_nine_packet_coercive_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (ninePacketV1 gFine z0 z1 z2 z3 z4 z5 z6 z7 z8))).re ≤
      -(6 / 5 : ℝ) * energy gFine.1 *
        energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ :=
  nine_packet_coercive_v1
    gFine 0 gFine_width_one_one_twenty_eight_v1 gFine_moments_v3
    z0 z1 z2 z3 z4 z5 z6 z7 z8

theorem canonical_nine_packet_sign_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (ninePacketV1 gFine z0 z1 z2 z3 z4 z5 z6 z7 z8))).re ≤ 0 := by
  have hb := canonical_nine_packet_coercive_v1 z0 z1 z2 z3 z4 z5 z6 z7 z8
  have hE := energy_nonnegative gFine.1
  have hS : 0 ≤ energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
    unfold energy9
    positivity
  nlinarith [mul_nonneg hE hS]

end AEGIS.RHRationalNinePacketConcreteV1

#print axioms AEGIS.RHRationalNinePacketConcreteV1.fine_width_implies_width_one_sixty_four_v1
#print axioms AEGIS.RHRationalNinePacketConcreteV1.translated_diagonal_nine_v1
#print axioms AEGIS.RHRationalNinePacketConcreteV1.nine_packet_coercive_v1
#print axioms AEGIS.RHRationalNinePacketConcreteV1.canonical_nine_packet_coercive_v1
#print axioms AEGIS.RHRationalNinePacketConcreteV1.canonical_nine_packet_sign_v1
