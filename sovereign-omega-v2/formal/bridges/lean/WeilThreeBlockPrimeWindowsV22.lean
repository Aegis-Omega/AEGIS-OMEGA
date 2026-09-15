import WeilThreeBlockTranslatedPacketsV22
import WeilMixedClosureV2
import WeilThreeBlockAnalyticConstantsV21
import Mathlib.MeasureTheory.Integral.IntegralEqImproper
import Mathlib.NumberTheory.ArithmeticFunction.VonMangoldt
import Mathlib.Tactic

/-!
AEGIS Ω — retained exact prime windows V2.2.

Parent: f86af1f59c3095ee13877dae7f91b3c5a8b637f4.
This file uses the actual V2 mixed form and the special translated profile from
`WeilThreeBlockTranslatedPacketsV22`.

For width 1/32:
  * the diagonal prime sum has no m>=2 sample;
  * the adjacent (+,0) mixed sum has exactly m=2;
  * the outer (+,-) mixed sum has exactly m=4;
  * every reciprocal branch is zero.

No PNT, zero statistics, Archimedean B-bound, global Weil sign, or RH is used.
-/

open Set Function MeasureTheory Complex
open scoped ComplexConjugate
set_option autoImplicit false
noncomputable section

namespace AEGIS.WeilThreeBlockPrimeWindowsV22

open AEGIS.WeilMixedClosureV2
open AEGIS.WeilDisjointEnergyV2
open AEGIS.WeilThreeBlockAnalyticConstantsV21
open AEGIS.WeilThreeBlockTranslatedPacketsV22

/-- If a packet is nonzero at positive x, its log lies in its declared log-support interval. -/
theorem log_mem_of_packet_ne_zero
    (g : WeilCompactSmoothGV1) {lo hi x : ℝ}
    (hI : LogSupportIn g lo hi) (hx : 0 < x) (hg : g.1 x ≠ 0) :
    Real.log x ∈ Icc lo hi :=
  AEGIS.WeilThreeBlockTranslatedPacketsV22.log_mem_of_ne_zero g hI hx hg

/-- The actual mixed V2 integral vanishes if log x lies outside the support-difference interval. -/
theorem mixed_eq_zero_of_log_outside
    (p q : WeilCompactSmoothGV1)
    {plo phi qlo qhi x : ℝ}
    (hp : LogSupportIn p plo phi)
    (hq : LogSupportIn q qlo qhi)
    (hx : 0 < x)
    (hout : Real.log x < plo - qhi ∨ phi - qlo < Real.log x) :
    mixed p q x = 0 := by
  unfold mixed
  apply integral_eq_zero_of_ae
  filter_upwards [] with y
  by_cases hy : 0 < y
  · by_cases hqy : q.1 y = 0
    · simp [hqy]
    · have hqlog := log_mem_of_packet_ne_zero q hq hy hqy
      by_cases hpxy : p.1 (x * y) = 0
      · simp [hpxy]
      · have hxy : 0 < x * y := mul_pos hx hy
        have hplog := log_mem_of_packet_ne_zero p hp hxy hpxy
        have hlogmul : Real.log (x * y) = Real.log x + Real.log y := by
          rw [Real.log_mul hx.ne' hy.ne']
        rw [hlogmul] at hplog
        rcases hout with hout | hout
        · exfalso
          linarith [hplog.1, hqlog.2]
        · exfalso
          linarith [hplog.2, hqlog.1]
  · have hqy : q.1 y = 0 := packet_eq_zero_of_nonpos q (le_of_not_gt hy)
    simp [hqy]

