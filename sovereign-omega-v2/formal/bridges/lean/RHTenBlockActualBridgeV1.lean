import RHTenBlockComparisonV1
import Mathlib.Tactic

/-!
AEGIS Omega -- conditional complex ten-block comparison bridge V1.

This module turns ten diagonal lower bounds, forty-four baseline off-diagonal
norm bounds, and one distinguished endpoint off-diagonal norm bound into the
exact 3591/3200 coercivity margin supplied by RHTenBlockComparisonV1.

Hypotheses:
- every diagonal >= 5671/3200 E;
- every off-diagonal except (0,9) has norm <= 1/100 E;
- endpoint pair (0,9) has norm <= 57/100 E.

This is finite complex algebra only. It does not prove that any repository
packet family satisfies the hypotheses.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Complex
open scoped ComplexConjugate

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHTenBlockActualBridgeV1

open AEGIS.RHTenBlockComparisonV1

def tenValue (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) (z9 : ℂ) (D0 : ℝ) (D1 : ℝ) (D2 : ℝ) (D3 : ℝ) (D4 : ℝ) (D5 : ℝ) (D6 : ℝ) (D7 : ℝ) (D8 : ℝ) (D9 : ℝ)
    (b01 : ℂ) (b02 : ℂ) (b03 : ℂ) (b04 : ℂ) (b05 : ℂ) (b06 : ℂ) (b07 : ℂ) (b08 : ℂ) (b09 : ℂ) (b12 : ℂ) (b13 : ℂ) (b14 : ℂ) (b15 : ℂ) (b16 : ℂ) (b17 : ℂ) (b18 : ℂ) (b19 : ℂ) (b23 : ℂ) (b24 : ℂ) (b25 : ℂ) (b26 : ℂ) (b27 : ℂ) (b28 : ℂ) (b29 : ℂ) (b34 : ℂ) (b35 : ℂ) (b36 : ℂ) (b37 : ℂ) (b38 : ℂ) (b39 : ℂ) (b45 : ℂ) (b46 : ℂ) (b47 : ℂ) (b48 : ℂ) (b49 : ℂ) (b56 : ℂ) (b57 : ℂ) (b58 : ℂ) (b59 : ℂ) (b67 : ℂ) (b68 : ℂ) (b69 : ℂ) (b78 : ℂ) (b79 : ℂ) (b89 : ℂ) : ℝ :=
  -(‖z0‖ ^ 2 * D0 + ‖z1‖ ^ 2 * D1 + ‖z2‖ ^ 2 * D2 + ‖z3‖ ^ 2 * D3 + ‖z4‖ ^ 2 * D4 + ‖z5‖ ^ 2 * D5 + ‖z6‖ ^ 2 * D6 + ‖z7‖ ^ 2 * D7 + ‖z8‖ ^ 2 * D8 + ‖z9‖ ^ 2 * D9) +
  2 * ((z0 * star z1 * b01).re +
       (z0 * star z2 * b02).re +
       (z0 * star z3 * b03).re +
       (z0 * star z4 * b04).re +
       (z0 * star z5 * b05).re +
       (z0 * star z6 * b06).re +
       (z0 * star z7 * b07).re +
       (z0 * star z8 * b08).re +
       (z0 * star z9 * b09).re +
       (z1 * star z2 * b12).re +
       (z1 * star z3 * b13).re +
       (z1 * star z4 * b14).re +
       (z1 * star z5 * b15).re +
       (z1 * star z6 * b16).re +
       (z1 * star z7 * b17).re +
       (z1 * star z8 * b18).re +
       (z1 * star z9 * b19).re +
       (z2 * star z3 * b23).re +
       (z2 * star z4 * b24).re +
       (z2 * star z5 * b25).re +
       (z2 * star z6 * b26).re +
       (z2 * star z7 * b27).re +
       (z2 * star z8 * b28).re +
       (z2 * star z9 * b29).re +
       (z3 * star z4 * b34).re +
       (z3 * star z5 * b35).re +
       (z3 * star z6 * b36).re +
       (z3 * star z7 * b37).re +
       (z3 * star z8 * b38).re +
       (z3 * star z9 * b39).re +
       (z4 * star z5 * b45).re +
       (z4 * star z6 * b46).re +
       (z4 * star z7 * b47).re +
       (z4 * star z8 * b48).re +
       (z4 * star z9 * b49).re +
       (z5 * star z6 * b56).re +
       (z5 * star z7 * b57).re +
       (z5 * star z8 * b58).re +
       (z5 * star z9 * b59).re +
       (z6 * star z7 * b67).re +
       (z6 * star z8 * b68).re +
       (z6 * star z9 * b69).re +
       (z7 * star z8 * b78).re +
       (z7 * star z9 * b79).re +
       (z8 * star z9 * b89).re)

