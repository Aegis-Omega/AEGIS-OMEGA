import RHFineMomentPacketV3
import WeilSeparatedArchBridgeV31
import Mathlib.NumberTheory.ArithmeticFunction.VonMangoldt
import Mathlib.Tactic

/-!
AEGIS Omega -- rational nine-packet prime-window producer V1.

Research-only additive source candidate.

The existing canonical packet gFine is sharpened to its actual logarithmic
support radius 1/256. Hence its log-correlation support radius is 1/128.
For q = 33/16, the first eight multiplicative gap windows contain only
integers with vanishing von Mangoldt coefficient. The ninth gap is deliberately
out of scope here; the exact-rational preflight finds prime witnesses there.

This module proves no nine-packet coercivity theorem, no globalization, no
universal Weil sign and no RH conclusion.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set MeasureTheory Complex
open scoped ComplexConjugate BigOperators

set_option autoImplicit false
noncomputable section

namespace AEGIS.RHRationalNinePacketPrimeWindowV1

open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockTranslatedPacketsV22
open AEGIS.WeilThreeBlockCrossPrimeV28
open AEGIS.WeilSeparatedArchBridgeV31
open AEGIS.RHFineMomentPacketV3

def WidthOneOneTwentyEightAt (g : WeilCompactSmoothGV1) (a : ℝ) : Prop :=
  LogSupportIn g (a - (1 / 256 : ℝ)) (a + (1 / 256 : ℝ))

theorem gFine_width_one_one_twenty_eight_v1 :
    WidthOneOneTwentyEightAt gFine 0 := by
  change tsupport (logLift gFine.1) ⊆ Icc (0 - 1 / 256) (0 + 1 / 256)
  apply closure_minimal
  · intro t ht
    by_contra hout
    have hphi : phiFine t = 0 := by
      apply image_eq_zero_of_notMem_tsupport
      intro hmem
      have hs := phiFine_tsupport_strict_v3 hmem
      apply hout
      simpa using hs
    apply ht
    rw [logLift_gFine_apply_v3, hphi]
    simp
  · exact isClosed_Icc

theorem logCorrelation_zero_of_fine_width_abs_v1
    (g : WeilCompactSmoothGV1) (a u : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hu : (1 / 128 : ℝ) < |u|) :
    logCorrelationV25 g u = 0 := by
  unfold logCorrelationV25
  apply integral_eq_zero_of_ae
  filter_upwards [] with v
  by_cases h0 : logLift g.1 v = 0
  · simp [h0]
  · by_cases h1 : logLift g.1 (v + u) = 0
    · simp [h1]
    · have hm0 : v ∈ tsupport (logLift g.1) := subset_tsupport _ h0
      have hm1 : v + u ∈ tsupport (logLift g.1) := subset_tsupport _ h1
      have hv := hw hm0
      have hvu := hw hm1
      have habs : |u| ≤ (1 / 128 : ℝ) := by
        rw [abs_le]
        constructor <;> linarith [hv.1, hv.2, hvu.1, hvu.2]
      exact False.elim ((not_le_of_gt hu) habs)

def qNineV1 : ℝ := 33 / 16

theorem nat_envelope_of_log_window_v1
    {m : ℕ} (hm : 0 < m) {c : ℝ} (hc : 0 < c)
    (hw : |Real.log (m : ℝ) - Real.log c| ≤ (1 / 128 : ℝ)) :
    c * (127 / 128 : ℝ) ≤ (m : ℝ) ∧
      (m : ℝ) < c * (128 / 127 : ℝ) := by
  have hmpos : (0 : ℝ) < (m : ℝ) := by exact_mod_cast hm
  obtain ⟨hl, hu⟩ := abs_le.mp hw
  have hup := Real.exp_le_exp.mpr
    (show Real.log (m : ℝ) ≤ Real.log c + 1 / 128 by linarith)
  have hlo := Real.exp_le_exp.mpr
    (show Real.log c - 1 / 128 ≤ Real.log (m : ℝ) by linarith)
  rw [Real.exp_add, Real.exp_log hc, Real.exp_log hmpos] at hup
  rw [sub_eq_add_neg, Real.exp_add, Real.exp_log hc, Real.exp_log hmpos] at hlo
  have hexp_hi : Real.exp (1 / 128 : ℝ) < (128 / 127 : ℝ) := by
    calc
      _ < 1 / (1 - (1 / 128 : ℝ)) :=
        Real.exp_bound_div_one_sub_of_interval' (by norm_num) (by norm_num)
      _ = _ := by norm_num
  have hexp_lo : (127 / 128 : ℝ) ≤ Real.exp (-(1 / 128 : ℝ)) := by
    linarith [Real.add_one_le_exp (-(1 / 128 : ℝ))]
  constructor
  · nlinarith [mul_le_mul_of_nonneg_left hexp_lo hc.le]
  · nlinarith [mul_lt_mul_of_pos_left hexp_hi hc]

private theorem qNineV1_pos : 0 < qNineV1 := by norm_num [qNineV1]

private theorem vm18_zero : ArithmeticFunction.vonMangoldt 18 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm77_zero : ArithmeticFunction.vonMangoldt 77 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm158_zero : ArithmeticFunction.vonMangoldt 158 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm159_zero : ArithmeticFunction.vonMangoldt 159 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm160_zero : ArithmeticFunction.vonMangoldt 160 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm325_zero : ArithmeticFunction.vonMangoldt 325 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm326_zero : ArithmeticFunction.vonMangoldt 326 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm327_zero : ArithmeticFunction.vonMangoldt 327 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm328_zero : ArithmeticFunction.vonMangoldt 328 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm329_zero : ArithmeticFunction.vonMangoldt 329 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)
private theorem vm330_zero : ArithmeticFunction.vonMangoldt 330 = 0 := by
  exact ArithmeticFunction.vonMangoldt_eq_zero_iff.mpr (by decide)