/-- Exact scaling identity for the actual V2 mixed form under the retained translations. -/
theorem mixed_translate_scale
    (g : WeilCompactSmoothGV1) (di dj x : ℝ) :
    mixed (translatePacket g di) (translatePacket g dj) x =
      (Real.exp ((dj - di) / 2) : ℂ) *
        mixed g g (Real.exp (dj - di) * x) := by
  unfold mixed
  let F : ℝ → ℂ := fun y =>
    (translatePacket g di).1 (x * y) * star ((translatePacket g dj).1 y)
  have hchange := integral_comp_mul_left_Ioi' F 0 (Real.exp_pos dj)
  rw [mul_zero] at hchange
  rw [← hchange, Complex.real_smul]
  have hfun :
      (fun y : ℝ => F (Real.exp dj * y)) =
        fun y : ℝ =>
          (Real.exp ((dj - di) / 2) : ℂ) /
              (Real.exp dj : ℂ) *
            (g.1 ((Real.exp (dj - di) * x) * y) * star (g.1 y)) := by
    funext y
    unfold F
    simp only [translatePacket_apply, map_mul, Complex.star_def, Complex.conj_ofReal]
    have h1 : Real.exp (-dj) * (Real.exp dj * y) = y := by
      calc
        Real.exp (-dj) * (Real.exp dj * y)
            = (Real.exp (-dj) * Real.exp dj) * y := by ring
        _ = y := by rw [← Real.exp_add]; simp
    have h2 : Real.exp (-di) * (x * (Real.exp dj * y)) =
        (Real.exp (dj - di) * x) * y := by
      rw [show Real.exp (dj - di) = Real.exp (-di) * Real.exp dj by
        rw [← Real.exp_add]; congr 1; ring]
      ring
    rw [h1, h2]
    have hcoef :
        (Real.exp dj : ℂ) *
          ((Real.exp (-di / 2) : ℂ) * (Real.exp (-dj / 2) : ℂ)) =
          (Real.exp ((dj - di) / 2) : ℂ) := by
      rw [← Complex.ofReal_mul, ← Complex.ofReal_mul, ← Real.exp_add, ← Real.exp_add]
      congr 1
      ring
    have hneC : (Real.exp dj : ℂ) ≠ 0 := by simp
    have hcoef' :
        (Real.exp (-di / 2) : ℂ) * (Real.exp (-dj / 2) : ℂ) =
          (Real.exp ((dj - di) / 2) : ℂ) / (Real.exp dj : ℂ) := by
      apply (eq_div_iff hneC).2
      simpa [mul_comm, mul_left_comm, mul_assoc] using hcoef
    rw [hcoef']
    ring
  rw [hfun, integral_const_mul]
  have hne : (Real.exp dj : ℂ) ≠ 0 := by simp
  field_simp [hne]

/-- The base mixed value at x=1 is exactly the repository L2 energy. -/
theorem mixed_self_one_eq_energy (g : WeilCompactSmoothGV1) :
    mixed g g 1 = (energy g.1 : ℂ) := by
  unfold mixed
  simp only [one_mul]
  rw [AEGIS.WeilLogCoordinateIsometryV21.packet_energy_eq_positive_energy g]
  rw [← integral_ofReal]
  apply setIntegral_congr_fun measurableSet_Ioi
  intro y hy
  simp [Complex.star_def, Complex.mul_conj, Complex.sq_norm]

/-- Elementary 1/32 window constants not already needed by V2.1. -/
theorem exp_one_thirty_two_lt_thirty_two_over_thirty_one :
    Real.exp (1 / 32 : ℝ) < (32 / 31 : ℝ) := by
  calc
    Real.exp (1 / 32 : ℝ)
        < 1 / (1 - (1 / 32 : ℝ)) :=
      Real.exp_bound_div_one_sub_of_interval' (by norm_num) (by norm_num)
    _ = (32 / 31 : ℝ) := by norm_num

theorem log_three_halves_gt_one_thirty_two :
    (1 / 32 : ℝ) < Real.log (3 / 2 : ℝ) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num : (0 : ℝ) < 3 / 2)]
  exact exp_one_thirty_two_lt_thirty_two_over_thirty_one.trans (by norm_num)

theorem log_four_thirds_gt_one_thirty_two :
    (1 / 32 : ℝ) < Real.log (4 / 3 : ℝ) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num : (0 : ℝ) < 4 / 3)]
  exact exp_one_thirty_two_lt_thirty_two_over_thirty_one.trans (by norm_num)

