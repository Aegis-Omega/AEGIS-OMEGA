/-
Adversarial controls for `WeilArchimedeanCothTailV1`.

A tail bound is worth nothing if the quantity it bounds is degenerate, so both
directions are pinned here rather than asserted in prose:

* the tail is a strictly positive real number, not a totalisation artefact;
* the tail is strictly BELOW `7 * log 2`.

The second is the one that matters. Without it, `6 * log 2 < tail` would be
consistent with the tail being unbounded, and the separation would carry no
information. With it the tail is sandwiched, `6 log 2 < tail < 7 log 2`, and
the certificate's constant is genuinely cleared by a finite margin.
-/
import WeilArchimedeanCothTailV1

open Set Filter MeasureTheory Real
open AEGIS.WeilArchimedeanCothTailV1

/-- The tail is a genuine positive number. -/
theorem coth_tail_pos : 0 < ∫ u in Ioi (1 / 32 : ℝ), 1 / Real.sinh u :=
  lt_trans (by positivity) six_log_two_lt_integral_one_div_sinh_Ioi

/-- **Negative control.**  The same tail is strictly below `7 * log 2`, so the
lower bound is a real separation and not slack against an unbounded quantity. -/
theorem coth_tail_lt_seven_log_two :
    (∫ u in Ioi (1 / 32 : ℝ), 1 / Real.sinh u) < 7 * Real.log 2 := by
  rw [integral_one_div_sinh_Ioi (by norm_num : (0:ℝ) < 1 / 32)]
  have hub : Real.exp (-(1 / 32 : ℝ)) ≤ 32 / 33 := by
    have h := Real.add_one_le_exp (1 / 32 : ℝ)
    have hpos : (0:ℝ) < Real.exp (1 / 32) := Real.exp_pos _
    rw [Real.exp_neg, inv_le_comm₀ hpos (by norm_num)]
    linarith
  have hlt1 : Real.exp (-(1 / 32 : ℝ)) < 1 := by
    rw [Real.exp_lt_one_iff]; norm_num
  have hden : (0:ℝ) < 1 - Real.exp (-(1 / 32 : ℝ)) := by linarith
  have hratio :
      (1 + Real.exp (-(1 / 32 : ℝ))) / (1 - Real.exp (-(1 / 32 : ℝ))) < 128 := by
    rw [div_lt_iff₀ hden]; linarith
  have h128 : Real.log 128 = 7 * Real.log 2 := by
    rw [show (128 : ℝ) = 2 ^ (7 : ℕ) by norm_num, Real.log_pow]; norm_num
  rw [← h128]
  exact Real.log_lt_log (by positivity) hratio

#print axioms coth_tail_pos
#print axioms coth_tail_lt_seven_log_two
