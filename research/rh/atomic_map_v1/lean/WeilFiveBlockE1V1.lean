import WeilFiveBlockCrossV1
import WeilDiagonalLogGainV1

open MeasureTheory Complex
open scoped ComplexConjugate
set_option autoImplicit false
noncomputable section

namespace AEGIS.WeilFiveBlockE1V1

open WeilDisjointEnergyV2 WeilMixedAlgebraV2
open WeilThreeBlockTranslatedPacketsV22 WeilDiagonalLogGainV1
open WeilFiveBlockPerronV1 WeilFiveBlockCrossV1

private def displacement (i : Fin 5) : ℝ := (i.val : ℝ) * Real.log 2

private def packet (g : WeilCompactSmoothGV1) (i : Fin 5) : WeilCompactSmoothGV1 :=
  translatePacket g (displacement i)

/-- Five dyadic translates of the same packet, with arbitrary complex coefficients. -/
def comb (g : WeilCompactSmoothGV1) (z : Fin 5 → ℂ) : WeilCompactSmoothGV1 :=
  addPacket (scalePacket (z 0) (packet g 0))
    (addPacket (scalePacket (z 1) (packet g 1))
      (addPacket (scalePacket (z 2) (packet g 2))
        (addPacket (scalePacket (z 3) (packet g 3)) (scalePacket (z 4) (packet g 4)))))

private theorem comb_apply (g : WeilCompactSmoothGV1) (z : Fin 5 → ℂ) (t : ℝ) :
    (comb g z).1 t = ∑ i : Fin 5, z i * (packet g i).1 t := by
  simp [comb, addPacket, scalePacket, Fin.sum_univ_succ]

private theorem expansion (g : WeilCompactSmoothGV1) (z : Fin 5 → ℂ) :
    (B (comb g z) (comb g z)).re =
      ∑ i : Fin 5, ∑ j : Fin 5, (z i * (conj (z j) * B (packet g i) (packet g j))).re := by
  calc
    _ = ∑ j : Fin 5, ∑ i : Fin 5, (star (z j) * (z i * B (packet g i) (packet g j))).re := by
      simp only [comb, B_add_left, B_add_right, B_scale_left, B_scale_right,
        Fin.sum_univ_succ, Fin.sum_univ_zero, add_zero, mul_add, Complex.add_re]
      rfl
    _ = _ := by
      rw [Finset.sum_comm]
      refine Finset.sum_congr rfl fun i _ => Finset.sum_congr rfl fun j _ => ?_
      change (conj (z j) * (z i * B (packet g i) (packet g j))).re = _
      rw [mul_left_comm]

private theorem gap (i j : Fin 5) (hij : i < j) :
    displacement j - displacement i = ((j.val - i.val : ℕ) : ℝ) * Real.log 2 := by
  rw [Nat.cast_sub (show i.val ≤ j.val from le_of_lt hij)]
  unfold displacement
  ring

private theorem ordered_gap (i j : Fin 5) (hij : i < j) :
    Real.log 2 ≤ displacement j - displacement i := by
  rw [gap i j hij]
  have hi : i.val < j.val := hij
  have hk : (1 : ℝ) ≤ ((j.val - i.val : ℕ) : ℝ) := by exact_mod_cast (show 1 ≤ j.val - i.val by omega)
  simpa using mul_le_mul_of_nonneg_right hk (Real.log_nonneg (by norm_num : (1 : ℝ) ≤ 2))

private theorem comb_energy (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) (z : Fin 5 → ℂ) :
    energy (comb g z).1 = energy g.1 * ∑ i : Fin 5, ‖z i‖ ^ 2 := by
  have ordered_disjoint (i j : Fin 5) (hij : i < j) (t : ℝ) :
      (packet g i).1 t = 0 ∨ (packet g j).1 t = 0 := by
    exact pointwise_disjoint_of_log_intervals _ _
      (translate_logSupportIn g (displacement i) _ _ hw)
      (translate_logSupportIn g (displacement j) _ _ hw)
      (by linarith [ordered_gap i j hij, log_two_gt_one_thirty_two]) t
  have pointwise (t : ℝ) : ‖(comb g z).1 t‖ ^ 2 =
      ∑ i : Fin 5, ‖z i‖ ^ 2 * ‖(packet g i).1 t‖ ^ 2 := by
    rw [comb_apply]
    by_cases h : ∃ i : Fin 5, (packet g i).1 t ≠ 0
    · obtain ⟨i, hi⟩ := h
      have hother (j : Fin 5) (hji : j ≠ i) : (packet g j).1 t = 0 := by
        rcases lt_or_gt_of_ne hji with hj | hj
        · exact (ordered_disjoint j i hj t).resolve_right hi
        · exact (ordered_disjoint i j hj t).resolve_left hi
      rw [Finset.sum_eq_single i, Finset.sum_eq_single i]
      · rw [norm_mul, mul_pow]
      · intro j _ hji
        simp [hother j hji]
      · simp
      · intro j _ hji
        simp [hother j hji]
      · simp
    · push Not at h
      simp [h]
  have hInt (i : Fin 5) : Integrable (fun t : ℝ => ‖(packet g i).1 t‖ ^ 2) := by
    apply Continuous.integrable_of_hasCompactSupport
    · exact ((packet g i).2.1.continuous.norm).pow 2
    · apply (packet g i).2.2.1.mono
      intro t ht
      change ‖(packet g i).1 t‖ ^ 2 ≠ 0 at ht
      change (packet g i).1 t ≠ 0
      intro hz
      exact ht (by simp [hz])
  unfold energy
  simp_rw [pointwise]
  rw [integral_finsetSum _ (fun i _ => (hInt i).const_mul _)]
  simp only [integral_const_mul]
  rw [Finset.mul_sum]
  refine Finset.sum_congr rfl fun i _ => ?_
  change ‖z i‖ ^ 2 * energy (packet g i).1 = energy g.1 * ‖z i‖ ^ 2
  rw [packet, translate_energy, mul_comm]