theorem log_five_fourths_gt_one_thirty_two :
    (1 / 32 : ℝ) < Real.log (5 / 4 : ℝ) := by
  rw [Real.lt_log_iff_exp_lt (by norm_num : (0 : ℝ) < 5 / 4)]
  exact exp_one_thirty_two_lt_thirty_two_over_thirty_one.trans (by norm_num)

theorem vonMangoldt_two : ArithmeticFunction.vonMangoldt 2 = Real.log 2 := by
  exact ArithmeticFunction.vonMangoldt_apply_prime (by norm_num)

theorem vonMangoldt_four : ArithmeticFunction.vonMangoldt 4 = Real.log 2 := by
  calc
    ArithmeticFunction.vonMangoldt 4
        = ArithmeticFunction.vonMangoldt (2 ^ 2) := by norm_num
    _ = ArithmeticFunction.vonMangoldt 2 :=
      ArithmeticFunction.vonMangoldt_apply_pow (by norm_num)
    _ = Real.log 2 := vonMangoldt_two

theorem exp_neg_half_log_two_eq_inv_sqrt_two :
    Real.exp (-Real.log 2 / 2) = 1 / Real.sqrt 2 := by
  have hsq : (Real.exp (Real.log 2 / 2)) ^ 2 = (2 : ℝ) := by
    rw [pow_two, ← Real.exp_add]
    convert Real.exp_log (show (0 : ℝ) < 2 by norm_num) using 1 <;> ring
  have hsqrt : (Real.sqrt 2) ^ 2 = (2 : ℝ) := Real.sq_sqrt (by norm_num)
  have heq : Real.exp (Real.log 2 / 2) = Real.sqrt 2 := by
    have hp : 0 < Real.exp (Real.log 2 / 2) := Real.exp_pos _
    have hs : 0 ≤ Real.sqrt 2 := Real.sqrt_nonneg _
    nlinarith
  rw [show -Real.log 2 / 2 = -(Real.log 2 / 2) by ring, Real.exp_neg, heq]
  simp [one_div]

/-- Base diagonal autocorrelation samples vanish for every m>=2 and reciprocal m^-1. -/
theorem diagonal_samples_zero
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a)
    {m : ℕ} (hm : 2 ≤ m) :
    WeilAutocorrelationV1 g (m : ℝ) = 0 ∧
      WeilAutocorrelationV1 g ((m : ℝ)⁻¹) = 0 := by
  have hmpos : (0 : ℝ) < (m : ℝ) := by positivity
  have hlogm : (1 / 32 : ℝ) < Real.log (m : ℝ) := by
    have h2m : (2 : ℝ) ≤ (m : ℝ) := by exact_mod_cast hm
    exact log_two_gt_one_thirty_two.trans_le (Real.log_le_log (by norm_num) h2m)
  have hdiag : LogSupportIn g (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) := hw
  constructor
  · rw [← diagonal_eq]
    apply mixed_eq_zero_of_log_outside g g hdiag hdiag hmpos
    right
    linarith
  · rw [← diagonal_eq]
    apply mixed_eq_zero_of_log_outside g g hdiag hdiag (inv_pos.mpr hmpos)
    left
    rw [Real.log_inv]
    linarith

theorem diagonal_prime_sum_zero
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a) :
    WeilPrimeSumV1 (WeilAutocorrelationV1 g) = 0 := by
  unfold WeilPrimeSumV1
  have hterm : ∀ n : ℕ, WeilPrimeTermV1 (WeilAutocorrelationV1 g) n = 0 := by
    intro n
    by_cases hn : n = 0
    · subst n
      simp [WeilPrimeTermV1]
    · have hm : 2 ≤ n + 1 := by omega
      rcases diagonal_samples_zero g a hw hm with ⟨hp, hi⟩
      unfold WeilPrimeTermV1
      change ((ArithmeticFunction.vonMangoldt (n + 1) : ℝ) : ℂ) *
        (WeilAutocorrelationV1 g ((n + 1 : ℕ) : ℝ) +
          (1 / ((n + 1 : ℕ) : ℂ)) *
            WeilAutocorrelationV1 g (((n + 1 : ℕ) : ℝ)⁻¹)) = 0
      rw [hp, hi]
      ring
  simp [hterm]