private theorem gap_window_bounds_v1
    (k : ℕ) {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ k)| ≤ (1 / 128 : ℝ)) :
    qNineV1 ^ k * (127 / 128 : ℝ) ≤ (m : ℝ) ∧
      (m : ℝ) < qNineV1 ^ k * (128 / 127 : ℝ) := by
  exact nat_envelope_of_log_window_v1 hm (pow_pos qNineV1_pos k) hw

theorem gap_one_vonMangoldt_zero_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ 1)| ≤ (1 / 128 : ℝ)) :
    ArithmeticFunction.vonMangoldt m = 0 := by
  have h := gap_window_bounds_v1 1 hm hw
  have hlo : (2 : ℝ) < (m : ℝ) := by exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 3 := by exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : 2 < m := by exact_mod_cast hlo
  have hhiN : m < 3 := by exact_mod_cast hhi
  omega

theorem gap_two_vonMangoldt_zero_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ 2)| ≤ (1 / 128 : ℝ)) :
    ArithmeticFunction.vonMangoldt m = 0 := by
  have h := gap_window_bounds_v1 2 hm hw
  have hlo : (4 : ℝ) < (m : ℝ) := by exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 5 := by exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : 4 < m := by exact_mod_cast hlo
  have hhiN : m < 5 := by exact_mod_cast hhi
  omega

theorem gap_three_vonMangoldt_zero_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ 3)| ≤ (1 / 128 : ℝ)) :
    ArithmeticFunction.vonMangoldt m = 0 := by
  have h := gap_window_bounds_v1 3 hm hw
  have hlo : (8 : ℝ) < (m : ℝ) := by exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 9 := by exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : 8 < m := by exact_mod_cast hlo
  have hhiN : m < 9 := by exact_mod_cast hhi
  omega

theorem gap_four_vonMangoldt_zero_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ 4)| ≤ (1 / 128 : ℝ)) :
    ArithmeticFunction.vonMangoldt m = 0 := by
  have h := gap_window_bounds_v1 4 hm hw
  have hlo : (17 : ℝ) < (m : ℝ) := by exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 19 := by exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : 17 < m := by exact_mod_cast hlo
  have hhiN : m < 19 := by exact_mod_cast hhi
  have hm18 : m = 18 := by omega
  subst m
  exact vm18_zero

theorem gap_five_vonMangoldt_zero_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ 5)| ≤ (1 / 128 : ℝ)) :
    ArithmeticFunction.vonMangoldt m = 0 := by
  have h := gap_window_bounds_v1 5 hm hw
  have hlo : (37 : ℝ) < (m : ℝ) := by exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 38 := by exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : 37 < m := by exact_mod_cast hlo
  have hhiN : m < 38 := by exact_mod_cast hhi
  omega

theorem gap_six_vonMangoldt_zero_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ 6)| ≤ (1 / 128 : ℝ)) :
    ArithmeticFunction.vonMangoldt m = 0 := by
  have h := gap_window_bounds_v1 6 hm hw
  have hlo : (76 : ℝ) < (m : ℝ) := by exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 78 := by exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : 76 < m := by exact_mod_cast hlo
  have hhiN : m < 78 := by exact_mod_cast hhi
  have hm77 : m = 77 := by omega
  subst m
  exact vm77_zero

theorem gap_seven_vonMangoldt_zero_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ 7)| ≤ (1 / 128 : ℝ)) :
    ArithmeticFunction.vonMangoldt m = 0 := by
  have h := gap_window_bounds_v1 7 hm hw
  have hlo : (157 : ℝ) < (m : ℝ) := by exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 161 := by exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : 157 < m := by exact_mod_cast hlo
  have hhiN : m < 161 := by exact_mod_cast hhi
  interval_cases m <;> simp [vm158_zero, vm159_zero, vm160_zero]

theorem gap_eight_vonMangoldt_zero_v1
    {m : ℕ} (hm : 0 < m)
    (hw : |Real.log (m : ℝ) - Real.log (qNineV1 ^ 8)| ≤ (1 / 128 : ℝ)) :
    ArithmeticFunction.vonMangoldt m = 0 := by
  have h := gap_window_bounds_v1 8 hm hw
  have hlo : (324 : ℝ) < (m : ℝ) := by exact lt_of_lt_of_le (by norm_num [qNineV1]) h.1
  have hhi : (m : ℝ) < 331 := by exact h.2.trans_le (by norm_num [qNineV1])
  have hloN : 324 < m := by exact_mod_cast hlo
  have hhiN : m < 331 := by exact_mod_cast hhi
  interval_cases m <;>
    simp [vm325_zero, vm326_zero, vm327_zero, vm328_zero, vm329_zero, vm330_zero]

end AEGIS.RHRationalNinePacketPrimeWindowV1

#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gFine_width_one_one_twenty_eight_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.logCorrelation_zero_of_fine_width_abs_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gap_one_vonMangoldt_zero_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gap_two_vonMangoldt_zero_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gap_three_vonMangoldt_zero_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gap_four_vonMangoldt_zero_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gap_five_vonMangoldt_zero_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gap_six_vonMangoldt_zero_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gap_seven_vonMangoldt_zero_v1
#print axioms AEGIS.RHRationalNinePacketPrimeWindowV1.gap_eight_vonMangoldt_zero_v1
