import Mathlib

/-!
# Diagonal log-gain, sub-lemma S1 (Mathlib only)

For `h : ℝ → ℂ` measurable and zero outside `[lo, lo + L]` (`L > 0`),

  log 2 · ∫ ‖h‖²  ≤  ∫_{s ∈ (0,L]} (1/(2s)) · ∫ ‖h(x+s) − h(x)‖² dx ds.

The bound does not depend on `L` (the form is scale invariant).

Since `∫ ‖h(x+s) − h(x)‖² = 2(E − Re C(s))` (with `E = ∫‖h‖²`, `C(s) = ∫ h(x+s) conj h(x)`),
the right-hand side is `∫_0^1 (E − Re C(s))/s ds`, the inner Archimedean diagonal term in
log coordinates (`∫_0^L (E − Re C(s))/s ds`). The statement is in `ℝ≥0∞`, so no integrability hypothesis is needed.

Proof: write `b = lo + L`. On `(b−s, b]` the shifted term vanishes and on `[lo−s, lo)` the
unshifted one does, so the inner integral is at least `∫_{(b−s,b]} ‖h‖² + ∫_{[lo,lo+s)} ‖h‖²`;
Tonelli turns the weight `1/(2s)` into `(log(L/(b−x)) + log(L/(x−lo)))/2 ≥ log 2` on `(lo,b)`.

This is analysis only. It is not a Weil-positivity statement and not RH.
-/

open MeasureTheory Set

noncomputable section

namespace AEGIS.WeilDiagonalLogGainS1

/-- Pointwise energy density. -/
def F (h : ℝ → ℂ) (x : ℝ) : ENNReal := ENNReal.ofReal (‖h x‖ ^ 2)

/-- Weight `1/(2s)`. -/
def w (s : ℝ) : ENNReal := ENNReal.ofReal (1 / (2 * s))

/-- Step 1: the shift difference dominates the two boundary layers. -/
theorem boundary_layers (h : ℝ → ℂ) (lo L : ℝ)
    (hs : ∀ x, x ∉ Icc lo (lo + L) → h x = 0)
    {s : ℝ} (hs1 : s ≤ L) :
    (∫⁻ x in Ioc (lo + L - s) (lo + L), F h x) + ∫⁻ x in Ico lo (lo + s), F h x ≤
      ∫⁻ x, ENNReal.ofReal (‖h (x + s) - h x‖ ^ 2) := by
  set G : ℝ → ENNReal := fun x => ENNReal.ofReal (‖h (x + s) - h x‖ ^ 2) with hG
  have p1 : (∫⁻ x in Ioc (lo + L - s) (lo + L), F h x) =
      ∫⁻ x in Ioc (lo + L - s) (lo + L), G x := by
    apply setLIntegral_congr_fun measurableSet_Ioc
    intro x hx
    have : h (x + s) = 0 := hs _ (fun hm => by linarith [hm.2, hx.1])
    simp [F, hG, this]
  have p2 : (∫⁻ x in Ico lo (lo + s), F h x) = ∫⁻ x in Ico (lo - s) lo, G x := by
    have e1 : (∫⁻ x in Ico (lo - s) lo, G x) = ∫⁻ x in Ico (lo - s) lo, F h (x + s) := by
      apply setLIntegral_congr_fun measurableSet_Ico
      intro x hx
      have : h x = 0 := hs _ (fun hm => by linarith [hm.1, hx.2])
      simp [F, hG, this]
    rw [e1, ← lintegral_indicator measurableSet_Ico, ← lintegral_indicator measurableSet_Ico]
    have e2 : (fun x => (Ico (lo - s) lo).indicator (fun x => F h (x + s)) x) =
        fun x => (Ico lo (lo + s)).indicator (F h) (x + s) := by
      funext x
      have hmem : x ∈ Ico (lo - s) lo ↔ x + s ∈ Ico lo (lo + s) := by
        simp only [mem_Ico]
        constructor <;> intro hh <;> constructor <;> linarith [hh.1, hh.2]
      by_cases hx : x ∈ Ico (lo - s) lo
      · rw [indicator_of_mem hx, indicator_of_mem (hmem.mp hx)]
      · rw [indicator_of_notMem hx, indicator_of_notMem (fun hh => hx (hmem.mpr hh))]
    rw [e2, lintegral_add_right_eq_self (fun y => (Ico lo (lo + s)).indicator (F h) y) s]
  have hdisj : Disjoint (Ioc (lo + L - s) (lo + L)) (Ico (lo - s) lo) := by
    rw [Set.disjoint_left]
    intro x h1 h2
    linarith [h1.1, h2.2]
  rw [p1, p2, ← lintegral_union measurableSet_Ico hdisj]
  exact setLIntegral_le_lintegral _ _

