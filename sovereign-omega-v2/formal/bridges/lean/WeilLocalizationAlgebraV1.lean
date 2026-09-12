import Mathlib.Analysis.Complex.Norm
import Mathlib.Tactic

/-!
Finite-frame pointwise localization algebra.  The normalization assumptions
are explicit.  No assertion about an integral kernel, Mellin transport,
positivity of a zeta functional, or the Riemann Hypothesis is made here.
-/

open Complex
open scoped BigOperators ComplexConjugate

set_option autoImplicit false

noncomputable section

/-- Squared mismatch of two finite real frames. -/
def WeilFrameDefectV1 {ι : Type*} (s : Finset ι) (a b : ι → ℝ) : ℝ :=
  ∑ j ∈ s, (a j - b j) ^ 2

/-- A single complex weighted difference, with the cross term explicit. -/
theorem weil_weighted_difference_normsq_v1 (a b : ℝ) (z w : ℂ) :
    normSq ((a : ℂ) * z - (b : ℂ) * w) =
      a ^ 2 * normSq z + b ^ 2 * normSq w -
        (a * b) * (2 * (z * conj w).re) := by
  simp [Complex.normSq_apply, Complex.mul_re, Complex.mul_im]
  <;> ring

/-- The frame mismatch is exactly twice one minus the frame correlation. -/
theorem weil_frame_defect_eq_v1 {ι : Type*} (s : Finset ι) (a b : ι → ℝ)
    (ha : ∑ j ∈ s, (a j) ^ 2 = 1)
    (hb : ∑ j ∈ s, (b j) ^ 2 = 1) :
    WeilFrameDefectV1 s a b = 2 - 2 * ∑ j ∈ s, a j * b j := by
  unfold WeilFrameDefectV1
  calc
    (∑ j ∈ s, (a j - b j) ^ 2) =
        ∑ j ∈ s, ((a j) ^ 2 + (b j) ^ 2 - (a j * b j) * 2) := by
      apply Finset.sum_congr rfl
      intro j hj
      ring
    _ = 2 - 2 * ∑ j ∈ s, a j * b j := by
      simp only [Finset.sum_sub_distrib, Finset.sum_add_distrib, ← Finset.sum_mul]
      rw [ha, hb]
      ring

/-- The squared mismatch is nonnegative without a normalization assumption. -/
theorem weil_frame_defect_nonnegative_v1 {ι : Type*}
    (s : Finset ι) (a b : ι → ℝ) :
    0 ≤ WeilFrameDefectV1 s a b := by
  exact Finset.sum_nonneg (fun j _ => sq_nonneg (a j - b j))

/-- Two normalized real frames have squared mismatch at most four. -/
theorem weil_frame_defect_le_four_v1 {ι : Type*}
    (s : Finset ι) (a b : ι → ℝ)
    (ha : ∑ j ∈ s, (a j) ^ 2 = 1)
    (hb : ∑ j ∈ s, (b j) ^ 2 = 1) :
    WeilFrameDefectV1 s a b ≤ 4 := by
  unfold WeilFrameDefectV1
  calc
    (∑ j ∈ s, (a j - b j) ^ 2) ≤
        ∑ j ∈ s, ((a j) ^ 2 * 2 + (b j) ^ 2 * 2) := by
      apply Finset.sum_le_sum
      intro j hj
      nlinarith [sq_nonneg (a j + b j)]
    _ = 4 := by
      simp only [Finset.sum_add_distrib, ← Finset.sum_mul]
      rw [ha, hb]
      norm_num

/-- Nonnegative correlation improves the upper bound to two. -/
theorem weil_frame_defect_le_two_v1 {ι : Type*}
    (s : Finset ι) (a b : ι → ℝ)
    (ha : ∑ j ∈ s, (a j) ^ 2 = 1)
    (hb : ∑ j ∈ s, (b j) ^ 2 = 1)
    (hab : 0 ≤ ∑ j ∈ s, a j * b j) :
    WeilFrameDefectV1 s a b ≤ 2 := by
  rw [weil_frame_defect_eq_v1 s a b ha hb]
  linarith

/-- Exact finite-frame pointwise IMS identity.  Its defect cross term can
have either sign; this identity alone is not a positivity theorem. -/
theorem weil_frame_localization_identity_v1 {ι : Type*}
    (s : Finset ι) (a b : ι → ℝ) (z w : ℂ)
    (ha : ∑ j ∈ s, (a j) ^ 2 = 1)
    (hb : ∑ j ∈ s, (b j) ^ 2 = 1) :
    (∑ j ∈ s, normSq ((a j : ℂ) * z - (b j : ℂ) * w)) =
      normSq (z - w) + WeilFrameDefectV1 s a b * (z * conj w).re := by
  have hs : (∑ j ∈ s, normSq ((a j : ℂ) * z - (b j : ℂ) * w)) =
      normSq z + normSq w - (∑ j ∈ s, a j * b j) * (2 * (z * conj w).re) := by
    simp_rw [weil_weighted_difference_normsq_v1]
    simp only [Finset.sum_sub_distrib, Finset.sum_add_distrib, ← Finset.sum_mul]
    rw [ha, hb]
    ring
  have hd := weil_weighted_difference_normsq_v1 1 1 z w
  norm_num at hd
  rw [hs, weil_frame_defect_eq_v1 s a b ha hb, hd]
  simp [Complex.mul_re] <;> ring

#print axioms weil_weighted_difference_normsq_v1
#print axioms weil_frame_defect_eq_v1
#print axioms weil_frame_defect_nonnegative_v1
#print axioms weil_frame_defect_le_four_v1
#print axioms weil_frame_defect_le_two_v1
#print axioms weil_frame_localization_identity_v1
