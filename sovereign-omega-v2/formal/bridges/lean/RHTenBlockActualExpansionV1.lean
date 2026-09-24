import RHTenBlockActualBridgeV1
import WeilMixedAlgebraV2
import Mathlib.Tactic

/-!
AEGIS Omega -- actual repository B expansion for ten packets V1.

This module binds the abstract ten-block value to the actual AEGIS arithmetic
form B. It proves an exact ten-packet expansion and then applies the conditional
3591/3200 comparison theorem when ten diagonal, forty-four baseline cross, and
one endpoint cross hypothesis are supplied.

No analytic hypothesis is discharged here.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Complex
open scoped ComplexConjugate

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHTenBlockActualExpansionV1

open AEGIS.WeilMixedAlgebraV2
open AEGIS.RHTenBlockComparisonV1
open AEGIS.RHTenBlockActualBridgeV1

def combo10 (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) (z9 : ℂ)
    (g0 : WeilCompactSmoothGV1) (g1 : WeilCompactSmoothGV1) (g2 : WeilCompactSmoothGV1) (g3 : WeilCompactSmoothGV1) (g4 : WeilCompactSmoothGV1) (g5 : WeilCompactSmoothGV1) (g6 : WeilCompactSmoothGV1) (g7 : WeilCompactSmoothGV1) (g8 : WeilCompactSmoothGV1) (g9 : WeilCompactSmoothGV1) : WeilCompactSmoothGV1 :=
  addPacket (scalePacket z0 g0) (addPacket (scalePacket z1 g1) (addPacket (scalePacket z2 g2) (addPacket (scalePacket z3 g3) (addPacket (scalePacket z4 g4) (addPacket (scalePacket z5 g5) (addPacket (scalePacket z6 g6) (addPacket (scalePacket z7 g7) (addPacket (scalePacket z8 g8) (scalePacket z9 g9)))))))))

private theorem self_im_zero_ten_v1
    (g : WeilCompactSmoothGV1) : (B g g).im = 0 := by
  have h := congrArg Complex.im (B_hermitian g g)
  simp only [Complex.conj_im] at h
  linarith

