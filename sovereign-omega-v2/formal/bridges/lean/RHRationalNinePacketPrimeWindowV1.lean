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
open AEGIS.WeilMixedAlgebraV2
open AEGIS.WeilThreeBlockAnalyticConstantsV21
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


theorem exp_one_over_128_upper_v1 :
    Real.exp (1 / 128 : ℝ) < (128 / 127 : ℝ) := by
  calc
    _ < 1 / (1 - (1 / 128 : ℝ)) :=
      Real.exp_bound_div_one_sub_of_interval' (by norm_num) (by norm_num)
    _ = _ := by norm_num

theorem mixed_translate_zero_of_fine_width_v1
    (g : WeilCompactSmoothGV1) (a d1 d2 u : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hu : (1 / 128 : ℝ) < |u + d2 - d1|) :
    mixed (translatePacket g d1) (translatePacket g d2) (Real.exp u) = 0 := by
  have h := exp_half_mul_mixed_translate_v28 g d1 d2 u
  rw [logCorrelation_zero_of_fine_width_abs_v1 g a (u + d2 - d1) hw hu] at h
  have he : (Real.exp (u / 2) : ℂ) ≠ 0 :=
    Complex.ofReal_ne_zero.mpr (Real.exp_ne_zero _)
  exact (mul_eq_zero.mp h).resolve_left he

theorem mixed_nat_zero_of_positive_gap_v1
    (g : WeilCompactSmoothGV1) (a d1 d2 : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hgap : (1 / 128 : ℝ) < d2 - d1)
    (m : ℕ) (hm : 0 < m) :
    mixed (translatePacket g d1) (translatePacket g d2) (m : ℝ) = 0 := by
  have hmpos : (0 : ℝ) < (m : ℝ) := by exact_mod_cast hm
  have hm1 : (1 : ℝ) ≤ (m : ℝ) := by
    exact_mod_cast (Nat.one_le_iff_ne_zero.mpr (Nat.ne_of_gt hm))
  have hlogm : 0 ≤ Real.log (m : ℝ) := Real.log_nonneg hm1
  have harg : 0 < Real.log (m : ℝ) + d2 - d1 := by linarith
  have hfar :
      (1 / 128 : ℝ) < |Real.log (m : ℝ) + d2 - d1| := by
    rw [abs_of_pos harg]
    linarith
  have hz := mixed_translate_zero_of_fine_width_v1
    g a d1 d2 (Real.log (m : ℝ)) hw hfar
  simpa only [Real.exp_log hmpos] using hz