/-- `∫_{(a,L]} 1/(2s) ds = log(L/a)/2` for `0 < a ≤ L`, as a lower integral. -/
theorem lintegral_w (a L : ℝ) (ha : 0 < a) (haL : a ≤ L) :
    (∫⁻ s in Ioc a L, w s) = ENNReal.ofReal (Real.log (L / a) / 2) := by
  have hint : IntegrableOn (fun s : ℝ => 1 / (2 * s)) (Ioc a L) := by
    have hc : ContinuousOn (fun s : ℝ => 1 / (2 * s)) (Icc a L) := by
      apply ContinuousOn.div continuousOn_const (continuousOn_const.mul continuousOn_id)
      intro x hx; have : 0 < x := lt_of_lt_of_le ha hx.1
      exact mul_ne_zero two_ne_zero (ne_of_gt this)
    exact (hc.integrableOn_Icc).mono_set Ioc_subset_Icc_self
  have hnn : 0 ≤ᵐ[volume.restrict (Ioc a L)] fun s : ℝ => 1 / (2 * s) := by
    filter_upwards [ae_restrict_mem measurableSet_Ioc] with s hs
    have : 0 < s := lt_trans ha hs.1
    positivity
  unfold w
  rw [← ofReal_integral_eq_lintegral_ofReal hint hnn]
  congr 1
  have h1 : (∫ s in Ioc a L, 1 / (2 * s)) = (∫ s in a..L, 1 / s) / 2 := by
    rw [intervalIntegral.integral_of_le haL, ← integral_div]
    congr 1; funext s; ring
  rw [h1, integral_one_div_of_pos ha (lt_of_lt_of_le ha haL)]

/-- The kernel inequality at the core: `log(L/p) + log(L/q) ≥ 2 log 2` when `p + q = L`. -/
theorem log_sum_ge (L p q : ℝ) (hp : 0 < p) (hq : 0 < q) (hpq : p + q = L) :
    2 * Real.log 2 ≤ Real.log (L / p) + Real.log (L / q) := by
  have hL : 0 < L := by linarith
  rw [← Real.log_mul (by positivity) (by positivity)]
  have h4 : (4 : ℝ) ≤ L / p * (L / q) := by
    rw [div_mul_div_comm, le_div_iff₀ (by positivity), ← hpq]
    nlinarith [sq_nonneg (p - q)]
  calc 2 * Real.log 2 = Real.log 4 := by
        rw [show (4 : ℝ) = 2 ^ 2 by norm_num, Real.log_pow]; norm_num
    _ ≤ _ := Real.log_le_log (by norm_num) h4

/-- Indicator kernels written with `if`, so the joint function is visibly measurable. -/
def ind1 (lo L s x : ℝ) : ENNReal := if lo + L - s < x ∧ x ≤ lo + L then 1 else 0
def ind2 (lo s x : ℝ) : ENNReal := if lo ≤ x ∧ x < lo + s then 1 else 0

