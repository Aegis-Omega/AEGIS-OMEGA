import Lc.LiCriterion.XiOrderBridge

/-!
AEGIS Ω — exact provider-bound Li criterion bridge v1.

The imported provider theorem is compiled only after rebinding its original
Mathlib pin to the AEGIS Lean/Mathlib environment and applying the separately
audited three-token compatibility patch in the hosted verification lane.

This module does not prove the Li-coefficient nonnegativity statement and
therefore does not prove the Riemann Hypothesis.  It only exposes the already
kernel-checked biconditional against Mathlib's `RiemannHypothesis` under an
AEGIS-owned theorem name.
-/

namespace AegisRhLiBridge

/-- The provider's unconditional Li criterion, rebound into the AEGIS evidence
surface. This is an equivalence theorem, not a proof of either side. -/
theorem aegis_li_criterion_rh_iff_v1 :
    RiemannHypothesis ↔
      (∀ n : ℕ, 0 ≤ (LiCriterion.taylorCoeff LiCriterion.riemannXi n).re) :=
  LiCriterion.li_criterion_rh_iff

end AegisRhLiBridge

#print axioms AegisRhLiBridge.aegis_li_criterion_rh_iff_v1