theorem mixed_inv_nat_zero_outside_gap_v1
    (g : WeilCompactSmoothGV1) (a d1 d2 : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (m : ℕ) (hm : 0 < m)
    (hfar0 : (1 / 128 : ℝ) <
      |Real.log (m : ℝ) - (d2 - d1)|) :
    mixed (translatePacket g d1) (translatePacket g d2) ((m : ℝ)⁻¹) = 0 := by
  have harg :
      -Real.log (m : ℝ) + d2 - d1 =
        -(Real.log (m : ℝ) - (d2 - d1)) := by ring
  have hfar :
      (1 / 128 : ℝ) <
        |-Real.log (m : ℝ) + d2 - d1| := by
    rw [harg, abs_neg]
    exact hfar0
  have hz := mixed_translate_zero_of_fine_width_v1
    g a d1 d2 (-Real.log (m : ℝ)) hw hfar
  have he : Real.exp (-Real.log (m : ℝ)) = (m : ℝ)⁻¹ := by
    rw [Real.exp_neg, Real.exp_log (by exact_mod_cast hm)]
  simpa only [he] using hz

theorem prime_sum_zero_of_window_vm_v1
    (g : WeilCompactSmoothGV1) (a d1 d2 : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hgap : (1 / 128 : ℝ) < d2 - d1)
    (hvm : ∀ m : ℕ, 0 < m →
      |Real.log (m : ℝ) - (d2 - d1)| ≤ (1 / 128 : ℝ) →
      ArithmeticFunction.vonMangoldt m = 0) :
    WeilPrimeSumV1
      (mixed (translatePacket g d1) (translatePacket g d2)) = 0 := by
  unfold WeilPrimeSumV1
  have hterm :
      WeilPrimeTermV1
        (mixed (translatePacket g d1) (translatePacket g d2)) =
        (0 : ℕ → ℂ) := by
    funext n
    have hm : 0 < n + 1 := by omega
    have hp := mixed_nat_zero_of_positive_gap_v1
      g a d1 d2 hw hgap (n + 1) hm
    by_cases hwin :
        |Real.log ((n + 1 : ℕ) : ℝ) - (d2 - d1)| ≤ (1 / 128 : ℝ)
    · have hv := hvm (n + 1) hm hwin
      simp [WeilPrimeTermV1, hp, hv]
    · have hfar :
          (1 / 128 : ℝ) <
            |Real.log ((n + 1 : ℕ) : ℝ) - (d2 - d1)| :=
        lt_of_not_ge hwin
      have hi := mixed_inv_nat_zero_outside_gap_v1
        g a d1 d2 hw (n + 1) hm hfar
      simp [WeilPrimeTermV1, hp, hi]
  rw [hterm]
  simp

private theorem qNine_gap_one_gt_cutoff_v1 :
    (1 / 128 : ℝ) < Real.log (qNineV1 ^ 1) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

private theorem qNine_gap_two_gt_cutoff_v1 :
    (1 / 128 : ℝ) < Real.log (qNineV1 ^ 2) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

private theorem qNine_gap_three_gt_cutoff_v1 :
    (1 / 128 : ℝ) < Real.log (qNineV1 ^ 3) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

private theorem qNine_gap_four_gt_cutoff_v1 :
    (1 / 128 : ℝ) < Real.log (qNineV1 ^ 4) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

private theorem qNine_gap_five_gt_cutoff_v1 :
    (1 / 128 : ℝ) < Real.log (qNineV1 ^ 5) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

private theorem qNine_gap_six_gt_cutoff_v1 :
    (1 / 128 : ℝ) < Real.log (qNineV1 ^ 6) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

private theorem qNine_gap_seven_gt_cutoff_v1 :
    (1 / 128 : ℝ) < Real.log (qNineV1 ^ 7) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

private theorem qNine_gap_eight_gt_cutoff_v1 :
    (1 / 128 : ℝ) < Real.log (qNineV1 ^ 8) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num [qNineV1])]
  exact exp_one_over_128_upper_v1.trans (by norm_num [qNineV1])

theorem gap_one_prime_sum_zero_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0)
        (translatePacket g (Real.log (qNineV1 ^ 1)))) = 0 := by
  apply prime_sum_zero_of_window_vm_v1 g a 0
    (Real.log (qNineV1 ^ 1)) hw
  · simpa using qNine_gap_one_gt_cutoff_v1
  · intro m hm hwin
    simpa using gap_one_vonMangoldt_zero_v1 hm hwin

theorem gap_two_prime_sum_zero_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0)
        (translatePacket g (Real.log (qNineV1 ^ 2)))) = 0 := by
  apply prime_sum_zero_of_window_vm_v1 g a 0
    (Real.log (qNineV1 ^ 2)) hw
  · simpa using qNine_gap_two_gt_cutoff_v1
  · intro m hm hwin
    simpa using gap_two_vonMangoldt_zero_v1 hm hwin

theorem gap_three_prime_sum_zero_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0)
        (translatePacket g (Real.log (qNineV1 ^ 3)))) = 0 := by
  apply prime_sum_zero_of_window_vm_v1 g a 0
    (Real.log (qNineV1 ^ 3)) hw
  · simpa using qNine_gap_three_gt_cutoff_v1
  · intro m hm hwin
    simpa using gap_three_vonMangoldt_zero_v1 hm hwin

theorem gap_four_prime_sum_zero_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0)
        (translatePacket g (Real.log (qNineV1 ^ 4)))) = 0 := by
  apply prime_sum_zero_of_window_vm_v1 g a 0
    (Real.log (qNineV1 ^ 4)) hw
  · simpa using qNine_gap_four_gt_cutoff_v1
  · intro m hm hwin
    simpa using gap_four_vonMangoldt_zero_v1 hm hwin

