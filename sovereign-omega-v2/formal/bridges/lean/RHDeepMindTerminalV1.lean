import AegisLiCriterionRebindV1

/-!
AEGIS Ω — current-head Li terminal for the DeepMind/Mathlib RH target.

The target type is Mathlib's `RiemannHypothesis`, which is exactly the
predicate used by Google DeepMind Formal Conjectures Millennium RH.

This module performs no proof promotion. It isolates the sole remaining
producer obligation after the unconditional Li criterion has been rebound:
nonnegativity of every Li–Keiper coefficient.
-/

namespace AEGIS.RHDeepMindTerminalV1

def LiNonnegativityV1 : Prop :=
  ∀ n : ℕ, 0 ≤ (LiCriterion.taylorCoeff LiCriterion.riemannXi n).re

theorem li_nonnegativity_iff_rh_v1 :
    LiNonnegativityV1 ↔ RiemannHypothesis := by
  simpa [LiNonnegativityV1] using
    AegisRhLiBridge.aegis_li_criterion_rh_iff_v1.symm

theorem li_nonnegativity_closes_rh_v1
    (h : LiNonnegativityV1) : RiemannHypothesis :=
  (li_nonnegativity_iff_rh_v1).mp h

theorem rh_implies_li_nonnegativity_v1
    (h : RiemannHypothesis) : LiNonnegativityV1 :=
  (li_nonnegativity_iff_rh_v1).mpr h

end AEGIS.RHDeepMindTerminalV1

#print axioms AEGIS.RHDeepMindTerminalV1.li_nonnegativity_iff_rh_v1
#print axioms AEGIS.RHDeepMindTerminalV1.li_nonnegativity_closes_rh_v1