theorem five_block_bound_of_moments (g : WeilCompactSmoothGV1) (a : ℝ)
    (hw : WidthOneThirtyTwoAt g a) (hm : WeilMomentConditionsV1 g)
    (z : Fin 5 → ℂ) :
    (WeilExplicitRightSideV1 (WeilAutocorrelationV1 (comb g z))).re ≤
      -(17 / 100 : ℝ) * energy (comb g z).1 := by
  let E := energy g.1
  let x : Fin 5 → ℝ := fun i => ‖z i‖
  have hE : 0 ≤ E := energy_nonnegative _
  have hdiag (i : Fin 5) : (B (packet g i) (packet g i)).re ≤ -(17 / 10 : ℝ) * E := by
    have hwidth : WidthOneThirtyTwoAt (packet g i) (a + displacement i) := by
      unfold WidthOneThirtyTwoAt packet
      convert translate_logSupportIn g (displacement i) _ _ hw using 1 <;> ring
    have h := width_diagonal_log_gain_v1 (packet g i) _ hwidth
    rw [packet, translate_energy] at h
    change (103 / 100 + Real.exp (-(1 / 32 : ℝ)) * Real.log 2) * E ≤
      -(B (packet g i) (packet g i)).re at h
    linarith [mul_le_mul_of_nonneg_right log_gain_constant_gt.le hE]
  have hforward (i j : Fin 5) (hij : i < j) :
      ‖B (packet g i) (packet g j)‖ ≤ cross i j * E := by
    have hi : i.val < j.val := hij
    have hj := j.isLt
    have hk : 1 ≤ j.val - i.val := by omega
    have hk4 : j.val - i.val ≤ 4 := by omega
    simpa [packet, cross, Nat.sub_eq_zero_of_le hi.le] using
      translated_cross_bound g a (displacement i) (displacement j) hw hm
        (j.val - i.val) hk hk4 (gap i j hij)
  have entry (i j : Fin 5) :
      (z i * (conj (z j) * B (packet g i) (packet g j))).re ≤
        (if i = j then -(17 / 10 : ℝ) * E * x i ^ 2 else 0) +
        E * (cross i j * x i * x j) := by
    by_cases h : i = j
    · subst j
      rw [if_pos rfl, cross_self]
      simp only [zero_mul, mul_zero, add_zero]
      rw [← mul_assoc, Complex.mul_conj]
      change (((Complex.normSq (z i) : ℝ) : ℂ) * B (packet g i) (packet g i)).re ≤ _
      simp only [Complex.mul_re, Complex.ofReal_re, Complex.ofReal_im, zero_mul, sub_zero, ← Complex.sq_norm]
      exact (mul_le_mul_of_nonneg_left (hdiag i) (sq_nonneg (x i))).trans_eq (mul_comm _ _)
    · rw [if_neg h, zero_add]
      have hb : ‖B (packet g i) (packet g j)‖ ≤ cross i j * E := by
        rcases lt_or_gt_of_ne h with hlt | hlt
        · exact hforward i j hlt
        · rw [B_hermitian (packet g j) (packet g i), Complex.norm_conj, cross_symm]
          exact hforward j i hlt
      calc
        _ ≤ ‖z i * (conj (z j) * B (packet g i) (packet g j))‖ :=
          Complex.re_le_norm _
        _ = (x i * x j) * ‖B (packet g i) (packet g j)‖ := by
          simp only [x, norm_mul, Complex.norm_conj, mul_assoc]
        _ ≤ (x i * x j) * (cross i j * E) :=
          mul_le_mul_of_nonneg_left hb (mul_nonneg (norm_nonneg _) (norm_nonneg _))
        _ = _ := by ring
  change (B (comb g z) (comb g z)).re ≤ _
  rw [expansion, comb_energy g a hw]
  have hsum := Finset.sum_le_sum (s := Finset.univ) fun i (_ : i ∈ (Finset.univ : Finset (Fin 5))) =>
    Finset.sum_le_sum (s := Finset.univ) fun j (_ : j ∈ (Finset.univ : Finset (Fin 5))) => entry i j
  simp only [Finset.sum_add_distrib, Finset.sum_ite_eq, Finset.mem_univ, if_true,
    ← Finset.mul_sum] at hsum
  have hquad := mul_le_mul_of_nonneg_left (quadratic_bound x) hE
  change _ ≤ -(17 / 100 : ℝ) * (E * ∑ i : Fin 5, x i ^ 2)
  linarith

end AEGIS.WeilFiveBlockE1V1

#print axioms AEGIS.WeilFiveBlockE1V1.five_block_bound_of_moments
