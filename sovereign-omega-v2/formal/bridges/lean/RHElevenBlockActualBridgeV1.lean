import RHElevenBlockComparisonV1
import Mathlib.Tactic

/-!
AEGIS Omega -- conditional complex eleven-block comparison bridge V1.

This module turns eleven diagonal lower bounds and fifty-five off-diagonal
norm bounds into the exact 106083/118400 coercivity margin supplied by
RHElevenBlockComparisonV1.

Cross envelopes:
- gaps 1..8: 1/100 E;
- gap 9: 57/100 E;
- gap 10: 837/3700 E.

This is finite complex algebra only. It does not prove that any repository
packet family satisfies the hypotheses.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Complex
open scoped ComplexConjugate

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHElevenBlockActualBridgeV1

open AEGIS.RHElevenBlockComparisonV1

def elevenValue (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) (z9 : ℂ) (z10 : ℂ) (D0 : ℝ) (D1 : ℝ) (D2 : ℝ) (D3 : ℝ) (D4 : ℝ) (D5 : ℝ) (D6 : ℝ) (D7 : ℝ) (D8 : ℝ) (D9 : ℝ) (D10 : ℝ)
    (b01 : ℂ) (b02 : ℂ) (b03 : ℂ) (b04 : ℂ) (b05 : ℂ) (b06 : ℂ) (b07 : ℂ) (b08 : ℂ) (b09 : ℂ) (b010 : ℂ) (b12 : ℂ) (b13 : ℂ) (b14 : ℂ) (b15 : ℂ) (b16 : ℂ) (b17 : ℂ) (b18 : ℂ) (b19 : ℂ) (b110 : ℂ) (b23 : ℂ) (b24 : ℂ) (b25 : ℂ) (b26 : ℂ) (b27 : ℂ) (b28 : ℂ) (b29 : ℂ) (b210 : ℂ) (b34 : ℂ) (b35 : ℂ) (b36 : ℂ) (b37 : ℂ) (b38 : ℂ) (b39 : ℂ) (b310 : ℂ) (b45 : ℂ) (b46 : ℂ) (b47 : ℂ) (b48 : ℂ) (b49 : ℂ) (b410 : ℂ) (b56 : ℂ) (b57 : ℂ) (b58 : ℂ) (b59 : ℂ) (b510 : ℂ) (b67 : ℂ) (b68 : ℂ) (b69 : ℂ) (b610 : ℂ) (b78 : ℂ) (b79 : ℂ) (b710 : ℂ) (b89 : ℂ) (b810 : ℂ) (b910 : ℂ) : ℝ :=
  -(‖z0‖ ^ 2 * D0 + ‖z1‖ ^ 2 * D1 + ‖z2‖ ^ 2 * D2 + ‖z3‖ ^ 2 * D3 + ‖z4‖ ^ 2 * D4 + ‖z5‖ ^ 2 * D5 + ‖z6‖ ^ 2 * D6 + ‖z7‖ ^ 2 * D7 + ‖z8‖ ^ 2 * D8 + ‖z9‖ ^ 2 * D9 + ‖z10‖ ^ 2 * D10) +
  2 * ((z0 * star z1 * b01).re +
       (z0 * star z2 * b02).re +
       (z0 * star z3 * b03).re +
       (z0 * star z4 * b04).re +
       (z0 * star z5 * b05).re +
       (z0 * star z6 * b06).re +
       (z0 * star z7 * b07).re +
       (z0 * star z8 * b08).re +
       (z0 * star z9 * b09).re +
       (z0 * star z10 * b010).re +
       (z1 * star z2 * b12).re +
       (z1 * star z3 * b13).re +
       (z1 * star z4 * b14).re +
       (z1 * star z5 * b15).re +
       (z1 * star z6 * b16).re +
       (z1 * star z7 * b17).re +
       (z1 * star z8 * b18).re +
       (z1 * star z9 * b19).re +
       (z1 * star z10 * b110).re +
       (z2 * star z3 * b23).re +
       (z2 * star z4 * b24).re +
       (z2 * star z5 * b25).re +
       (z2 * star z6 * b26).re +
       (z2 * star z7 * b27).re +
       (z2 * star z8 * b28).re +
       (z2 * star z9 * b29).re +
       (z2 * star z10 * b210).re +
       (z3 * star z4 * b34).re +
       (z3 * star z5 * b35).re +
       (z3 * star z6 * b36).re +
       (z3 * star z7 * b37).re +
       (z3 * star z8 * b38).re +
       (z3 * star z9 * b39).re +
       (z3 * star z10 * b310).re +
       (z4 * star z5 * b45).re +
       (z4 * star z6 * b46).re +
       (z4 * star z7 * b47).re +
       (z4 * star z8 * b48).re +
       (z4 * star z9 * b49).re +
       (z4 * star z10 * b410).re +
       (z5 * star z6 * b56).re +
       (z5 * star z7 * b57).re +
       (z5 * star z8 * b58).re +
       (z5 * star z9 * b59).re +
       (z5 * star z10 * b510).re +
       (z6 * star z7 * b67).re +
       (z6 * star z8 * b68).re +
       (z6 * star z9 * b69).re +
       (z6 * star z10 * b610).re +
       (z7 * star z8 * b78).re +
       (z7 * star z9 * b79).re +
       (z7 * star z10 * b710).re +
       (z8 * star z9 * b89).re +
       (z8 * star z10 * b810).re +
       (z9 * star z10 * b910).re)