theorem actual_ten_block_expansion_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) (z9 : ℂ)
    (g0 : WeilCompactSmoothGV1) (g1 : WeilCompactSmoothGV1) (g2 : WeilCompactSmoothGV1) (g3 : WeilCompactSmoothGV1) (g4 : WeilCompactSmoothGV1) (g5 : WeilCompactSmoothGV1) (g6 : WeilCompactSmoothGV1) (g7 : WeilCompactSmoothGV1) (g8 : WeilCompactSmoothGV1) (g9 : WeilCompactSmoothGV1) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (combo10 z0 z1 z2 z3 z4 z5 z6 z7 z8 z9 g0 g1 g2 g3 g4 g5 g6 g7 g8 g9))).re =
    tenValue z0 z1 z2 z3 z4 z5 z6 z7 z8 z9
      (-(B g0 g0).re) (-(B g1 g1).re) (-(B g2 g2).re) (-(B g3 g3).re) (-(B g4 g4).re) (-(B g5 g5).re) (-(B g6 g6).re) (-(B g7 g7).re) (-(B g8 g8).re) (-(B g9 g9).re)
      (B g0 g1) (B g0 g2) (B g0 g3) (B g0 g4) (B g0 g5) (B g0 g6) (B g0 g7) (B g0 g8) (B g0 g9) (B g1 g2) (B g1 g3) (B g1 g4) (B g1 g5) (B g1 g6) (B g1 g7) (B g1 g8) (B g1 g9) (B g2 g3) (B g2 g4) (B g2 g5) (B g2 g6) (B g2 g7) (B g2 g8) (B g2 g9) (B g3 g4) (B g3 g5) (B g3 g6) (B g3 g7) (B g3 g8) (B g3 g9) (B g4 g5) (B g4 g6) (B g4 g7) (B g4 g8) (B g4 g9) (B g5 g6) (B g5 g7) (B g5 g8) (B g5 g9) (B g6 g7) (B g6 g8) (B g6 g9) (B g7 g8) (B g7 g9) (B g8 g9) := by
  change (B (combo10 z0 z1 z2 z3 z4 z5 z6 z7 z8 z9 g0 g1 g2 g3 g4 g5 g6 g7 g8 g9)
    (combo10 z0 z1 z2 z3 z4 z5 z6 z7 z8 z9 g0 g1 g2 g3 g4 g5 g6 g7 g8 g9)).re = _
  unfold combo10
  simp only [B_add_left, B_add_right, B_scale_left, B_scale_right]
  rw [B_hermitian g0 g1,
      B_hermitian g0 g2,
      B_hermitian g0 g3,
      B_hermitian g0 g4,
      B_hermitian g0 g5,
      B_hermitian g0 g6,
      B_hermitian g0 g7,
      B_hermitian g0 g8,
      B_hermitian g0 g9,
      B_hermitian g1 g2,
      B_hermitian g1 g3,
      B_hermitian g1 g4,
      B_hermitian g1 g5,
      B_hermitian g1 g6,
      B_hermitian g1 g7,
      B_hermitian g1 g8,
      B_hermitian g1 g9,
      B_hermitian g2 g3,
      B_hermitian g2 g4,
      B_hermitian g2 g5,
      B_hermitian g2 g6,
      B_hermitian g2 g7,
      B_hermitian g2 g8,
      B_hermitian g2 g9,
      B_hermitian g3 g4,
      B_hermitian g3 g5,
      B_hermitian g3 g6,
      B_hermitian g3 g7,
      B_hermitian g3 g8,
      B_hermitian g3 g9,
      B_hermitian g4 g5,
      B_hermitian g4 g6,
      B_hermitian g4 g7,
      B_hermitian g4 g8,
      B_hermitian g4 g9,
      B_hermitian g5 g6,
      B_hermitian g5 g7,
      B_hermitian g5 g8,
      B_hermitian g5 g9,
      B_hermitian g6 g7,
      B_hermitian g6 g8,
      B_hermitian g6 g9,
      B_hermitian g7 g8,
      B_hermitian g7 g9,
      B_hermitian g8 g9]
  unfold tenValue
  simp only [Complex.star_def, Complex.add_re, Complex.add_im,
    Complex.mul_re, Complex.mul_im, Complex.conj_re, Complex.conj_im,
    Complex.sq_norm, Complex.normSq_apply, self_im_zero_ten_v1]
  ring