/-- Adjacent and outer actual V2 mixed functions. -/
def adjacent (g : WeilCompactSmoothGV1) : ℝ → ℂ := mixed (gPlus g) (gZero g)
def outer (g : WeilCompactSmoothGV1) : ℝ → ℂ := mixed (gPlus g) (gMinus g)

/-- Exact resonant values from the retained translation normalization. -/
theorem adjacent_two_eq
    (g : WeilCompactSmoothGV1) :
    adjacent g 2 = (1 / Real.sqrt 2 : ℝ) * (energy g.1 : ℂ) := by
  unfold adjacent gPlus gZero
  rw [mixed_translate_scale]
  rw [show Real.exp (0 - Real.log 2) * 2 = (1 : ℝ) by
    rw [zero_sub, Real.exp_neg, Real.exp_log (by norm_num : (0 : ℝ) < 2)]; norm_num]
  rw [mixed_self_one_eq_energy]
  rw [show (0 - Real.log 2) / 2 = -Real.log 2 / 2 by ring]
  rw [exp_neg_half_log_two_eq_inv_sqrt_two]
  norm_num

theorem outer_four_eq
    (g : WeilCompactSmoothGV1) :
    outer g 4 = (1 / 2 : ℝ) * (energy g.1 : ℂ) := by
  unfold outer gPlus gMinus
  rw [mixed_translate_scale]
  have hexp4 : Real.exp (2 * Real.log 2) = (4 : ℝ) := by
    rw [show 2 * Real.log 2 = Real.log 2 + Real.log 2 by ring,
      Real.exp_add, Real.exp_log (by norm_num : (0 : ℝ) < 2),
      Real.exp_log (by norm_num : (0 : ℝ) < 2)]
    norm_num
  have harg : Real.exp (-Real.log 2 - Real.log 2) * 4 = (1 : ℝ) := by
    rw [show -Real.log 2 - Real.log 2 = -(2 * Real.log 2) by ring,
      Real.exp_neg, hexp4]
    norm_num
  rw [harg, mixed_self_one_eq_energy]
  have hcoef : Real.exp ((-Real.log 2 - Real.log 2) / 2) = (1 / 2 : ℝ) := by
    rw [show (-Real.log 2 - Real.log 2) / 2 = -Real.log 2 by ring,
      Real.exp_neg, Real.exp_log (by norm_num : (0 : ℝ) < 2)]
    norm_num
  rw [hcoef]

/-- All non-resonant adjacent samples vanish. -/
theorem adjacent_sample_zero_of_ne_two
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a)
    {m : ℕ} (hm : 1 ≤ m) (hne : m ≠ 2) :
    adjacent g (m : ℝ) = 0 := by
  unfold adjacent
  have hp := translate_logSupportIn g (Real.log 2)
    (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) hw
  have hq := translate_logSupportIn g 0
    (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) hw
  have hmpos : (0 : ℝ) < (m : ℝ) := by exact_mod_cast (show 0 < m by omega)
  apply mixed_eq_zero_of_log_outside (gPlus g) (gZero g) hp hq hmpos
  by_cases hm1 : m = 1
  · subst m
    left
    have hlog2 := log_two_gt_one_thirty_two
    norm_num
    linarith
  · have hm3 : 3 ≤ m := by omega
    right
    have hlog3 : Real.log 3 - Real.log 2 > (1 / 32 : ℝ) := by
      rw [← Real.log_div (by norm_num : (3 : ℝ) ≠ 0) (by norm_num : (2 : ℝ) ≠ 0)]
      norm_num
      exact log_three_halves_gt_one_thirty_two
    have hmon : Real.log 3 ≤ Real.log (m : ℝ) :=
      Real.log_le_log (by norm_num) (by exact_mod_cast hm3)
    linarith