theorem kernel_ge (lo L x : ℝ) (hx0 : lo < x) (hx1 : x < lo + L) :
    ENNReal.ofReal (Real.log 2) ≤
      ∫⁻ s in Ioc (0 : ℝ) L, w s * (ind1 lo L s x + ind2 lo s x) := by
  have hA : (∫⁻ s in Ioc (lo + L - x) L, w s) ≤ ∫⁻ s in Ioc (0 : ℝ) L, w s * ind1 lo L s x := by
    calc (∫⁻ s in Ioc (lo + L - x) L, w s) = ∫⁻ s in Ioc (lo + L - x) L, w s * ind1 lo L s x := by
          apply setLIntegral_congr_fun measurableSet_Ioc
          intro s hs; simp [ind1, show lo + L - s < x by linarith [hs.1], hx1.le]
      _ ≤ _ := lintegral_mono_set (Ioc_subset_Ioc_left (by linarith))
  have hB : (∫⁻ s in Ioc (x - lo) L, w s) ≤ ∫⁻ s in Ioc (0 : ℝ) L, w s * ind2 lo s x := by
    calc (∫⁻ s in Ioc (x - lo) L, w s) = ∫⁻ s in Ioc (x - lo) L, w s * ind2 lo s x := by
          apply setLIntegral_congr_fun measurableSet_Ioc
          intro s hs; simp [ind2, hx0.le, show x < lo + s by linarith [hs.1]]
      _ ≤ _ := lintegral_mono_set (Ioc_subset_Ioc_left (by linarith))
  rw [lintegral_w (lo + L - x) L (by linarith) (by linarith)] at hA
  rw [lintegral_w (x - lo) L (by linarith) (by linarith)] at hB
  have hmeas : Measurable fun s : ℝ => w s * ind2 lo s x := by
    unfold w ind2
    apply Measurable.mul (ENNReal.measurable_ofReal.comp (by fun_prop))
    have hset : MeasurableSet {a : ℝ | lo ≤ x ∧ x < lo + a} :=
      (measurableSet_le (measurable_const : Measurable fun _ : ℝ => lo)
        (measurable_const : Measurable fun _ : ℝ => x)).inter
        (measurableSet_lt (measurable_const : Measurable fun _ : ℝ => x)
          (by fun_prop : Measurable fun a : ℝ => lo + a))
    exact Measurable.ite hset measurable_const measurable_const
  have hsplit : (∫⁻ s in Ioc (0 : ℝ) L, w s * (ind1 lo L s x + ind2 lo s x)) =
      (∫⁻ s in Ioc (0 : ℝ) L, w s * ind1 lo L s x) + ∫⁻ s in Ioc (0 : ℝ) L, w s * ind2 lo s x := by
    simp_rw [mul_add]
    exact lintegral_add_right _ hmeas
  rw [hsplit]
  have hL1 : 1 ≤ L / (lo + L - x) := by rw [le_div_iff₀ (by linarith)]; linarith
  have hL2 : 1 ≤ L / (x - lo) := by rw [le_div_iff₀ (by linarith)]; linarith
  have hl1 : 0 ≤ Real.log (L / (lo + L - x)) / 2 :=
    div_nonneg (Real.log_nonneg hL1) (by norm_num)
  have hl2 : 0 ≤ Real.log (L / (x - lo)) / 2 :=
    div_nonneg (Real.log_nonneg hL2) (by norm_num)
  calc ENNReal.ofReal (Real.log 2)
      ≤ ENNReal.ofReal (Real.log (L / (lo + L - x)) / 2 + Real.log (L / (x - lo)) / 2) := by
        apply ENNReal.ofReal_le_ofReal
        linarith [log_sum_ge L (lo + L - x) (x - lo) (by linarith) (by linarith) (by ring)]
    _ = ENNReal.ofReal (Real.log (L / (lo + L - x)) / 2) +
          ENNReal.ofReal (Real.log (L / (x - lo)) / 2) := ENNReal.ofReal_add hl1 hl2
    _ ≤ _ := add_le_add hA hB