theorem actual_ten_block_bound_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) (z9 : ℂ)
    (g0 : WeilCompactSmoothGV1) (g1 : WeilCompactSmoothGV1) (g2 : WeilCompactSmoothGV1) (g3 : WeilCompactSmoothGV1) (g4 : WeilCompactSmoothGV1) (g5 : WeilCompactSmoothGV1) (g6 : WeilCompactSmoothGV1) (g7 : WeilCompactSmoothGV1) (g8 : WeilCompactSmoothGV1) (g9 : WeilCompactSmoothGV1)
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
    (h9 : (5671 / 3200 : ℝ) * E ≤ -(B g9 g9).re)
    (h01 : ‖B g0 g1‖ ≤ (1 / 100 : ℝ) * E)
    (h02 : ‖B g0 g2‖ ≤ (1 / 100 : ℝ) * E)
    (h03 : ‖B g0 g3‖ ≤ (1 / 100 : ℝ) * E)
    (h04 : ‖B g0 g4‖ ≤ (1 / 100 : ℝ) * E)
    (h05 : ‖B g0 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h06 : ‖B g0 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h07 : ‖B g0 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h08 : ‖B g0 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h09 : ‖B g0 g9‖ ≤ (57 / 100 : ℝ) * E)
    (h12 : ‖B g1 g2‖ ≤ (1 / 100 : ℝ) * E)
    (h13 : ‖B g1 g3‖ ≤ (1 / 100 : ℝ) * E)
    (h14 : ‖B g1 g4‖ ≤ (1 / 100 : ℝ) * E)
    (h15 : ‖B g1 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h16 : ‖B g1 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h17 : ‖B g1 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h18 : ‖B g1 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h19 : ‖B g1 g9‖ ≤ (1 / 100 : ℝ) * E)
    (h23 : ‖B g2 g3‖ ≤ (1 / 100 : ℝ) * E)
    (h24 : ‖B g2 g4‖ ≤ (1 / 100 : ℝ) * E)
    (h25 : ‖B g2 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h26 : ‖B g2 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h27 : ‖B g2 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h28 : ‖B g2 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h29 : ‖B g2 g9‖ ≤ (1 / 100 : ℝ) * E)
    (h34 : ‖B g3 g4‖ ≤ (1 / 100 : ℝ) * E)
    (h35 : ‖B g3 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h36 : ‖B g3 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h37 : ‖B g3 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h38 : ‖B g3 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h39 : ‖B g3 g9‖ ≤ (1 / 100 : ℝ) * E)
    (h45 : ‖B g4 g5‖ ≤ (1 / 100 : ℝ) * E)
    (h46 : ‖B g4 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h47 : ‖B g4 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h48 : ‖B g4 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h49 : ‖B g4 g9‖ ≤ (1 / 100 : ℝ) * E)
    (h56 : ‖B g5 g6‖ ≤ (1 / 100 : ℝ) * E)
    (h57 : ‖B g5 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h58 : ‖B g5 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h59 : ‖B g5 g9‖ ≤ (1 / 100 : ℝ) * E)
    (h67 : ‖B g6 g7‖ ≤ (1 / 100 : ℝ) * E)
    (h68 : ‖B g6 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h69 : ‖B g6 g9‖ ≤ (1 / 100 : ℝ) * E)
    (h78 : ‖B g7 g8‖ ≤ (1 / 100 : ℝ) * E)
    (h79 : ‖B g7 g9‖ ≤ (1 / 100 : ℝ) * E)
    (h89 : ‖B g8 g9‖ ≤ (1 / 100 : ℝ) * E) :
    (WeilExplicitRightSideV1
      (WeilAutocorrelationV1
        (combo10 z0 z1 z2 z3 z4 z5 z6 z7 z8 z9 g0 g1 g2 g3 g4 g5 g6 g7 g8 g9))).re ≤
      -(3591 / 3200 : ℝ) * E *
        energy10 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ := by
  rw [actual_ten_block_expansion_v1]
  exact ten_value_bound_v1
    z0 z1 z2 z3 z4 z5 z6 z7 z8 z9
    (-(B g0 g0).re) (-(B g1 g1).re) (-(B g2 g2).re) (-(B g3 g3).re) (-(B g4 g4).re) (-(B g5 g5).re) (-(B g6 g6).re) (-(B g7 g7).re) (-(B g8 g8).re) (-(B g9 g9).re)
    E
    (B g0 g1) (B g0 g2) (B g0 g3) (B g0 g4) (B g0 g5) (B g0 g6) (B g0 g7) (B g0 g8) (B g0 g9) (B g1 g2) (B g1 g3) (B g1 g4) (B g1 g5) (B g1 g6) (B g1 g7) (B g1 g8) (B g1 g9) (B g2 g3) (B g2 g4) (B g2 g5) (B g2 g6) (B g2 g7) (B g2 g8) (B g2 g9) (B g3 g4) (B g3 g5) (B g3 g6) (B g3 g7) (B g3 g8) (B g3 g9) (B g4 g5) (B g4 g6) (B g4 g7) (B g4 g8) (B g4 g9) (B g5 g6) (B g5 g7) (B g5 g8) (B g5 g9) (B g6 g7) (B g6 g8) (B g6 g9) (B g7 g8) (B g7 g9) (B g8 g9)
    hE h0 h1 h2 h3 h4 h5 h6 h7 h8 h9 h01 h02 h03 h04 h05 h06 h07 h08 h09 h12 h13 h14 h15 h16 h17 h18 h19 h23 h24 h25 h26 h27 h28 h29 h34 h35 h36 h37 h38 h39 h45 h46 h47 h48 h49 h56 h57 h58 h59 h67 h68 h69 h78 h79 h89

end AEGIS.RHTenBlockActualExpansionV1

#print axioms AEGIS.RHTenBlockActualExpansionV1.actual_ten_block_expansion_v1
#print axioms AEGIS.RHTenBlockActualExpansionV1.actual_ten_block_bound_v1
