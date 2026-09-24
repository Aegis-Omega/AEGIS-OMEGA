import RHFineDiagonalUpgradeV3
import RHRationalNinePacketConcreteV1
import RHNineBlockActualExpansionV1
import Mathlib.Tactic

/-!
AEGIS Omega -- fine-diagonal nine-packet coercivity V1.

The kernel-verified nine-packet comparison spends 2/25 of diagonal budget on
the complete set of 36 off-diagonal pairs. The independently kernel-verified
fine-support diagonal improves 32/25 to 5671/3200, an exact gain 63/128.

Therefore the same nine-packet family has coercivity margin

  6/5 + 63/128 = 1083/640.

This remains a concrete finite-family theorem only.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHFineNinePacketCoercivityV1

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.RHFineDiagonalUpgradeV3
open AEGIS.RHRationalNinePacketPrimeWindowV1
open AEGIS.RHNineBlockComparisonV1
open AEGIS.RHNineBlockActualBridgeV1
open AEGIS.RHNineBlockActualExpansionV1
open AEGIS.RHRationalNinePacketConcreteV1
open AEGIS.RHFineMomentPacketV3

theorem nine_value_bound_fine_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ)
    (D0 : ℝ) (D1 : ℝ) (D2 : ℝ) (D3 : ℝ) (D4 : ℝ) (D5 : ℝ) (D6 : ℝ) (D7 : ℝ) (D8 : ℝ) (E : ℝ)
    (b01 : ℂ) (b02 : ℂ) (b03 : ℂ) (b04 : ℂ) (b05 : ℂ) (b06 : ℂ) (b07 : ℂ) (b08 : ℂ) (b12 : ℂ) (b13 : ℂ) (b14 : ℂ) (b15 : ℂ) (b16 : ℂ) (b17 : ℂ) (b18 : ℂ) (b23 : ℂ) (b24 : ℂ) (b25 : ℂ) (b26 : ℂ) (b27 : ℂ) (b28 : ℂ) (b34 : ℂ) (b35 : ℂ) (b36 : ℂ) (b37 : ℂ) (b38 : ℂ) (b45 : ℂ) (b46 : ℂ) (b47 : ℂ) (b48 : ℂ) (b56 : ℂ) (b57 : ℂ) (b58 : ℂ) (b67 : ℂ) (b68 : ℂ) (b78 : ℂ)
    (hE : 0 ≤ E)
    (h0 : (5671 / 3200 : ℝ) * E ≤ D0)
    (h1 : (5671 / 3200 : ℝ) * E ≤ D1)
    (h2 : (5671 / 3200 : ℝ) * E ≤ D2)
    (h3 : (5671 / 3200 : ℝ) * E ≤ D3)
    (h4 : (5671 / 3200 : ℝ) * E ≤ D4)
    (h5 : (5671 / 3200 : ℝ) * E ≤ D5)
    (h6 : (5671 / 3200 : ℝ) * E ≤ D6)
    (h7 : (5671 / 3200 : ℝ) * E ≤ D7)
    (h8 : (5671 / 3200 : ℝ) * E ≤ D8)
    (h01 : ‖b01‖ ≤ (1 / 100 : ℝ) * E)
    (h02 : ‖b02‖ ≤ (1 / 100 : ℝ) * E)
    (h03 : ‖b03‖ ≤ (1 / 100 : ℝ) * E)
    (h04 : ‖b04‖ ≤ (1 / 100 : ℝ) * E)
    (h05 : ‖b05‖ ≤ (1 / 100 : ℝ) * E)
    (h06 : ‖b06‖ ≤ (1 / 100 : ℝ) * E)
    (h07 : ‖b07‖ ≤ (1 / 100 : ℝ) * E)
    (h08 : ‖b08‖ ≤ (1 / 100 : ℝ) * E)
    (h12 : ‖b12‖ ≤ (1 / 100 : ℝ) * E)
    (h13 : ‖b13‖ ≤ (1 / 100 : ℝ) * E)
    (h14 : ‖b14‖ ≤ (1 / 100 : ℝ) * E)
    (h15 : ‖b15‖ ≤ (1 / 100 : ℝ) * E)
    (h16 : ‖b16‖ ≤ (1 / 100 : ℝ) * E)
    (h17 : ‖b17‖ ≤ (1 / 100 : ℝ) * E)
    (h18 : ‖b18‖ ≤ (1 / 100 : ℝ) * E)
    (h23 : ‖b23‖ ≤ (1 / 100 : ℝ) * E)
    (h24 : ‖b24‖ ≤ (1 / 100 : ℝ) * E)
    (h25 : ‖b25‖ ≤ (1 / 100 : ℝ) * E)
    (h26 : ‖b26‖ ≤ (1 / 100 : ℝ) * E)
    (h27 : ‖b27‖ ≤ (1 / 100 : ℝ) * E)
    (h28 : ‖b28‖ ≤ (1 / 100 : ℝ) * E)
    (h34 : ‖b34‖ ≤ (1 / 100 : ℝ) * E)
    (h35 : ‖b35‖ ≤ (1 / 100 : ℝ) * E)
    (h36 : ‖b36‖ ≤ (1 / 100 : ℝ) * E)
    (h37 : ‖b37‖ ≤ (1 / 100 : ℝ) * E)
    (h38 : ‖b38‖ ≤ (1 / 100 : ℝ) * E)
    (h45 : ‖b45‖ ≤ (1 / 100 : ℝ) * E)
    (h46 : ‖b46‖ ≤ (1 / 100 : ℝ) * E)
    (h47 : ‖b47‖ ≤ (1 / 100 : ℝ) * E)
    (h48 : ‖b48‖ ≤ (1 / 100 : ℝ) * E)
    (h56 : ‖b56‖ ≤ (1 / 100 : ℝ) * E)
    (h57 : ‖b57‖ ≤ (1 / 100 : ℝ) * E)
    (h58 : ‖b58‖ ≤ (1 / 100 : ℝ) * E)
    (h67 : ‖b67‖ ≤ (1 / 100 : ℝ) * E)
    (h68 : ‖b68‖ ≤ (1 / 100 : ℝ) * E)
    (h78 : ‖b78‖ ≤ (1 / 100 : ℝ) * E) :
    nineValue z0 z1 z2 z3 z4 z5 z6 z7 z8 D0 D1 D2 D3 D4 D5 D6 D7 D8 b01 b02 b03 b04 b05 b06 b07 b08 b12 b13 b14 b15 b16 b17 b18 b23 b24 b25 b26 b27 b28 b34 b35 b36 b37 b38 b45 b46 b47 b48 b56 b57 b58 b67 b68 b78 ≤
      -(1083 / 640 : ℝ) * E * energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
  let D0' : ℝ := D0 - (63 / 128 : ℝ) * E
  let D1' : ℝ := D1 - (63 / 128 : ℝ) * E
  let D2' : ℝ := D2 - (63 / 128 : ℝ) * E
  let D3' : ℝ := D3 - (63 / 128 : ℝ) * E
  let D4' : ℝ := D4 - (63 / 128 : ℝ) * E
  let D5' : ℝ := D5 - (63 / 128 : ℝ) * E
  let D6' : ℝ := D6 - (63 / 128 : ℝ) * E
  let D7' : ℝ := D7 - (63 / 128 : ℝ) * E
  let D8' : ℝ := D8 - (63 / 128 : ℝ) * E
  have h0' : (32 / 25 : ℝ) * E ≤ D0' := by
    dsimp [D0']
    linarith [h0]
  have h1' : (32 / 25 : ℝ) * E ≤ D1' := by
    dsimp [D1']
    linarith [h1]
  have h2' : (32 / 25 : ℝ) * E ≤ D2' := by
    dsimp [D2']
    linarith [h2]
  have h3' : (32 / 25 : ℝ) * E ≤ D3' := by
    dsimp [D3']
    linarith [h3]
  have h4' : (32 / 25 : ℝ) * E ≤ D4' := by
    dsimp [D4']
    linarith [h4]
  have h5' : (32 / 25 : ℝ) * E ≤ D5' := by
    dsimp [D5']
    linarith [h5]
  have h6' : (32 / 25 : ℝ) * E ≤ D6' := by
    dsimp [D6']
    linarith [h6]
  have h7' : (32 / 25 : ℝ) * E ≤ D7' := by
    dsimp [D7']
    linarith [h7]
  have h8' : (32 / 25 : ℝ) * E ≤ D8' := by
    dsimp [D8']
    linarith [h8]
  have hold := nine_value_bound_v1
    z0 z1 z2 z3 z4 z5 z6 z7 z8
    D0' D1' D2' D3' D4' D5' D6' D7' D8' E
    b01 b02 b03 b04 b05 b06 b07 b08 b12 b13 b14 b15 b16 b17 b18 b23 b24 b25 b26 b27 b28 b34 b35 b36 b37 b38 b45 b46 b47 b48 b56 b57 b58 b67 b68 b78
    hE h0' h1' h2' h3' h4' h5' h6' h7' h8' h01 h02 h03 h04 h05 h06 h07 h08 h12 h13 h14 h15 h16 h17 h18 h23 h24 h25 h26 h27 h28 h34 h35 h36 h37 h38 h45 h46 h47 h48 h56 h57 h58 h67 h68 h78
  have hid :
      nineValue z0 z1 z2 z3 z4 z5 z6 z7 z8 D0 D1 D2 D3 D4 D5 D6 D7 D8 b01 b02 b03 b04 b05 b06 b07 b08 b12 b13 b14 b15 b16 b17 b18 b23 b24 b25 b26 b27 b28 b34 b35 b36 b37 b38 b45 b46 b47 b48 b56 b57 b58 b67 b68 b78 =
        nineValue z0 z1 z2 z3 z4 z5 z6 z7 z8 D0' D1' D2' D3' D4' D5' D6' D7' D8' b01 b02 b03 b04 b05 b06 b07 b08 b12 b13 b14 b15 b16 b17 b18 b23 b24 b25 b26 b27 b28 b34 b35 b36 b37 b38 b45 b46 b47 b48 b56 b57 b58 b67 b68 b78 -
          (63 / 128 : ℝ) * E * energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
    unfold nineValue energy9
    dsimp [D0', D1', D2', D3', D4', D5', D6', D7', D8']
    ring
  rw [hid]
  linarith [hold]

theorem actual_nine_block_bound_fine_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ)
    (g0 : WeilCompactSmoothGV1) (g1 : WeilCompactSmoothGV1) (g2 : WeilCompactSmoothGV1) (g3 : WeilCompactSmoothGV1) (g4 : WeilCompactSmoothGV1) (g5 : WeilCompactSmoothGV1) (g6 : WeilCompactSmoothGV1) (g7 : WeilCompactSmoothGV1) (g8 : WeilCompactSmoothGV1)
    (E : ℝ) (hE : 0 ≤ E)
    (h0 : (5671 / 3200 : ℝ) * E ≤ -(B g0 g0).re)
    (h1 : (5671 / 3200 : ℝ) * E ≤ -(B g1 g1).re)
    (h2 : (5671 / 3200 : ℝ) * E ≤ -(B g2 g2).re)
    (h3 : (5671 / 3200 : ℝ) * E ≤ -(B g3 g3).re)
    (h4 : (5671 / 3200 : ℝ) * E ≤ -(B g4 g4).re)
    (h5 : (5671 / 3200 : ℝ) * E ≤ -(B g5 g5).re)
    (h6 : (5671 / 3200 : ℝ) * E ≤ -(B g6 g6).re)
    (h7 : (5671 / 3200 : ℝ) * E ≤ -(B g7 g7).re)
    (h8 : (5671 / 3200 : ℝ) * E ≤ -(B g8 g8).re)
    (h01 : ‖B g0 g1‖ ≤ (1 / 100 : ℝ) * E)
    (h02 : ‖B g0 g2‖ ≤ (1 / 100 : ℝ) * E)
    (h03 : ‖B g0 g3‖ ≤ (1 / 100 : ℝ) * E)
    (h04 : ‖B g0 g4‖ ≤ (1 / 100 : ℝ) * E)
    (h05 : ‖B g0 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h06 : ‖B g0 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h07 : ‖B g0 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h08 : ‖B g0 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h12 : ‖B g1 g2‖ ≤ (1 / 100 : ℝ) * E)
    (h13 : ‖B g1 g3‖ ≤ (1 / 100 : ℝ) * E)
    (h14 : ‖B g1 g4‖ ≤ (1 / 100 : ℝ) * E)
    (h15 : ‖B g1 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h16 : ‖B g1 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h17 : ‖B g1 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h18 : ‖B g1 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h23 : ‖B g2 g3‖ ≤ (1 / 100 : ℝ) * E)
    (h24 : ‖B g2 g4‖ ≤ (1 / 100 : ℝ) * E)
    (h25 : ‖B g2 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h26 : ‖B g2 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h27 : ‖B g2 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h28 : ‖B g2 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h34 : ‖B g3 g4‖ ≤ (1 / 100 : ℝ) * E)
    (h35 : ‖B g3 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h36 : ‖B g3 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h37 : ‖B g3 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h38 : ‖B g3 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h45 : ‖B g4 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h46 : ‖B g4 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h47 : ‖B g4 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h48 : ‖B g4 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h56 : ‖B g5 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h57 : ‖B g5 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h58 : ‖B g5 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h67 : ‖B g6 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h68 : ‖B g6 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h78 : ‖B g7 g8‖ ≤ (1 / 100 : ℝ) * E) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (combo9 z0 z1 z2 z3 z4 z5 z6 z7 z8 g0 g1 g2 g3 g4 g5 g6 g7 g8))).re ≤
      -(1083 / 640 : ℝ) * E * energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
  rw [actual_nine_block_expansion_v1]
  exact nine_value_bound_fine_v1
    z0 z1 z2 z3 z4 z5 z6 z7 z8
    (-(B g0 g0).re) (-(B g1 g1).re) (-(B g2 g2).re) (-(B g3 g3).re) (-(B g4 g4).re) (-(B g5 g5).re) (-(B g6 g6).re) (-(B g7 g7).re) (-(B g8 g8).re) E
    (B g0 g1) (B g0 g2) (B g0 g3) (B g0 g4) (B g0 g5) (B g0 g6) (B g0 g7) (B g0 g8) (B g1 g2) (B g1 g3) (B g1 g4) (B g1 g5) (B g1 g6) (B g1 g7) (B g1 g8) (B g2 g3) (B g2 g4) (B g2 g5) (B g2 g6) (B g2 g7) (B g2 g8) (B g3 g4) (B g3 g5) (B g3 g6) (B g3 g7) (B g3 g8) (B g4 g5) (B g4 g6) (B g4 g7) (B g4 g8) (B g5 g6) (B g5 g7) (B g5 g8) (B g6 g7) (B g6 g8) (B g7 g8)
    hE h0 h1 h2 h3 h4 h5 h6 h7 h8 h01 h02 h03 h04 h05 h06 h07 h08 h12 h13 h14 h15 h16 h17 h18 h23 h24 h25 h26 h27 h28 h34 h35 h36 h37 h38 h45 h46 h47 h48 h56 h57 h58 h67 h68 h78

theorem translated_fine_diagonal_v1
    (g : WeilCompactSmoothGV1) (a d : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    (5671 / 3200 : ℝ) * energy g.1 ≤
      -(B (translatePacket g d) (translatePacket g d)).re := by
  have hwidth :
      WidthOneOneTwentyEightAt (translatePacket g d) (a + d) := by
    have hs := translate_logSupportIn g d
      (a - 1 / 256) (a + 1 / 256) hw
    change LogSupportIn (translatePacket g d)
      (a + d - 1 / 256) (a + d + 1 / 256)
    convert hs using 1 <;> ring
  have hd := fine_diagonal_5671_over_3200_v3
    (translatePacket g d) (a + d) hwidth
  rw [translate_energy] at hd
  exact hd

theorem nine_packet_coercive_fine_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g)
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (ninePacketV1 g z0 z1 z2 z3 z4 z5 z6 z7 z8))).re ≤
      -(1083 / 640 : ℝ) * energy g.1 * energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
  have hE := energy_nonnegative g.1
  have h0 := translated_fine_diagonal_v1 g a (qNineShiftV1 0) hw
  have h1 := translated_fine_diagonal_v1 g a (qNineShiftV1 1) hw
  have h2 := translated_fine_diagonal_v1 g a (qNineShiftV1 2) hw
  have h3 := translated_fine_diagonal_v1 g a (qNineShiftV1 3) hw
  have h4 := translated_fine_diagonal_v1 g a (qNineShiftV1 4) hw
  have h5 := translated_fine_diagonal_v1 g a (qNineShiftV1 5) hw
  have h6 := translated_fine_diagonal_v1 g a (qNineShiftV1 6) hw
  have h7 := translated_fine_diagonal_v1 g a (qNineShiftV1 7) hw
  have h8 := translated_fine_diagonal_v1 g a (qNineShiftV1 8) hw
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
  exact actual_nine_block_bound_fine_v1
    z0 z1 z2 z3 z4 z5 z6 z7 z8
    (translatePacket g (qNineShiftV1 0)) (translatePacket g (qNineShiftV1 1)) (translatePacket g (qNineShiftV1 2)) (translatePacket g (qNineShiftV1 3)) (translatePacket g (qNineShiftV1 4)) (translatePacket g (qNineShiftV1 5)) (translatePacket g (qNineShiftV1 6)) (translatePacket g (qNineShiftV1 7)) (translatePacket g (qNineShiftV1 8))
    (energy g.1) hE
    h0 h1 h2 h3 h4 h5 h6 h7 h8 h01 h02 h03 h04 h05 h06 h07 h08 h12 h13 h14 h15 h16 h17 h18 h23 h24 h25 h26 h27 h28 h34 h35 h36 h37 h38 h45 h46 h47 h48 h56 h57 h58 h67 h68 h78

theorem canonical_nine_packet_coercive_fine_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (ninePacketV1 gFine z0 z1 z2 z3 z4 z5 z6 z7 z8))).re ≤
      -(1083 / 640 : ℝ) * energy gFine.1 * energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ :=
  nine_packet_coercive_fine_v1
    gFine 0 gFine_width_one_one_twenty_eight_v1 gFine_moments_v3
    z0 z1 z2 z3 z4 z5 z6 z7 z8

theorem canonical_nine_packet_sign_fine_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (ninePacketV1 gFine z0 z1 z2 z3 z4 z5 z6 z7 z8))).re ≤ 0 := by
  have hb := canonical_nine_packet_coercive_fine_v1 z0 z1 z2 z3 z4 z5 z6 z7 z8
  have hE := energy_nonnegative gFine.1
  have hS : 0 ≤ energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
    unfold energy9
    positivity
  nlinarith [mul_nonneg hE hS]

end AEGIS.RHFineNinePacketCoercivityV1

#print axioms AEGIS.RHFineNinePacketCoercivityV1.nine_value_bound_fine_v1
#print axioms AEGIS.RHFineNinePacketCoercivityV1.actual_nine_block_bound_fine_v1
#print axioms AEGIS.RHFineNinePacketCoercivityV1.translated_fine_diagonal_v1
#print axioms AEGIS.RHFineNinePacketCoercivityV1.nine_packet_coercive_fine_v1
#print axioms AEGIS.RHFineNinePacketCoercivityV1.canonical_nine_packet_coercive_fine_v1
#print axioms AEGIS.RHFineNinePacketCoercivityV1.canonical_nine_packet_sign_fine_v1