/-- **S1.** The diagonal log-gain inequality on `[lo, lo + L]`. -/
theorem log_gain (h : ℝ → ℂ) (hm : Measurable h) (lo L : ℝ)
    (hs : ∀ x, x ∉ Icc lo (lo + L) → h x = 0) :
    ENNReal.ofReal (Real.log 2) * ∫⁻ x, F h x ≤
      ∫⁻ s in Ioc (0 : ℝ) L, w s * ∫⁻ x, ENNReal.ofReal (‖h (x + s) - h x‖ ^ 2) := by
  have hF : Measurable (F h) := by unfold F; fun_prop
  have hlayer : ∀ s, (∫⁻ x in Ioc (lo + L - s) (lo + L), F h x) +
      (∫⁻ x in Ico lo (lo + s), F h x) =
      ∫⁻ x, (ind1 lo L s x + ind2 lo s x) * F h x := by
    intro s
    rw [← lintegral_indicator measurableSet_Ioc, ← lintegral_indicator measurableSet_Ico,
      ← lintegral_add_left' (hF.indicator measurableSet_Ioc).aemeasurable]
    congr 1; funext x
    simp only [ind1, ind2, Set.indicator, mem_Ioc, mem_Ico, add_mul]
    split_ifs <;> simp
  have step1 : (∫⁻ s in Ioc (0 : ℝ) L, w s * ∫⁻ x, (ind1 lo L s x + ind2 lo s x) * F h x) ≤
      ∫⁻ s in Ioc (0 : ℝ) L, w s * ∫⁻ x, ENNReal.ofReal (‖h (x + s) - h x‖ ^ 2) := by
    apply lintegral_mono_ae
    filter_upwards [ae_restrict_mem measurableSet_Ioc] with s hsm
    rw [← hlayer s]
    gcongr
    exact boundary_layers h lo L hs hsm.2
  refine le_trans ?_ step1
  have hjoint : Measurable (Function.uncurry fun (s x : ℝ) =>
      w s * ((ind1 lo L s x + ind2 lo s x) * F h x)) := by
    unfold w ind1 ind2
    apply Measurable.mul (ENNReal.measurable_ofReal.comp (by fun_prop))
    apply Measurable.mul
    · apply Measurable.add
      · have hset : MeasurableSet {a : ℝ × ℝ | lo + L - a.1 < a.2 ∧ a.2 ≤ lo + L} :=
          (measurableSet_lt (by fun_prop : Measurable fun a : ℝ × ℝ => lo + L - a.1)
            (by fun_prop : Measurable fun a : ℝ × ℝ => a.2)).inter
            (measurableSet_le (by fun_prop : Measurable fun a : ℝ × ℝ => a.2)
              (measurable_const : Measurable fun _ : ℝ × ℝ => lo + L))
        exact Measurable.ite hset measurable_const measurable_const
      · have hset : MeasurableSet {a : ℝ × ℝ | lo ≤ a.2 ∧ a.2 < lo + a.1} :=
          (measurableSet_le (measurable_const : Measurable fun _ : ℝ × ℝ => lo)
            (by fun_prop : Measurable fun a : ℝ × ℝ => a.2)).inter
            (measurableSet_lt (by fun_prop : Measurable fun a : ℝ × ℝ => a.2)
              (by fun_prop : Measurable fun a : ℝ × ℝ => lo + a.1))
        exact Measurable.ite hset measurable_const measurable_const
    · exact hF.comp measurable_snd
  have hswap : (∫⁻ s in Ioc (0 : ℝ) L, w s * ∫⁻ x, (ind1 lo L s x + ind2 lo s x) * F h x) =
      ∫⁻ x, F h x * ∫⁻ s in Ioc (0 : ℝ) L, w s * (ind1 lo L s x + ind2 lo s x) := by
    have e : (∫⁻ s in Ioc (0 : ℝ) L, w s * ∫⁻ x, (ind1 lo L s x + ind2 lo s x) * F h x) =
        ∫⁻ s in Ioc (0 : ℝ) L, ∫⁻ x, w s * ((ind1 lo L s x + ind2 lo s x) * F h x) := by
      congr 1; funext s
      rw [lintegral_const_mul' (w s) _ (ENNReal.ofReal_ne_top : w s ≠ ⊤)]
    rw [e, lintegral_lintegral_swap hjoint.aemeasurable]
    congr 1; funext x
    rw [← lintegral_const_mul' (F h x) _ (ENNReal.ofReal_ne_top : F h x ≠ ⊤)]
    congr 1; funext s; ring
  rw [hswap]
  have hsupp : Function.support (F h) ⊆ Icc lo (lo + L) := by
    intro x hx
    by_contra hn
    exact hx (by simp [F, hs x hn])
  calc ENNReal.ofReal (Real.log 2) * ∫⁻ x, F h x
      = ENNReal.ofReal (Real.log 2) * ∫⁻ x in Ioo lo (lo + L), F h x := by
        rw [Measure.restrict_congr_set Ioo_ae_eq_Icc, setLIntegral_eq_of_support_subset hsupp]
    _ = ∫⁻ x in Ioo lo (lo + L), F h x * ENNReal.ofReal (Real.log 2) := by
        rw [lintegral_mul_const' _ _ ENNReal.ofReal_ne_top, mul_comm]
    _ ≤ ∫⁻ x in Ioo lo (lo + L), F h x *
          ∫⁻ s in Ioc (0 : ℝ) L, w s * (ind1 lo L s x + ind2 lo s x) := by
        apply lintegral_mono_ae
        filter_upwards [ae_restrict_mem measurableSet_Ioo] with x hx
        gcongr
        exact kernel_ge lo L x hx.1 hx.2
    _ ≤ _ := setLIntegral_le_lintegral _ _

end AEGIS.WeilDiagonalLogGainS1

#print axioms AEGIS.WeilDiagonalLogGainS1.boundary_layers
#print axioms AEGIS.WeilDiagonalLogGainS1.lintegral_w
#print axioms AEGIS.WeilDiagonalLogGainS1.log_sum_ge
#print axioms AEGIS.WeilDiagonalLogGainS1.kernel_ge
#print axioms AEGIS.WeilDiagonalLogGainS1.log_gain
