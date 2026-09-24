import RHNineBlockActualBridgeV1
import Mathlib.Tactic

/-!
AEGIS Omega -- fine-diagonal nine-block bridge V1.

The verified fine-support diagonal lower bound is 5671/3200, exactly
63/128 stronger than the earlier 32/25 bound. Instead of re-proving the
36-pair comparison, shift every diagonal by 63/128 * E and reuse the existing
nine-block 6/5 theorem. The shift contributes exactly 63/128 times the
coefficient energy, yielding 1083/640 coercivity.

Finite complex algebra only.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Complex
open scoped ComplexConjugate

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHNineBlockFineBridgeV1

open AEGIS.RHNineBlockComparisonV1
open AEGIS.RHNineBlockActualBridgeV1

set_option maxHeartbeats 400000 in
theorem nine_value_bound_fine_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) (D0 : ℝ) (D1 : ℝ) (D2 : ℝ) (D3 : ℝ) (D4 : ℝ) (D5 : ℝ) (D6 : ℝ) (D7 : ℝ) (D8 : ℝ) (E : ℝ)
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
      -(1083 / 640 : ℝ) * E *
        energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
  have hw0 : (32 / 25 : ℝ) * E ≤ D0 - (63 / 128 : ℝ) * E := by
    linarith [h0]
  have hw1 : (32 / 25 : ℝ) * E ≤ D1 - (63 / 128 : ℝ) * E := by
    linarith [h1]
  have hw2 : (32 / 25 : ℝ) * E ≤ D2 - (63 / 128 : ℝ) * E := by
    linarith [h2]
  have hw3 : (32 / 25 : ℝ) * E ≤ D3 - (63 / 128 : ℝ) * E := by
    linarith [h3]
  have hw4 : (32 / 25 : ℝ) * E ≤ D4 - (63 / 128 : ℝ) * E := by
    linarith [h4]
  have hw5 : (32 / 25 : ℝ) * E ≤ D5 - (63 / 128 : ℝ) * E := by
    linarith [h5]
  have hw6 : (32 / 25 : ℝ) * E ≤ D6 - (63 / 128 : ℝ) * E := by
    linarith [h6]
  have hw7 : (32 / 25 : ℝ) * E ≤ D7 - (63 / 128 : ℝ) * E := by
    linarith [h7]
  have hw8 : (32 / 25 : ℝ) * E ≤ D8 - (63 / 128 : ℝ) * E := by
    linarith [h8]
  have hweak := nine_value_bound_v1
    z0 z1 z2 z3 z4 z5 z6 z7 z8
    (D0 - (63 / 128 : ℝ) * E) (D1 - (63 / 128 : ℝ) * E) (D2 - (63 / 128 : ℝ) * E) (D3 - (63 / 128 : ℝ) * E) (D4 - (63 / 128 : ℝ) * E) (D5 - (63 / 128 : ℝ) * E) (D6 - (63 / 128 : ℝ) * E) (D7 - (63 / 128 : ℝ) * E) (D8 - (63 / 128 : ℝ) * E)
    E
    b01 b02 b03 b04 b05 b06 b07 b08 b12 b13 b14 b15 b16 b17 b18 b23 b24 b25 b26 b27 b28 b34 b35 b36 b37 b38 b45 b46 b47 b48 b56 b57 b58 b67 b68 b78
    hE hw0 hw1 hw2 hw3 hw4 hw5 hw6 hw7 hw8 h01 h02 h03 h04 h05 h06 h07 h08 h12 h13 h14 h15 h16 h17 h18 h23 h24 h25 h26 h27 h28 h34 h35 h36 h37 h38 h45 h46 h47 h48 h56 h57 h58 h67 h68 h78
  have hdiag :
      -(‖z0‖ ^ 2 * D0 + ‖z1‖ ^ 2 * D1 + ‖z2‖ ^ 2 * D2 +
        ‖z3‖ ^ 2 * D3 + ‖z4‖ ^ 2 * D4 + ‖z5‖ ^ 2 * D5 +
        ‖z6‖ ^ 2 * D6 + ‖z7‖ ^ 2 * D7 + ‖z8‖ ^ 2 * D8) =
      -(‖z0‖ ^ 2 * (D0 - (63 / 128 : ℝ) * E) +
        ‖z1‖ ^ 2 * (D1 - (63 / 128 : ℝ) * E) +
        ‖z2‖ ^ 2 * (D2 - (63 / 128 : ℝ) * E) +
        ‖z3‖ ^ 2 * (D3 - (63 / 128 : ℝ) * E) +
        ‖z4‖ ^ 2 * (D4 - (63 / 128 : ℝ) * E) +
        ‖z5‖ ^ 2 * (D5 - (63 / 128 : ℝ) * E) +
        ‖z6‖ ^ 2 * (D6 - (63 / 128 : ℝ) * E) +
        ‖z7‖ ^ 2 * (D7 - (63 / 128 : ℝ) * E) +
        ‖z8‖ ^ 2 * (D8 - (63 / 128 : ℝ) * E)) -
        (63 / 128 : ℝ) * E *
          energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
    unfold energy9
    ring
  have hidentity :
      nineValue z0 z1 z2 z3 z4 z5 z6 z7 z8 D0 D1 D2 D3 D4 D5 D6 D7 D8 b01 b02 b03 b04 b05 b06 b07 b08 b12 b13 b14 b15 b16 b17 b18 b23 b24 b25 b26 b27 b28 b34 b35 b36 b37 b38 b45 b46 b47 b48 b56 b57 b58 b67 b68 b78 =
        nineValue z0 z1 z2 z3 z4 z5 z6 z7 z8 (D0 - (63 / 128 : ℝ) * E) (D1 - (63 / 128 : ℝ) * E) (D2 - (63 / 128 : ℝ) * E) (D3 - (63 / 128 : ℝ) * E) (D4 - (63 / 128 : ℝ) * E) (D5 - (63 / 128 : ℝ) * E) (D6 - (63 / 128 : ℝ) * E) (D7 - (63 / 128 : ℝ) * E) (D8 - (63 / 128 : ℝ) * E) b01 b02 b03 b04 b05 b06 b07 b08 b12 b13 b14 b15 b16 b17 b18 b23 b24 b25 b26 b27 b28 b34 b35 b36 b37 b38 b45 b46 b47 b48 b56 b57 b58 b67 b68 b78 -
          (63 / 128 : ℝ) * E * energy9 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ := by
    unfold nineValue
    rw [hdiag]
    abel
  rw [hidentity]
  linarith only [hweak]

end AEGIS.RHNineBlockFineBridgeV1

#print axioms AEGIS.RHNineBlockFineBridgeV1.nine_value_bound_fine_v1