theorem pair_re_le_eleven_v1
    (z w b : ℂ) (c E : ℝ) (hb : ‖b‖ ≤ c * E) :
    (z * star w * b).re ≤ c * E * ‖z‖ * ‖w‖ := by
  calc
    (z * star w * b).re ≤ ‖z * star w * b‖ := Complex.re_le_norm _
    _ = (‖z‖ * ‖w‖) * ‖b‖ := by simp only [norm_mul, norm_star]
    _ ≤ (‖z‖ * ‖w‖) * (c * E) :=
      mul_le_mul_of_nonneg_left hb
        (mul_nonneg (norm_nonneg _) (norm_nonneg _))
    _ = c * E * ‖z‖ * ‖w‖ := by ring

theorem eleven_value_bound_v1
    (z0 : ℂ) (z1 : ℂ) (z2 : ℂ) (z3 : ℂ) (z4 : ℂ) (z5 : ℂ) (z6 : ℂ) (z7 : ℂ) (z8 : ℂ) (z9 : ℂ) (z10 : ℂ) (D0 : ℝ) (D1 : ℝ) (D2 : ℝ) (D3 : ℝ) (D4 : ℝ) (D5 : ℝ) (D6 : ℝ) (D7 : ℝ) (D8 : ℝ) (D9 : ℝ) (D10 : ℝ) (E : ℝ)
    (b01 : ℂ) (b02 : ℂ) (b03 : ℂ) (b04 : ℂ) (b05 : ℂ) (b06 : ℂ) (b07 : ℂ) (b08 : ℂ) (b09 : ℂ) (b010 : ℂ) (b12 : ℂ) (b13 : ℂ) (b14 : ℂ) (b15 : ℂ) (b16 : ℂ) (b17 : ℂ) (b18 : ℂ) (b19 : ℂ) (b110 : ℂ) (b23 : ℂ) (b24 : ℂ) (b25 : ℂ) (b26 : ℂ) (b27 : ℂ) (b28 : ℂ) (b29 : ℂ) (b210 : ℂ) (b34 : ℂ) (b35 : ℂ) (b36 : ℂ) (b37 : ℂ) (b38 : ℂ) (b39 : ℂ) (b310 : ℂ) (b45 : ℂ) (b46 : ℂ) (b47 : ℂ) (b48 : ℂ) (b49 : ℂ) (b410 : ℂ) (b56 : ℂ) (b57 : ℂ) (b58 : ℂ) (b59 : ℂ) (b510 : ℂ) (b67 : ℂ) (b68 : ℂ) (b69 : ℂ) (b610 : ℂ) (b78 : ℂ) (b79 : ℂ) (b710 : ℂ) (b89 : ℂ) (b810 : ℂ) (b910 : ℂ)
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
    (h10 : (5671 / 3200 : ℝ) * E ≤ D10)
    (h01 : ‖b01‖ ≤ (1 / 100 : ℝ) * E)
    (h02 : ‖b02‖ ≤ (1 / 100 : ℝ) * E)
    (h03 : ‖b03‖ ≤ (1 / 100 : ℝ) * E)
    (h04 : ‖b04‖ ≤ (1 / 100 : ℝ) * E)
    (h05 : ‖b05‖ ≤ (1 / 100 : ℝ) * E)
    (h06 : ‖b06‖ ≤ (1 / 100 : ℝ) * E)
    (h07 : ‖b07‖ ≤ (1 / 100 : ℝ) * E)
    (h08 : ‖b08‖ ≤ (1 / 100 : ℝ) * E)
    (h09 : ‖b09‖ ≤ (57 / 100 : ℝ) * E)
    (h010 : ‖b010‖ ≤ (837 / 3700 : ℝ) * E)
    (h12 : ‖b12‖ ≤ (1 / 100 : ℝ) * E)
    (h13 : ‖b13‖ ≤ (1 / 100 : ℝ) * E)
    (h14 : ‖b14‖ ≤ (1 / 100 : ℝ) * E)
    (h15 : ‖b15‖ ≤ (1 / 100 : ℝ) * E)
    (h16 : ‖b16‖ ≤ (1 / 100 : ℝ) * E)
    (h17 : ‖b17‖ ≤ (1 / 100 : ℝ) * E)
    (h18 : ‖b18‖ ≤ (1 / 100 : ℝ) * E)
    (h19 : ‖b19‖ ≤ (1 / 100 : ℝ) * E)
    (h110 : ‖b110‖ ≤ (57 / 100 : ℝ) * E)
    (h23 : ‖b23‖ ≤ (1 / 100 : ℝ) * E)
    (h24 : ‖b24‖ ≤ (1 / 100 : ℝ) * E)
    (h25 : ‖b25‖ ≤ (1 / 100 : ℝ) * E)
    (h26 : ‖b26‖ ≤ (1 / 100 : ℝ) * E)
    (h27 : ‖b27‖ ≤ (1 / 100 : ℝ) * E)
    (h28 : ‖b28‖ ≤ (1 / 100 : ℝ) * E)
    (h29 : ‖b29‖ ≤ (1 / 100 : ℝ) * E)
    (h210 : ‖b210‖ ≤ (1 / 100 : ℝ) * E)
    (h34 : ‖b34‖ ≤ (1 / 100 : ℝ) * E)
    (h35 : ‖b35‖ ≤ (1 / 100 : ℝ) * E)
    (h36 : ‖b36‖ ≤ (1 / 100 : ℝ) * E)
    (h37 : ‖b37‖ ≤ (1 / 100 : ℝ) * E)
    (h38 : ‖b38‖ ≤ (1 / 100 : ℝ) * E)
    (h39 : ‖b39‖ ≤ (1 / 100 : ℝ) * E)
    (h310 : ‖b310‖ ≤ (1 / 100 : ℝ) * E)
    (h45 : ‖b45‖ ≤ (1 / 100 : ℝ) * E)
    (h46 : ‖b46‖ ≤ (1 / 100 : ℝ) * E)
    (h47 : ‖b47‖ ≤ (1 / 100 : ℝ) * E)
    (h48 : ‖b48‖ ≤ (1 / 100 : ℝ) * E)
    (h49 : ‖b49‖ ≤ (1 / 100 : ℝ) * E)
    (h410 : ‖b410‖ ≤ (1 / 100 : ℝ) * E)
    (h56 : ‖b56‖ ≤ (1 / 100 : ℝ) * E)
    (h57 : ‖b57‖ ≤ (1 / 100 : ℝ) * E)
    (h58 : ‖b58‖ ≤ (1 / 100 : ℝ) * E)
    (h59 : ‖b59‖ ≤ (1 / 100 : ℝ) * E)
    (h510 : ‖b510‖ ≤ (1 / 100 : ℝ) * E)
    (h67 : ‖b67‖ ≤ (1 / 100 : ℝ) * E)
    (h68 : ‖b68‖ ≤ (1 / 100 : ℝ) * E)
    (h69 : ‖b69‖ ≤ (1 / 100 : ℝ) * E)
    (h610 : ‖b610‖ ≤ (1 / 100 : ℝ) * E)
    (h78 : ‖b78‖ ≤ (1 / 100 : ℝ) * E)
    (h79 : ‖b79‖ ≤ (1 / 100 : ℝ) * E)
    (h710 : ‖b710‖ ≤ (1 / 100 : ℝ) * E)
    (h89 : ‖b89‖ ≤ (1 / 100 : ℝ) * E)
    (h810 : ‖b810‖ ≤ (1 / 100 : ℝ) * E)
    (h910 : ‖b910‖ ≤ (1 / 100 : ℝ) * E) :
    elevenValue z0 z1 z2 z3 z4 z5 z6 z7 z8 z9 z10 D0 D1 D2 D3 D4 D5 D6 D7 D8 D9 D10 b01 b02 b03 b04 b05 b06 b07 b08 b09 b010 b12 b13 b14 b15 b16 b17 b18 b19 b110 b23 b24 b25 b26 b27 b28 b29 b210 b34 b35 b36 b37 b38 b39 b310 b45 b46 b47 b48 b49 b410 b56 b57 b58 b59 b510 b67 b68 b69 b610 b78 b79 b710 b89 b810 b910 ≤
      -(106083 / 118400 : ℝ) * E *
        energy11 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ ‖z10‖ := by
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
  have hd10 := mul_le_mul_of_nonneg_left h10 (sq_nonneg ‖z10‖)
  have hp01 := pair_re_le_eleven_v1 z0 z1 b01 (1 / 100) E h01
  have hp02 := pair_re_le_eleven_v1 z0 z2 b02 (1 / 100) E h02
  have hp03 := pair_re_le_eleven_v1 z0 z3 b03 (1 / 100) E h03
  have hp04 := pair_re_le_eleven_v1 z0 z4 b04 (1 / 100) E h04
  have hp05 := pair_re_le_eleven_v1 z0 z5 b05 (1 / 100) E h05
  have hp06 := pair_re_le_eleven_v1 z0 z6 b06 (1 / 100) E h06
  have hp07 := pair_re_le_eleven_v1 z0 z7 b07 (1 / 100) E h07
  have hp08 := pair_re_le_eleven_v1 z0 z8 b08 (1 / 100) E h08
  have hp09 := pair_re_le_eleven_v1 z0 z9 b09 (57 / 100) E h09
  have hp010 := pair_re_le_eleven_v1 z0 z10 b010 (837 / 3700) E h010
  have hp12 := pair_re_le_eleven_v1 z1 z2 b12 (1 / 100) E h12
  have hp13 := pair_re_le_eleven_v1 z1 z3 b13 (1 / 100) E h13
  have hp14 := pair_re_le_eleven_v1 z1 z4 b14 (1 / 100) E h14
  have hp15 := pair_re_le_eleven_v1 z1 z5 b15 (1 / 100) E h15
  have hp16 := pair_re_le_eleven_v1 z1 z6 b16 (1 / 100) E h16
  have hp17 := pair_re_le_eleven_v1 z1 z7 b17 (1 / 100) E h17
  have hp18 := pair_re_le_eleven_v1 z1 z8 b18 (1 / 100) E h18
  have hp19 := pair_re_le_eleven_v1 z1 z9 b19 (1 / 100) E h19
  have hp110 := pair_re_le_eleven_v1 z1 z10 b110 (57 / 100) E h110
  have hp23 := pair_re_le_eleven_v1 z2 z3 b23 (1 / 100) E h23
  have hp24 := pair_re_le_eleven_v1 z2 z4 b24 (1 / 100) E h24
  have hp25 := pair_re_le_eleven_v1 z2 z5 b25 (1 / 100) E h25
  have hp26 := pair_re_le_eleven_v1 z2 z6 b26 (1 / 100) E h26
  have hp27 := pair_re_le_eleven_v1 z2 z7 b27 (1 / 100) E h27
  have hp28 := pair_re_le_eleven_v1 z2 z8 b28 (1 / 100) E h28
  have hp29 := pair_re_le_eleven_v1 z2 z9 b29 (1 / 100) E h29
  have hp210 := pair_re_le_eleven_v1 z2 z10 b210 (1 / 100) E h210
  have hp34 := pair_re_le_eleven_v1 z3 z4 b34 (1 / 100) E h34
  have hp35 := pair_re_le_eleven_v1 z3 z5 b35 (1 / 100) E h35
  have hp36 := pair_re_le_eleven_v1 z3 z6 b36 (1 / 100) E h36
  have hp37 := pair_re_le_eleven_v1 z3 z7 b37 (1 / 100) E h37
  have hp38 := pair_re_le_eleven_v1 z3 z8 b38 (1 / 100) E h38
  have hp39 := pair_re_le_eleven_v1 z3 z9 b39 (1 / 100) E h39
  have hp310 := pair_re_le_eleven_v1 z3 z10 b310 (1 / 100) E h310
  have hp45 := pair_re_le_eleven_v1 z4 z5 b45 (1 / 100) E h45
  have hp46 := pair_re_le_eleven_v1 z4 z6 b46 (1 / 100) E h46
  have hp47 := pair_re_le_eleven_v1 z4 z7 b47 (1 / 100) E h47
  have hp48 := pair_re_le_eleven_v1 z4 z8 b48 (1 / 100) E h48
  have hp49 := pair_re_le_eleven_v1 z4 z9 b49 (1 / 100) E h49
  have hp410 := pair_re_le_eleven_v1 z4 z10 b410 (1 / 100) E h410
  have hp56 := pair_re_le_eleven_v1 z5 z6 b56 (1 / 100) E h56
  have hp57 := pair_re_le_eleven_v1 z5 z7 b57 (1 / 100) E h57
  have hp58 := pair_re_le_eleven_v1 z5 z8 b58 (1 / 100) E h58
  have hp59 := pair_re_le_eleven_v1 z5 z9 b59 (1 / 100) E h59
  have hp510 := pair_re_le_eleven_v1 z5 z10 b510 (1 / 100) E h510
  have hp67 := pair_re_le_eleven_v1 z6 z7 b67 (1 / 100) E h67
  have hp68 := pair_re_le_eleven_v1 z6 z8 b68 (1 / 100) E h68
  have hp69 := pair_re_le_eleven_v1 z6 z9 b69 (1 / 100) E h69
  have hp610 := pair_re_le_eleven_v1 z6 z10 b610 (1 / 100) E h610
  have hp78 := pair_re_le_eleven_v1 z7 z8 b78 (1 / 100) E h78
  have hp79 := pair_re_le_eleven_v1 z7 z9 b79 (1 / 100) E h79
  have hp710 := pair_re_le_eleven_v1 z7 z10 b710 (1 / 100) E h710
  have hp89 := pair_re_le_eleven_v1 z8 z9 b89 (1 / 100) E h89
  have hp810 := pair_re_le_eleven_v1 z8 z10 b810 (1 / 100) E h810
  have hp910 := pair_re_le_eleven_v1 z9 z10 b910 (1 / 100) E h910
  have hdiag :
      -(‖z0‖ ^ 2 * D0 + ‖z1‖ ^ 2 * D1 + ‖z2‖ ^ 2 * D2 + ‖z3‖ ^ 2 * D3 + ‖z4‖ ^ 2 * D4 + ‖z5‖ ^ 2 * D5 + ‖z6‖ ^ 2 * D6 + ‖z7‖ ^ 2 * D7 + ‖z8‖ ^ 2 * D8 + ‖z9‖ ^ 2 * D9 + ‖z10‖ ^ 2 * D10) ≤
        -(5671 / 3200 : ℝ) * E *
          energy11 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ ‖z10‖ := by
    unfold energy11
    nlinarith only [hd0, hd1, hd2, hd3, hd4, hd5, hd6, hd7, hd8, hd9, hd10]
  have hrow0 :
      2 * ((z0 * star z1 * b01).re + (z0 * star z2 * b02).re + (z0 * star z3 * b03).re + (z0 * star z4 * b04).re + (z0 * star z5 * b05).re + (z0 * star z6 * b06).re + (z0 * star z7 * b07).re + (z0 * star z8 * b08).re + (z0 * star z9 * b09).re + (z0 * star z10 * b010).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z0‖ * ‖z1‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z2‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z8‖ + (57 / 100 : ℝ) * ‖z0‖ * ‖z9‖ + (837 / 3700 : ℝ) * ‖z0‖ * ‖z10‖) := by
    nlinarith only [hp01, hp02, hp03, hp04, hp05, hp06, hp07, hp08, hp09, hp010]
  have hrow1 :
      2 * ((z1 * star z2 * b12).re + (z1 * star z3 * b13).re + (z1 * star z4 * b14).re + (z1 * star z5 * b15).re + (z1 * star z6 * b16).re + (z1 * star z7 * b17).re + (z1 * star z8 * b18).re + (z1 * star z9 * b19).re + (z1 * star z10 * b110).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z1‖ * ‖z2‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z9‖ + (57 / 100 : ℝ) * ‖z1‖ * ‖z10‖) := by
    nlinarith only [hp12, hp13, hp14, hp15, hp16, hp17, hp18, hp19, hp110]
  have hrow2 :
      2 * ((z2 * star z3 * b23).re + (z2 * star z4 * b24).re + (z2 * star z5 * b25).re + (z2 * star z6 * b26).re + (z2 * star z7 * b27).re + (z2 * star z8 * b28).re + (z2 * star z9 * b29).re + (z2 * star z10 * b210).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z2‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z10‖) := by
    nlinarith only [hp23, hp24, hp25, hp26, hp27, hp28, hp29, hp210]
  have hrow3 :
      2 * ((z3 * star z4 * b34).re + (z3 * star z5 * b35).re + (z3 * star z6 * b36).re + (z3 * star z7 * b37).re + (z3 * star z8 * b38).re + (z3 * star z9 * b39).re + (z3 * star z10 * b310).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z3‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z10‖) := by
    nlinarith only [hp34, hp35, hp36, hp37, hp38, hp39, hp310]
  have hrow4 :
      2 * ((z4 * star z5 * b45).re + (z4 * star z6 * b46).re + (z4 * star z7 * b47).re + (z4 * star z8 * b48).re + (z4 * star z9 * b49).re + (z4 * star z10 * b410).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z4‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z10‖) := by
    nlinarith only [hp45, hp46, hp47, hp48, hp49, hp410]
  have hrow5 :
      2 * ((z5 * star z6 * b56).re + (z5 * star z7 * b57).re + (z5 * star z8 * b58).re + (z5 * star z9 * b59).re + (z5 * star z10 * b510).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z5‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z10‖) := by
    nlinarith only [hp56, hp57, hp58, hp59, hp510]
  have hrow6 :
      2 * ((z6 * star z7 * b67).re + (z6 * star z8 * b68).re + (z6 * star z9 * b69).re + (z6 * star z10 * b610).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z6‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z6‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z6‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z6‖ * ‖z10‖) := by
    nlinarith only [hp67, hp68, hp69, hp610]
  have hrow7 :
      2 * ((z7 * star z8 * b78).re + (z7 * star z9 * b79).re + (z7 * star z10 * b710).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z7‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z7‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z7‖ * ‖z10‖) := by
    nlinarith only [hp78, hp79, hp710]
  have hrow8 :
      2 * ((z8 * star z9 * b89).re + (z8 * star z10 * b810).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z8‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z8‖ * ‖z10‖) := by
    nlinarith only [hp89, hp810]
  have hrow9 :
      2 * ((z9 * star z10 * b910).re) ≤
        2 * E * ((1 / 100 : ℝ) * ‖z9‖ * ‖z10‖) := by
    nlinarith only [hp910]
  have hrows01 := add_le_add hrow0 hrow1
  have hrows23 := add_le_add hrow2 hrow3
  have hrows45 := add_le_add hrow4 hrow5
  have hrows67 := add_le_add hrow6 hrow7
  have hrows89 := add_le_add hrow8 hrow9
  have hrows03 := add_le_add hrows01 hrows23
  have hrows47 := add_le_add hrows45 hrows67
  have hrows07 := add_le_add hrows03 hrows47
  have hrowsAll := add_le_add hrows07 hrows89
  have hcross :
      2 * ((z0 * star z1 * b01).re + (z0 * star z2 * b02).re + (z0 * star z3 * b03).re + (z0 * star z4 * b04).re + (z0 * star z5 * b05).re + (z0 * star z6 * b06).re + (z0 * star z7 * b07).re + (z0 * star z8 * b08).re + (z0 * star z9 * b09).re + (z0 * star z10 * b010).re + (z1 * star z2 * b12).re + (z1 * star z3 * b13).re + (z1 * star z4 * b14).re + (z1 * star z5 * b15).re + (z1 * star z6 * b16).re + (z1 * star z7 * b17).re + (z1 * star z8 * b18).re + (z1 * star z9 * b19).re + (z1 * star z10 * b110).re + (z2 * star z3 * b23).re + (z2 * star z4 * b24).re + (z2 * star z5 * b25).re + (z2 * star z6 * b26).re + (z2 * star z7 * b27).re + (z2 * star z8 * b28).re + (z2 * star z9 * b29).re + (z2 * star z10 * b210).re + (z3 * star z4 * b34).re + (z3 * star z5 * b35).re + (z3 * star z6 * b36).re + (z3 * star z7 * b37).re + (z3 * star z8 * b38).re + (z3 * star z9 * b39).re + (z3 * star z10 * b310).re + (z4 * star z5 * b45).re + (z4 * star z6 * b46).re + (z4 * star z7 * b47).re + (z4 * star z8 * b48).re + (z4 * star z9 * b49).re + (z4 * star z10 * b410).re + (z5 * star z6 * b56).re + (z5 * star z7 * b57).re + (z5 * star z8 * b58).re + (z5 * star z9 * b59).re + (z5 * star z10 * b510).re + (z6 * star z7 * b67).re + (z6 * star z8 * b68).re + (z6 * star z9 * b69).re + (z6 * star z10 * b610).re + (z7 * star z8 * b78).re + (z7 * star z9 * b79).re + (z7 * star z10 * b710).re + (z8 * star z9 * b89).re + (z8 * star z10 * b810).re + (z9 * star z10 * b910).re) ≤
        E * cross11 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ ‖z10‖ := by
    calc
      2 * ((z0 * star z1 * b01).re + (z0 * star z2 * b02).re + (z0 * star z3 * b03).re + (z0 * star z4 * b04).re + (z0 * star z5 * b05).re + (z0 * star z6 * b06).re + (z0 * star z7 * b07).re + (z0 * star z8 * b08).re + (z0 * star z9 * b09).re + (z0 * star z10 * b010).re + (z1 * star z2 * b12).re + (z1 * star z3 * b13).re + (z1 * star z4 * b14).re + (z1 * star z5 * b15).re + (z1 * star z6 * b16).re + (z1 * star z7 * b17).re + (z1 * star z8 * b18).re + (z1 * star z9 * b19).re + (z1 * star z10 * b110).re + (z2 * star z3 * b23).re + (z2 * star z4 * b24).re + (z2 * star z5 * b25).re + (z2 * star z6 * b26).re + (z2 * star z7 * b27).re + (z2 * star z8 * b28).re + (z2 * star z9 * b29).re + (z2 * star z10 * b210).re + (z3 * star z4 * b34).re + (z3 * star z5 * b35).re + (z3 * star z6 * b36).re + (z3 * star z7 * b37).re + (z3 * star z8 * b38).re + (z3 * star z9 * b39).re + (z3 * star z10 * b310).re + (z4 * star z5 * b45).re + (z4 * star z6 * b46).re + (z4 * star z7 * b47).re + (z4 * star z8 * b48).re + (z4 * star z9 * b49).re + (z4 * star z10 * b410).re + (z5 * star z6 * b56).re + (z5 * star z7 * b57).re + (z5 * star z8 * b58).re + (z5 * star z9 * b59).re + (z5 * star z10 * b510).re + (z6 * star z7 * b67).re + (z6 * star z8 * b68).re + (z6 * star z9 * b69).re + (z6 * star z10 * b610).re + (z7 * star z8 * b78).re + (z7 * star z9 * b79).re + (z7 * star z10 * b710).re + (z8 * star z9 * b89).re + (z8 * star z10 * b810).re + (z9 * star z10 * b910).re) =
          (2 * ((z0 * star z1 * b01).re + (z0 * star z2 * b02).re + (z0 * star z3 * b03).re + (z0 * star z4 * b04).re + (z0 * star z5 * b05).re + (z0 * star z6 * b06).re + (z0 * star z7 * b07).re + (z0 * star z8 * b08).re + (z0 * star z9 * b09).re + (z0 * star z10 * b010).re)) +
          (2 * ((z1 * star z2 * b12).re + (z1 * star z3 * b13).re + (z1 * star z4 * b14).re + (z1 * star z5 * b15).re + (z1 * star z6 * b16).re + (z1 * star z7 * b17).re + (z1 * star z8 * b18).re + (z1 * star z9 * b19).re + (z1 * star z10 * b110).re)) +
          (2 * ((z2 * star z3 * b23).re + (z2 * star z4 * b24).re + (z2 * star z5 * b25).re + (z2 * star z6 * b26).re + (z2 * star z7 * b27).re + (z2 * star z8 * b28).re + (z2 * star z9 * b29).re + (z2 * star z10 * b210).re)) +
          (2 * ((z3 * star z4 * b34).re + (z3 * star z5 * b35).re + (z3 * star z6 * b36).re + (z3 * star z7 * b37).re + (z3 * star z8 * b38).re + (z3 * star z9 * b39).re + (z3 * star z10 * b310).re)) +
          (2 * ((z4 * star z5 * b45).re + (z4 * star z6 * b46).re + (z4 * star z7 * b47).re + (z4 * star z8 * b48).re + (z4 * star z9 * b49).re + (z4 * star z10 * b410).re)) +
          (2 * ((z5 * star z6 * b56).re + (z5 * star z7 * b57).re + (z5 * star z8 * b58).re + (z5 * star z9 * b59).re + (z5 * star z10 * b510).re)) +
          (2 * ((z6 * star z7 * b67).re + (z6 * star z8 * b68).re + (z6 * star z9 * b69).re + (z6 * star z10 * b610).re)) +
          (2 * ((z7 * star z8 * b78).re + (z7 * star z9 * b79).re + (z7 * star z10 * b710).re)) +
          (2 * ((z8 * star z9 * b89).re + (z8 * star z10 * b810).re)) +
          (2 * ((z9 * star z10 * b910).re)) := by ring
      _ ≤ (2 * E * ((1 / 100 : ℝ) * ‖z0‖ * ‖z1‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z2‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z0‖ * ‖z8‖ + (57 / 100 : ℝ) * ‖z0‖ * ‖z9‖ + (837 / 3700 : ℝ) * ‖z0‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z1‖ * ‖z2‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z1‖ * ‖z9‖ + (57 / 100 : ℝ) * ‖z1‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z2‖ * ‖z3‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z2‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z3‖ * ‖z4‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z3‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z4‖ * ‖z5‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z4‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z5‖ * ‖z6‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z5‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z6‖ * ‖z7‖ + (1 / 100 : ℝ) * ‖z6‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z6‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z6‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z7‖ * ‖z8‖ + (1 / 100 : ℝ) * ‖z7‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z7‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z8‖ * ‖z9‖ + (1 / 100 : ℝ) * ‖z8‖ * ‖z10‖)) +
          (2 * E * ((1 / 100 : ℝ) * ‖z9‖ * ‖z10‖)) := by
        convert hrowsAll using 1 <;> try ring
        all_goals with_reducible_and_instances rfl
      _ = E * cross11 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ ‖z10‖ := by
        unfold cross11 pairSum11
        ring
  have hvalue := add_le_add hdiag hcross
  have hc := mul_le_mul_of_nonneg_left
    (cross_eleven_le_1621_over_1850_v1 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ ‖z10‖) hE
  calc
    elevenValue z0 z1 z2 z3 z4 z5 z6 z7 z8 z9 z10 D0 D1 D2 D3 D4 D5 D6 D7 D8 D9 D10 b01 b02 b03 b04 b05 b06 b07 b08 b09 b010 b12 b13 b14 b15 b16 b17 b18 b19 b110 b23 b24 b25 b26 b27 b28 b29 b210 b34 b35 b36 b37 b38 b39 b310 b45 b46 b47 b48 b49 b410 b56 b57 b58 b59 b510 b67 b68 b69 b610 b78 b79 b710 b89 b810 b910 ≤
        -(5671 / 3200 : ℝ) * E * energy11 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ ‖z10‖ +
          E * cross11 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ ‖z10‖ := by
      simpa [elevenValue] using hvalue
    _ ≤ -(106083 / 118400 : ℝ) * E * energy11 ‖z0‖ ‖z1‖ ‖z2‖ ‖z3‖ ‖z4‖ ‖z5‖ ‖z6‖ ‖z7‖ ‖z8‖ ‖z9‖ ‖z10‖ := by
      nlinarith only [hc]

end AEGIS.RHElevenBlockActualBridgeV1

#print axioms AEGIS.RHElevenBlockActualBridgeV1.pair_re_le_eleven_v1
#print axioms AEGIS.RHElevenBlockActualBridgeV1.eleven_value_bound_v1
