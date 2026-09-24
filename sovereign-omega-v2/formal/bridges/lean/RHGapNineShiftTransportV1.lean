import RHRationalGapNinePrimeBoundV1
import RHRationalNinePacketPrimeWindowV1
import Mathlib.Tactic

/-!
AEGIS Omega -- gap-nine lattice transport V1.

Transport the kernel-GREEN canonical gap-nine B norm bound from the pair
(0, log((33/16)^9)) to any pair on the rational shift lattice whose
index separation is exactly nine.

This module changes no constants and introduces no larger packet theorem.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHGapNineShiftTransportV1

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.RHRationalNinePacketPrimeWindowV1
open AEGIS.RHRationalGapNinePrimeBoundV1

theorem qNineShift_gap_nine_eq_v1 (i : ℕ) :
    qNineShiftV1 (i + 9) - qNineShiftV1 i = gapNineV1 := by
  rw [qNineShift_gap_v1 i 9]
  rfl

theorem shift_gap_nine_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g)
    (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 9)))‖ ≤
      (57 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 9))
    0 gapNineV1 (by simpa using qNineShift_gap_nine_eq_v1 i)]
  exact gap_nine_B_norm_v1 g a hw hm

theorem canonical_endpoint_gap_nine_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g (qNineShiftV1 0))
      (translatePacket g (qNineShiftV1 9))‖ ≤
      (57 / 100 : ℝ) * energy g.1 := by
  simpa using shift_gap_nine_B_norm_v1 g a hw hm 0

end AEGIS.RHGapNineShiftTransportV1

#print axioms AEGIS.RHGapNineShiftTransportV1.qNineShift_gap_nine_eq_v1
#print axioms AEGIS.RHGapNineShiftTransportV1.shift_gap_nine_B_norm_v1
#print axioms AEGIS.RHGapNineShiftTransportV1.canonical_endpoint_gap_nine_B_norm_v1