theorem gap_five_prime_sum_zero_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0)
        (translatePacket g (Real.log (qNineV1 ^ 5)))) = 0 := by
  apply prime_sum_zero_of_window_vm_v1 g a 0
    (Real.log (qNineV1 ^ 5)) hw
  · simpa using qNine_gap_five_gt_cutoff_v1
  · intro m hm hwin
    simpa using gap_five_vonMangoldt_zero_v1 hm hwin

theorem gap_six_prime_sum_zero_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0)
        (translatePacket g (Real.log (qNineV1 ^ 6)))) = 0 := by
  apply prime_sum_zero_of_window_vm_v1 g a 0
    (Real.log (qNineV1 ^ 6)) hw
  · simpa using qNine_gap_six_gt_cutoff_v1
  · intro m hm hwin
    simpa using gap_six_vonMangoldt_zero_v1 hm hwin

theorem gap_seven_prime_sum_zero_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0)
        (translatePacket g (Real.log (qNineV1 ^ 7)))) = 0 := by
  apply prime_sum_zero_of_window_vm_v1 g a 0
    (Real.log (qNineV1 ^ 7)) hw
  · simpa using qNine_gap_seven_gt_cutoff_v1
  · intro m hm hwin
    simpa using gap_seven_vonMangoldt_zero_v1 hm hwin

theorem gap_eight_prime_sum_zero_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WeilPrimeSumV1
      (mixed (translatePacket g 0)
        (translatePacket g (Real.log (qNineV1 ^ 8)))) = 0 := by
  apply prime_sum_zero_of_window_vm_v1 g a 0
    (Real.log (qNineV1 ^ 8)) hw
  · simpa using qNine_gap_eight_gt_cutoff_v1
  · intro m hm hwin
    simpa using gap_eight_vonMangoldt_zero_v1 hm hwin


theorem fine_width_implies_width_one_thirty_two_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a) :
    WidthOneThirtyTwoAt g a := by
  intro t ht
  have h := hw ht
  exact ⟨by linarith [h.1], by linarith [h.2]⟩

theorem B_norm_le_one_hundred_of_prime_zero_fine_v1
    (g : WeilCompactSmoothGV1) (a d1 d2 : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g)
    (hgap : Real.log 2 ≤ d2 - d1)
    (hprime :
      WeilPrimeSumV1
        (mixed (translatePacket g d1) (translatePacket g d2)) = 0) :
    ‖B (translatePacket g d1) (translatePacket g d2)‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  have hcut : (1 / 128 : ℝ) < d2 - d1 := by
    nlinarith [log_two_lower]
  have hpos : 0 < d2 - d1 := lt_trans (by norm_num) hcut
  have hfar : (1 / 128 : ℝ) < |(0 : ℝ) + d2 - d1| := by
    rw [zero_add, abs_of_pos hpos]
    exact hcut
  have hz0 := mixed_translate_zero_of_fine_width_v1
    g a d1 d2 0 hw hfar
  have hzero :
      mixed (translatePacket g d1) (translatePacket g d2) 1 = 0 := by
    simpa only [Real.exp_zero] using hz0
  have harch := translated_arch_norm_bound
    g a d1 d2 (fine_width_implies_width_one_thirty_two_v1 g a hw) hm hgap
  unfold B WeilExplicitRightSideV1
  rw [hprime, hzero]
  simpa using harch

private theorem qNine_gap_one_log_two_v1 :
    Real.log 2 ≤ Real.log (qNineV1 ^ 1) := by
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

private theorem qNine_gap_two_log_two_v1 :
    Real.log 2 ≤ Real.log (qNineV1 ^ 2) := by
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

private theorem qNine_gap_three_log_two_v1 :
    Real.log 2 ≤ Real.log (qNineV1 ^ 3) := by
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

private theorem qNine_gap_four_log_two_v1 :
    Real.log 2 ≤ Real.log (qNineV1 ^ 4) := by
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

private theorem qNine_gap_five_log_two_v1 :
    Real.log 2 ≤ Real.log (qNineV1 ^ 5) := by
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

private theorem qNine_gap_six_log_two_v1 :
    Real.log 2 ≤ Real.log (qNineV1 ^ 6) := by
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

private theorem qNine_gap_seven_log_two_v1 :
    Real.log 2 ≤ Real.log (qNineV1 ^ 7) := by
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