theorem adjacent_inv_sample_zero
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a)
    {m : ℕ} (hm : 2 ≤ m) :
    adjacent g ((m : ℝ)⁻¹) = 0 := by
  unfold adjacent
  have hp := translate_logSupportIn g (Real.log 2)
    (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) hw
  have hq := translate_logSupportIn g 0
    (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) hw
  have hmpos : (0 : ℝ) < (m : ℝ) := by positivity
  apply mixed_eq_zero_of_log_outside (gPlus g) (gZero g) hp hq (inv_pos.mpr hmpos)
  left
  rw [Real.log_inv]
  have hlog2 := log_two_gt_one_thirty_two
  have hmon : Real.log 2 ≤ Real.log (m : ℝ) :=
    Real.log_le_log (by norm_num) (by exact_mod_cast hm)
  linarith

theorem adjacent_prime_sum
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a) :
    WeilPrimeSumV1 (adjacent g) =
      ((Real.log 2 / Real.sqrt 2 : ℝ) : ℂ) * (energy g.1 : ℂ) := by
  unfold WeilPrimeSumV1
  rw [tsum_eq_single 1]
  · change ((ArithmeticFunction.vonMangoldt 2 : ℝ) : ℂ) *
      (adjacent g 2 + (1 / (2 : ℂ)) * adjacent g ((2 : ℝ)⁻¹)) =
        ((Real.log 2 / Real.sqrt 2 : ℝ) : ℂ) * (energy g.1 : ℂ)
    rw [vonMangoldt_two, adjacent_two_eq]
    have hi : adjacent g ((2 : ℝ)⁻¹) = 0 :=
      adjacent_inv_sample_zero g a hw (by norm_num)
    rw [hi]
    norm_num
    ring
  · intro n hn
    unfold WeilPrimeTermV1
    by_cases hn0 : n = 0
    · subst n
      simp
    · have hm : 2 ≤ n + 1 := by omega
      have hpos : adjacent g ((n + 1 : ℕ) : ℝ) = 0 := by
        apply adjacent_sample_zero_of_ne_two g a hw (by omega)
        omega
      have hinv : adjacent g (((n + 1 : ℕ) : ℝ)⁻¹) = 0 :=
        adjacent_inv_sample_zero g a hw hm
      change ((ArithmeticFunction.vonMangoldt (n + 1) : ℝ) : ℂ) *
        (adjacent g ((n + 1 : ℕ) : ℝ) +
          (1 / ((n + 1 : ℕ) : ℂ)) *
            adjacent g (((n + 1 : ℕ) : ℝ)⁻¹)) = 0
      rw [hpos, hinv]
      ring