theorem pair_re_le_ten_v1
    (z w b : ℂ) (c E : ℝ) (hb : ‖b‖ ≤ c * E) :
    (z * star w * b).re ≤ c * E * ‖z‖ * ‖w‖ := by
  calc
    (z * star w * b).re ≤ ‖z * star w * b‖ := Complex.re_le_norm _
    _ = (‖z‖ * ‖w‖) * ‖b‖ := by simp only [norm_mul, norm_star]
    _ ≤ (‖z‖ * ‖w‖) * (c * E) :=
      mul_le_mul_of_nonneg_left hb
        (mul_nonneg (norm_nonneg _) (norm_nonneg _))
    _ = c * E * ‖z‖ * ‖w‖ := by ring

theorem ten_value_bound_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) (z9 : ℂ) (D0 : ℝ) (D1 : ℝ) (D2 : ℝ) (D3 : ℝ) (D4 : ℝ) (D5 : ℝ) (D6 : ℝ) (D7 : ℝ) (D8 : ℝ) (D9 : ℝ) (E : ℝ)
    (b01 : ℂ) (b02 : ℂ) (b03 : ℂ) (b04 : ℂ) (b05 : ℂ) (b06 : ℂ) (b07 : ℂ) (b08 : ℂ) (b09 : ℂ) (b12 : ℂ) (b13 : ℂ) (b14 : ℂ) (b15 : ℂ) (b16 : ℂ) (b17 : ℂ) (b18 : ℂ) (b19 : ℂ) (b23 : ℂ) (b24 : ℂ) (b25 : ℂ) (b26 : ℂ) (b27 : ℂ) (b28 : ℂ) (b29 : ℂ) (b34 : ℂ) (b35 : ℂ) (b36 : ℂ) (b37 : ℂ) (b38 : ℂ) (b39 : ℂ) (b45 : ℂ) (b46 : ℂ) (b47 : ℂ) (b48 : ℂ) (b49 : ℂ) (b56 : ℂ) (b57 : ℂ) (b58 : ℂ) (b59 : ℂ) (b67 : ℂ) (b68 : ℂ) (b69 : ℂ) (b78 : ℂ) (b79 : ℂ) (b89 : ℂ)
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
    (h9 : (5671 / 3200 : ℝ) * E ≤ D9)
    (h01 : ‖b01‖ ≤ (1 / 100 : ℝ) * E)
    (h02 : ‖b02‖ ≤ (1 / 100 : ℝ) * E)
    (h03 : ‖b03‖ ≤ (1 / 100 : ℝ) * E)
    (h04 : ‖b04‖ ≤ (1 / 100 : ℝ) * E)
    (h05 : ‖b05‖ ≤ (1 / 100 : ℝ) * E)
    (h06 : ‖b06‖ ≤ (1 / 100 : ℝ) * E)
    (h07 : ‖b07‖ ≤ (1 / 100 : ℝ) * E)
    (h08 : ‖b08‖ ≤ (1 / 100 : ℝ) * E)
    (h09 : ‖b09‖ ≤ (57 / 100 : ℝ) * E)
    (h12 : ‖b12‖ ≤ (1 / 100 : ℝ) * E)
    (h13 : ‖b13‖ ≤ (1 / 100 : ℝ) * E)
    (h14 : ‖b14‖ ≤ (1 / 100 : ℝ) * E)
    (h15 : ‖b15‖ ≤ (1 / 100 : ℝ) * E)
    (h16 : ‖b16‖ ≤ (1 / 100 : ℝ) * E)
    (h17 : ‖b17‖ ≤ (1 / 100 : ℝ) * E)
    (h18 : ‖b18‖ ≤ (1 / 100 : ℝ) * E)
    (h19 : ‖b19‖ ≤ (1 / 100 : ℝ) * E)
    (h23 : ‖b23‖ ≤ (1 / 100 : ℝ) * E)
    (h24 : ‖b24‖ ≤ (1 / 100 : ℝ) * E)
    (h25 : ‖b25‖ ≤ (1 / 100 : ℝ) * E)
    (h26 : ‖b26‖ ≤ (1 / 100 : ℝ) * E)
    (h27 : ‖b27‖ ≤ (1 / 100 : ℝ) * E)
    (h28 : ‖b28‖ ≤ (1 / 100 : ℝ) * E)
    (h29 : ‖b29‖ ≤ (1 / 100 : ℝ) * E)
    (h34 : ‖b34‖ ≤ (1 / 100 : ℝ) * E)
    (h35 : ‖b35‖ ≤ (1 / 100 : ℝ) * E)
    (h36 : ‖b36‖ ≤ (1 / 100 : ℝ) * E)
    (h37 : ‖b37‖ ≤ (1 / 100 : ℝ) * E)
    (h38 : ‖b38‖ ≤ (1 / 100 : ℝ) * E)
    (h39 : ‖b39‖ ≤ (1 / 100 : ℝ) * E)
    (h45 : ‖b45‖ ≤ (1 / 100 : ℝ) * E)
    (h46 : ‖b46‖ ≤ (1 / 100 : ℝ) * E)
    (h47 : ‖b47‖ ≤ (1 / 100 : ℝ) * E)
    (h48 : ‖b48‖ ≤ (1 / 100 : ℝ) * E)
    (h49 : ‖b49‖ ≤ (1 / 100 : ℝ) * E)
    (h56 : ‖b56‖ ≤ (1 / 100 : ℝ) * E)
    (h57 : ‖b57‖ ≤ (1 / 100 : ℝ) * E)
    (h58 : ‖b58‖ ≤ (1 / 100 : ℝ) * E)
    (h59 : ‖b59‖ ≤ (1 / 100 : ℝ) * E)
    (h67 : ‖b67‖ ≤ (1 / 100 : ℝ) * E)
    (h68 : ‖b68‖ ≤ (1 / 100 : ℝ) * E)
    (h69 : ‖b69‖ ≤ (1 / 100 : ℝ) * E)
    (h78 : ‖b78‖ ≤ (1 / 100 : ℝ) * E)
    (h79 : ‖b79‖ ≤ (1 / 100 : ℝ) * E)
    (h89 : ‖b89‖ ≤ (1 / 100 : ℝ) * E) :
    tenValue z0 z1 z2 z3 z4 z5 z6 z7 z8 z9 D0 D1 D2 D3 D4 D5 D6 D7 D8 D9 b01 b02 b03 b04 b05 b06 b07 b08 b09 b12 b13 b14 b15 b16 b17 b18 b19 b23 b24 b25 b26 b27 b28 b29 b34 b35 b36 b37 b38 b39 b45 b46 b47 b48 b49 b56 b57 b58 b59 b67 b68 b69 b78 b79 b89 ≤
      -(3591 / 3200 : ℝ) * E *
        energy10 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ := by
  have hd0 := mul_le_mul_of_nonneg_left h0 (sq_nonneg ‖z0‖)
  have hd1 := mul_le_mul_of_nonneg_left h1 (sq_nonneg ‖z1‖)
  have hd2 := mul_le_mul_of_nonneg_left h2 (sq_nonneg ‖z2‖)
  have hd3 := mul_le_mul_of_nonneg_left h3 (sq_nonneg ‖z3‖)
  have hd4 := mul_le_mul_of_nonneg_left h4 (sq_nonneg ‖z4‖)
  have hd5 := mul_le_mul_of_nonneg_left h5 (sq_nonneg ‖z5‖)
  have hd6 := mul_le_mul_of_nonneg_left h6 (sq_nonneg ‖z6‖)
  have hd7 := mul_le_mul_of_nonneg_left h7 (sq_nonneg ‖z7‖)
  have hd8 := mul_le_mul_of_nonneg_left h8 (sq_nonneg ‖z8‖)
  have hd9 := mul_le_mul_of_nonneg_left h9 (sq_nonneg ‖z9‖)
  have hp01 := pair_re_le_ten_v1 z0 z1 b01 (1 / 100) E h01
  have hp02 := pair_re_le_ten_v1 z0 z2 b02 (1 / 100) E h02
  have hp03 := pair_re_le_ten_v1 z0 z3 b03 (1 / 100) E h03
  have hp04 := pair_re_le_ten_v1 z0 z4 b04 (1 / 100) E h04
  have hp05 := pair_re_le_ten_v1 z0 z5 b05 (1 / 100) E h05
  have hp06 := pair_re_le_ten_v1 z0 z6 b06 (1 / 100) E h06
  have hp07 := pair_re_le_ten_v1 z0 z7 b07 (1 / 100) E h07
  have hp08 := pair_re_le_ten_v1 z0 z8 b08 (1 / 100) E h08
  have hp09 := pair_re_le_ten_v1 z0 z9 b09 (57 / 100) E h09
  have hp12 := pair_re_le_ten_v1 z1 z2 b12 (1 / 100) E h12
  have hp13 := pair_re_le_ten_v1 z1 z3 b13 (1 / 100) E h13
  have hp14 := pair_re_le_ten_v1 z1 z4 b14 (1 / 100) E h14
  have hp15 := pair_re_le_ten_v1 z1 z5 b15 (1 / 100) E h15
  have hp16 := pair_re_le_ten_v1 z1 z6 b16 (1 / 100) E h16
  have hp17 := pair_re_le_ten_v1 z1 z7 b17 (1 / 100) E h17
  have hp18 := pair_re_le_ten_v1 z1 z8 b18 (1 / 100) E h18
  have hp19 := pair_re_le_ten_v1 z1 z9 b19 (1 / 100) E h19
  have hp23 := pair_re_le_ten_v1 z2 z3 b23 (1 / 100) E h23
  have hp24 := pair_re_le_ten_v1 z2 z4 b24 (1 / 100) E h24
  have hp25 := pair_re_le_ten_v1 z2 z5 b25 (1 / 100) E h25
  have hp26 := pair_re_le_ten_v1 z2 z6 b26 (1 / 100) E h26
  have hp27 := pair_re_le_ten_v1 z2 z7 b27 (1 / 100) E h27
  have hp28 := pair_re_le_ten_v1 z2 z8 b28 (1 / 100) E h28
  have hp29 := pair_re_le_ten_v1 z2 z9 b29 (1 / 100) E h29
  have hp34 := pair_re_le_ten_v1 z3 z4 b34 (1 / 100) E h34
  have hp35 := pair_re_le_ten_v1 z3 z5 b35 (1 / 100) E h35
  have hp36 := pair_re_le_ten_v1 z3 z6 b36 (1 / 100) E h36
  have hp37 := pair_re_le_ten_v1 z3 z7 b37 (1 / 100) E h37
  have hp38 := pair_re_le_ten_v1 z3 z8 b38 (1 / 100) E h38
  have hp39 := pair_re_le_ten_v1 z3 z9 b39 (1 / 100) E h39
  have hp45 := pair_re_le_ten_v1 z4 z5 b45 (1 / 100) E h45
  have hp46 := pair_re_le_ten_v1 z4 z6 b46 (1 / 100) E h46
  have hp47 := pair_re_le_ten_v1 z4 z7 b47 (1 / 100) E h47
  have hp48 := pair_re_le_ten_v1 z4 z8 b48 (1 / 100) E h48
  have hp49 := pair_re_le_ten_v1 z4 z9 b49 (1 / 100) E h49
  have hp56 := pair_re_le_ten_v1 z5 z6 b56 (1 / 100) E h56
  have hp57 := pair_re_le_ten_v1 z5 z7 b57 (1 / 100) E h57
  have hp58 := pair_re_le_ten_v1 z5 z8 b58 (1 / 100) E h58
  have hp59 := pair_re_le_ten_v1 z5 z9 b59 (1 / 100) E h59
  have hp67 := pair_re_le_ten_v1 z6 z7 b67 (1 / 100) E h67
  have hp68 := pair_re_le_ten_v1 z6 z8 b68 (1 / 100) E h68
  have hp69 := pair_re_le_ten_v1 z6 z9 b69 (1 / 100) E h69
  have hp78 := pair_re_le_ten_v1 z7 z8 b78 (1 / 100) E h78
  have hp79 := pair_re_le_ten_v1 z7 z9 b79 (1 / 100) E h79
  have hp89 := pair_re_le_ten_v1 z8 z9 b89 (1 / 100) E h89
  have hdiag :
      -(‖z0‖ ^ 2 * D0 + ‖z1‖ ^ 2 * D1 + ‖z2‖ ^ 2 * D2 + ‖z3‖ ^ 2 * D3 + ‖z4‖ ^ 2 * D4 + ‖z5‖ ^ 2 * D5 + ‖z6‖ ^ 2 * D6 + ‖z7‖ ^ 2 * D7 + ‖z8‖ ^ 2 * D8 + ‖z9‖ ^ 2 * D9) ≤
        -(5671 / 3200 : ℝ) * E *
          energy10 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ := by
    unfold energy10
    nlinarith only [hd0, hd1, hd2, hd3, hd4, hd5, hd6, hd7, hd8, hd9]
  have hrow0 :
      2 * ((z0 * star z1 * b01).re + (z0 * star z2 * b02).re + (z0 * star z3 * b03).re + (z0 * star z4 * b04).re + (z0 * star z5 * b05).re + (z0 * star z6 * b06).re + (z0 * star z7 * b07).re + (z0 * star z8 * b08).re + (z0 * star z9 * b09).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z0‖ * ‖z1‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z2‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z8‖ + (57 / 100 : ℝ) * ‖z0‖ * ‖z9‖) := by
    nlinarith only [hp01, hp02, hp03, hp04, hp05, hp06, hp07, hp08, hp09]
  have hrow1 :
      2 * ((z1 * star z2 * b12).re + (z1 * star z3 * b13).re + (z1 * star z4 * b14).re + (z1 * star z5 * b15).re + (z1 * star z6 * b16).re + (z1 * star z7 * b17).re + (z1 * star z8 * b18).re + (z1 * star z9 * b19).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z1‖ * ‖z2‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z9‖) := by
    nlinarith only [hp12, hp13, hp14, hp15, hp16, hp17, hp18, hp19]
  have hrow2 :
      2 * ((z2 * star z3 * b23).re + (z2 * star z4 * b24).re + (z2 * star z5 * b25).re + (z2 * star z6 * b26).re + (z2 * star z7 * b27).re + (z2 * star z8 * b28).re + (z2 * star z9 * b29).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z2‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z9‖) := by
    nlinarith only [hp23, hp24, hp25, hp26, hp27, hp28, hp29]
  have hrow3 :
      2 * ((z3 * star z4 * b34).re + (z3 * star z5 * b35).re + (z3 * star z6 * b36).re + (z3 * star z7 * b37).re + (z3 * star z8 * b38).re + (z3 * star z9 * b39).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z3‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z9‖) := by
    nlinarith only [hp34, hp35, hp36, hp37, hp38, hp39]
  have hrow4 :
      2 * ((z4 * star z5 * b45).re + (z4 * star z6 * b46).re + (z4 * star z7 * b47).re + (z4 * star z8 * b48).re + (z4 * star z9 * b49).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z4‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z9‖) := by
    nlinarith only [hp45, hp46, hp47, hp48, hp49]
  have hrow5 :
      2 * ((z5 * star z6 * b56).re + (z5 * star z7 * b57).re + (z5 * star z8 * b58).re + (z5 * star z9 * b59).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z5‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z9‖) := by
    nlinarith only [hp56, hp57, hp58, hp59]
  have hrow6 :
      2 * ((z6 * star z7 * b67).re + (z6 * star z8 * b68).re + (z6 * star z9 * b69).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z6‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z6‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z6‖ * ‖z9‖) := by
    nlinarith only [hp67, hp68, hp69]
  have hrow7 :
      2 * ((z7 * star z8 * b78).re + (z7 * star z9 * b79).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z7‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z7‖ * ‖z9‖) := by
    nlinarith only [hp78, hp79]
  have hrow8 :
      2 * ((z8 * star z9 * b89).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z8‖ * ‖z9‖) := by
    nlinarith only [hp89]
  have hcross :
      2 * ((z0 * star z1 * b01).re +
       (z0 * star z2 * b02).re +
       (z0 * star z3 * b03).re +
       (z0 * star z4 * b04).re +
       (z0 * star z5 * b05).re +
       (z0 * star z6 * b06).re +
       (z0 * star z7 * b07).re +
       (z0 * star z8 * b08).re +
       (z0 * star z9 * b09).re +
       (z1 * star z2 * b12).re +
       (z1 * star z3 * b13).re +
       (z1 * star z4 * b14).re +
       (z1 * star z5 * b15).re +
       (z1 * star z6 * b16).re +
       (z1 * star z7 * b17).re +
       (z1 * star z8 * b18).re +
       (z1 * star z9 * b19).re +
       (z2 * star z3 * b23).re +
       (z2 * star z4 * b24).re +
       (z2 * star z5 * b25).re +
       (z2 * star z6 * b26).re +
       (z2 * star z7 * b27).re +
       (z2 * star z8 * b28).re +
       (z2 * star z9 * b29).re +
       (z3 * star z4 * b34).re +
       (z3 * star z5 * b35).re +
       (z3 * star z6 * b36).re +
       (z3 * star z7 * b37).re +
       (z3 * star z8 * b38).re +
       (z3 * star z9 * b39).re +
       (z4 * star z5 * b45).re +
       (z4 * star z6 * b46).re +
       (z4 * star z7 * b47).re +
       (z4 * star z8 * b48).re +
       (z4 * star z9 * b49).re +
       (z5 * star z6 * b56).re +
       (z5 * star z7 * b57).re +
       (z5 * star z8 * b58).re +
       (z5 * star z9 * b59).re +
       (z6 * star z7 * b67).re +
       (z6 * star z8 * b68).re +
       (z6 * star z9 * b69).re +
       (z7 * star z8 * b78).re +
       (z7 * star z9 * b79).re +
       (z8 * star z9 * b89).re) ≤
        E * cross10 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ := by
    unfold cross10 pairSum10
    nlinarith only [hrow0, hrow1, hrow2, hrow3, hrow4, hrow5, hrow6, hrow7, hrow8]
  have hvalue := add_le_add hdiag hcross
  have hc := mul_le_mul_of_nonneg_left
    (cross_ten_le_thirteen_over_twenty_v1 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖) hE
  calc
    tenValue z0 z1 z2 z3 z4 z5 z6 z7 z8 z9 D0 D1 D2 D3 D4 D5 D6 D7 D8 D9 b01 b02 b03 b04 b05 b06 b07 b08 b09 b12 b13 b14 b15 b16 b17 b18 b19 b23 b24 b25 b26 b27 b28 b29 b34 b35 b36 b37 b38 b39 b45 b46 b47 b48 b49 b56 b57 b58 b59 b67 b68 b69 b78 b79 b89 ≤
        -(5671 / 3200 : ℝ) * E * energy10 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ +
          E * cross10 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ := by
      simpa [tenValue] using hvalue
    _ ≤ -(3591 / 3200 : ℝ) * E * energy10 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ := by
      nlinarith only [hc]

end AEGIS.RHTenBlockActualBridgeV1

#print axioms AEGIS.RHTenBlockActualBridgeV1.pair_re_le_ten_v1
#print axioms AEGIS.RHTenBlockActualBridgeV1.ten_value_bound_v1
