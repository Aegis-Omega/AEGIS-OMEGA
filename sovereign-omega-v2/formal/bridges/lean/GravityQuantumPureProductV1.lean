import Mathlib.Data.Complex.Basic
import Mathlib.Tactic

namespace AEGIS.GravityQuantumPureProductV1

noncomputable section

def coeffDet (a00 a01 a10 a11 : ℂ) : ℂ :=
  a00 * a11 - a01 * a10

def IsPureProductCoeffs (a00 a01 a10 a11 : ℂ) : Prop :=
  ∃ x0 x1 y0 y1 : ℂ,
    a00 = x0 * y0 ∧
    a01 = x0 * y1 ∧
    a10 = x1 * y0 ∧
    a11 = x1 * y1

theorem pureProductCoeffs_imp_coeffDet_zero
    {a00 a01 a10 a11 : ℂ}
    (h : IsPureProductCoeffs a00 a01 a10 a11) :
    coeffDet a00 a01 a10 a11 = 0 := by
  rcases h with ⟨x0, x1, y0, y1, h00, h01, h10, h11⟩
  simp [coeffDet, h00, h01, h10, h11]
  ring

theorem coeffDet_zero_imp_pureProductCoeffs
    {a00 a01 a10 a11 : ℂ}
    (h : coeffDet a00 a01 a10 a11 = 0) :
    IsPureProductCoeffs a00 a01 a10 a11 := by
  by_cases h00 : a00 = 0
  · have hp : -(a01 * a10) = 0 := by
      simpa [coeffDet, h00] using h
    have hm : a01 * a10 = 0 := neg_eq_zero.mp hp
    rcases mul_eq_zero.mp hm with h01 | h10
    · refine ⟨0, 1, a10, a11, ?_, ?_, ?_, ?_⟩
      · simpa [h00]
      · simpa [h01]
      · simp
      · simp
    · refine ⟨a01, a11, 0, 1, ?_, ?_, ?_, ?_⟩
      · simpa [h00]
      · simp
      · simpa [h10]
      · simp
  · have hmul : a00 * a11 = a01 * a10 := sub_eq_zero.mp h
    refine ⟨1, a10 / a00, a00, a01, ?_, ?_, ?_, ?_⟩
    · simp
    · simp
    · field_simp [h00]
    · field_simp [h00]
      simpa [mul_comm, mul_left_comm, mul_assoc] using hmul.symm

theorem coeffDet_eq_zero_iff_pureProductCoeffs
    (a00 a01 a10 a11 : ℂ) :
    coeffDet a00 a01 a10 a11 = 0 ↔
      IsPureProductCoeffs a00 a01 a10 a11 := by
  constructor
  · exact coeffDet_zero_imp_pureProductCoeffs
  · exact pureProductCoeffs_imp_coeffDet_zero

theorem coeffDet_ne_zero_iff_not_pureProductCoeffs
    (a00 a01 a10 a11 : ℂ) :
    coeffDet a00 a01 a10 a11 ≠ 0 ↔
      ¬ IsPureProductCoeffs a00 a01 a10 a11 := by
  exact not_congr
    (coeffDet_eq_zero_iff_pureProductCoeffs a00 a01 a10 a11)

end

end AEGIS.GravityQuantumPureProductV1

#print axioms AEGIS.GravityQuantumPureProductV1.coeffDet_eq_zero_iff_pureProductCoeffs
#print axioms AEGIS.GravityQuantumPureProductV1.coeffDet_ne_zero_iff_not_pureProductCoeffs