/-- All non-resonant outer positive samples vanish; all reciprocal m>=2 samples vanish. -/
theorem outer_sample_zero_of_ne_four
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a)
    {m : ℕ} (hm : 2 ≤ m) (hne : m ≠ 4) :
    outer g (m : ℝ) = 0 := by
  unfold outer
  have hp := translate_logSupportIn g (Real.log 2)
    (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) hw
  have hq := translate_logSupportIn g (-Real.log 2)
    (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) hw
  have hmpos : (0 : ℝ) < (m : ℝ) := by positivity
  apply mixed_eq_zero_of_log_outside (gPlus g) (gMinus g) hp hq hmpos
  by_cases hle : m ≤ 3
  · left
    have hmon : Real.log (m : ℝ) ≤ Real.log 3 :=
      Real.log_le_log (by positivity) (by exact_mod_cast hle)
    have hgap : (1 / 32 : ℝ) < Real.log 4 - Real.log 3 := by
      rw [← Real.log_div (by norm_num : (4 : ℝ) ≠ 0) (by norm_num : (3 : ℝ) ≠ 0)]
      norm_num
      exact log_four_thirds_gt_one_thirty_two
    have hlog4 : Real.log 4 = 2 * Real.log 2 := by
      calc
        Real.log 4 = Real.log ((2 : ℝ)^2) := by norm_num
        _ = 2 * Real.log 2 := by rw [Real.log_pow]; norm_num
    linarith
  · right
    have hm5 : 5 ≤ m := by omega
    have hmon : Real.log 5 ≤ Real.log (m : ℝ) :=
      Real.log_le_log (by norm_num) (by exact_mod_cast hm5)
    have hgap : (1 / 32 : ℝ) < Real.log 5 - Real.log 4 := by
      rw [← Real.log_div (by norm_num : (5 : ℝ) ≠ 0) (by norm_num : (4 : ℝ) ≠ 0)]
      norm_num
      exact log_five_fourths_gt_one_thirty_two
    have hlog4 : Real.log 4 = 2 * Real.log 2 := by
      calc
        Real.log 4 = Real.log ((2 : ℝ)^2) := by norm_num
        _ = 2 * Real.log 2 := by rw [Real.log_pow]; norm_num
    linarith

theorem outer_inv_sample_zero
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a)
    {m : ℕ} (hm : 2 ≤ m) :
    outer g ((m : ℝ)⁻¹) = 0 := by
  unfold outer
  have hp := translate_logSupportIn g (Real.log 2)
    (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) hw
  have hq := translate_logSupportIn g (-Real.log 2)
    (a - (1 / 64 : ℝ)) (a + (1 / 64 : ℝ)) hw
  have hmpos : (0 : ℝ) < (m : ℝ) := by positivity
  apply mixed_eq_zero_of_log_outside (gPlus g) (gMinus g) hp hq (inv_pos.mpr hmpos)
  left
  rw [Real.log_inv]
  have hlog2 := log_two_gt_one_thirty_two
  have hmon : Real.log 2 ≤ Real.log (m : ℝ) :=
    Real.log_le_log (by norm_num) (by exact_mod_cast hm)
  linarith

theorem outer_prime_sum
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a) :
    WeilPrimeSumV1 (outer g) =
      (((Real.log 2) / 2 : ℝ) : ℂ) * (energy g.1 : ℂ) := by
  unfold WeilPrimeSumV1
  rw [tsum_eq_single 3]
  · change ((ArithmeticFunction.vonMangoldt 4 : ℝ) : ℂ) *
      (outer g 4 + (1 / (4 : ℂ)) * outer g ((4 : ℝ)⁻¹)) =
        (((Real.log 2) / 2 : ℝ) : ℂ) * (energy g.1 : ℂ)
    rw [vonMangoldt_four, outer_four_eq]
    have hi : outer g ((4 : ℝ)⁻¹) = 0 :=
      outer_inv_sample_zero g a hw (by norm_num)
    rw [hi]
    norm_num
    ring
  · intro n hn
    unfold WeilPrimeTermV1
    by_cases hn0 : n = 0
    · subst n
      simp
    · have hm : 2 ≤ n + 1 := by omega
      have hpos : outer g ((n + 1 : ℕ) : ℝ) = 0 := by
        apply outer_sample_zero_of_ne_four g a hw hm
        omega
      have hinv : outer g (((n + 1 : ℕ) : ℝ)⁻¹) = 0 :=
        outer_inv_sample_zero g a hw hm
      change ((ArithmeticFunction.vonMangoldt (n + 1) : ℝ) : ℂ) *
        (outer g ((n + 1 : ℕ) : ℝ) +
          (1 / ((n + 1 : ℕ) : ℂ)) *
            outer g (((n + 1 : ℕ) : ℝ)⁻¹)) = 0
      rw [hpos, hinv]
      ring

#print axioms mixed_translate_scale
#print axioms diagonal_prime_sum_zero
#print axioms adjacent_prime_sum
#print axioms outer_prime_sum

end AEGIS.WeilThreeBlockPrimeWindowsV22