private theorem qNine_gap_eight_log_two_v1 :
    Real.log 2 ≤ Real.log (qNineV1 ^ 8) := by
  exact le_of_lt ((Real.log_lt_log_iff (by norm_num)
    (by norm_num [qNineV1])).2 (by norm_num [qNineV1]))

theorem gap_one_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0)
      (translatePacket g (Real.log (qNineV1 ^ 1)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  exact B_norm_le_one_hundred_of_prime_zero_fine_v1
    g a 0 (Real.log (qNineV1 ^ 1)) hw hm
    (by simpa using qNine_gap_one_log_two_v1)
    (gap_one_prime_sum_zero_v1 g a hw)

theorem gap_two_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0)
      (translatePacket g (Real.log (qNineV1 ^ 2)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  exact B_norm_le_one_hundred_of_prime_zero_fine_v1
    g a 0 (Real.log (qNineV1 ^ 2)) hw hm
    (by simpa using qNine_gap_two_log_two_v1)
    (gap_two_prime_sum_zero_v1 g a hw)

theorem gap_three_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0)
      (translatePacket g (Real.log (qNineV1 ^ 3)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  exact B_norm_le_one_hundred_of_prime_zero_fine_v1
    g a 0 (Real.log (qNineV1 ^ 3)) hw hm
    (by simpa using qNine_gap_three_log_two_v1)
    (gap_three_prime_sum_zero_v1 g a hw)

theorem gap_four_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0)
      (translatePacket g (Real.log (qNineV1 ^ 4)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  exact B_norm_le_one_hundred_of_prime_zero_fine_v1
    g a 0 (Real.log (qNineV1 ^ 4)) hw hm
    (by simpa using qNine_gap_four_log_two_v1)
    (gap_four_prime_sum_zero_v1 g a hw)

theorem gap_five_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0)
      (translatePacket g (Real.log (qNineV1 ^ 5)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  exact B_norm_le_one_hundred_of_prime_zero_fine_v1
    g a 0 (Real.log (qNineV1 ^ 5)) hw hm
    (by simpa using qNine_gap_five_log_two_v1)
    (gap_five_prime_sum_zero_v1 g a hw)

theorem gap_six_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0)
      (translatePacket g (Real.log (qNineV1 ^ 6)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  exact B_norm_le_one_hundred_of_prime_zero_fine_v1
    g a 0 (Real.log (qNineV1 ^ 6)) hw hm
    (by simpa using qNine_gap_six_log_two_v1)
    (gap_six_prime_sum_zero_v1 g a hw)

theorem gap_seven_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0)
      (translatePacket g (Real.log (qNineV1 ^ 7)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  exact B_norm_le_one_hundred_of_prime_zero_fine_v1
    g a 0 (Real.log (qNineV1 ^ 7)) hw hm
    (by simpa using qNine_gap_seven_log_two_v1)
    (gap_seven_prime_sum_zero_v1 g a hw)

theorem gap_eight_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) :
    ‖B (translatePacket g 0)
      (translatePacket g (Real.log (qNineV1 ^ 8)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  exact B_norm_le_one_hundred_of_prime_zero_fine_v1
    g a 0 (Real.log (qNineV1 ^ 8)) hw hm
    (by simpa using qNine_gap_eight_log_two_v1)
    (gap_eight_prime_sum_zero_v1 g a hw)


/-- Positive-source carrier: mixed correlations vanish at nonpositive samples. -/
theorem mixed_zero_of_nonpos_nine_v1
    (p q : WeilCompactSmoothGV1) {x : ℝ} (hx : x ≤ 0) :
    mixed p q x = 0 := by
  unfold mixed
  apply setIntegral_eq_zero_of_forall_eq_zero
  intro y hy
  have hz := packet_eq_zero_of_nonpos p
    (mul_nonpos_of_nonpos_of_nonneg hx hy.le)
  rw [hz, zero_mul]

/-- The complete translated mixed correlation depends only on the translation gap. -/
theorem mixed_translate_eq_of_gap_nine_v1
    (g : WeilCompactSmoothGV1)
    (d1 d2 e1 e2 : ℝ) (hgap : d2 - d1 = e2 - e1) :
    mixed (translatePacket g d1) (translatePacket g d2) =
      mixed (translatePacket g e1) (translatePacket g e2) := by
  funext x
  by_cases hx : 0 < x
  · have h1 := exp_half_mul_mixed_translate_v28 g d1 d2 (Real.log x)
    have h2 := exp_half_mul_mixed_translate_v28 g e1 e2 (Real.log x)
    rw [Real.exp_log hx] at h1 h2
    have ha : Real.log x + d2 - d1 = Real.log x + e2 - e1 := by
      linarith
    rw [ha] at h1
    have he : (Real.exp (Real.log x / 2) : ℂ) ≠ 0 := by simp
    exact mul_left_cancel₀ he (h1.trans h2.symm)
  · rw [mixed_zero_of_nonpos_nine_v1 _ _ (le_of_not_gt hx),
        mixed_zero_of_nonpos_nine_v1 _ _ (le_of_not_gt hx)]

theorem B_translate_eq_of_gap_nine_v1
    (g : WeilCompactSmoothGV1)
    (d1 d2 e1 e2 : ℝ) (hgap : d2 - d1 = e2 - e1) :
    B (translatePacket g d1) (translatePacket g d2) =
      B (translatePacket g e1) (translatePacket g e2) := by
  unfold B
  rw [mixed_translate_eq_of_gap_nine_v1 g d1 d2 e1 e2 hgap]

def qNineShiftV1 (j : ℕ) : ℝ :=
  (j : ℝ) * Real.log qNineV1

theorem log_qNine_pow_v1 (k : ℕ) :
    Real.log (qNineV1 ^ k) = (k : ℝ) * Real.log qNineV1 := by
  simpa using (Real.log_pow qNineV1 k)

theorem qNineShift_gap_v1 (i k : ℕ) :
    qNineShiftV1 (i + k) - qNineShiftV1 i =
      Real.log (qNineV1 ^ k) := by
  rw [log_qNine_pow_v1]
  simp [qNineShiftV1, Nat.cast_add]
  ring

theorem shift_gap_one_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 1)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 1))
    0 (Real.log (qNineV1 ^ 1)) (by
      simpa using qNineShift_gap_v1 i 1)]
  exact gap_one_B_norm_v1 g a hw hm

theorem shift_gap_two_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 2)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 2))
    0 (Real.log (qNineV1 ^ 2)) (by
      simpa using qNineShift_gap_v1 i 2)]
  exact gap_two_B_norm_v1 g a hw hm

theorem shift_gap_three_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 3)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 3))
    0 (Real.log (qNineV1 ^ 3)) (by
      simpa using qNineShift_gap_v1 i 3)]
  exact gap_three_B_norm_v1 g a hw hm

theorem shift_gap_four_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 4)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 4))
    0 (Real.log (qNineV1 ^ 4)) (by
      simpa using qNineShift_gap_v1 i 4)]
  exact gap_four_B_norm_v1 g a hw hm

theorem shift_gap_five_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 5)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 5))
    0 (Real.log (qNineV1 ^ 5)) (by
      simpa using qNineShift_gap_v1 i 5)]
  exact gap_five_B_norm_v1 g a hw hm

theorem shift_gap_six_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 6)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 6))
    0 (Real.log (qNineV1 ^ 6)) (by
      simpa using qNineShift_gap_v1 i 6)]
  exact gap_six_B_norm_v1 g a hw hm

theorem shift_gap_seven_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 7)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 7))
    0 (Real.log (qNineV1 ^ 7)) (by
      simpa using qNineShift_gap_v1 i 7)]
  exact gap_seven_B_norm_v1 g a hw hm

theorem shift_gap_eight_B_norm_v1
    (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneOneTwentyEightAt g a)
    (hm : WeilMomentConditionsV1 g) (i : ℕ) :
    ‖B (translatePacket g (qNineShiftV1 i))
      (translatePacket g (qNineShiftV1 (i + 8)))‖ ≤
      (1 / 100 : ℝ) * energy g.1 := by
  rw [B_translate_eq_of_gap_nine_v1 g
    (qNineShiftV1 i) (qNineShiftV1 (i + 8))
    0 (Real.log (qNineV1 ^ 8)) (by
      simpa using qNineShift_gap_v1 i 8)]
  exact gap_eight_B_norm_v1 g a hw hm

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
