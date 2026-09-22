import Mathlib.Data.Finset.Card
import Mathlib.Data.Nat.Basic

namespace AEGIS.EpistemicAccountingV1

def composedUncertainty (hasLoss : Bool) (u1 u2 : Nat) : Nat :=
  if hasLoss then max u1 u2 else 0

theorem left_uncertainty_le_of_loss
    (u1 u2 : Nat) :
    u1 ≤ composedUncertainty true u1 u2 := by
  simp [composedUncertainty]

theorem right_uncertainty_le_of_loss
    (u1 u2 : Nat) :
    u2 ≤ composedUncertainty true u1 u2 := by
  simp [composedUncertainty]

theorem no_loss_uncertainty_zero
    (u1 u2 : Nat) :
    composedUncertainty false u1 u2 = 0 := by
  simp [composedUncertainty]

theorem card_disjoint_partition
    {α : Type} [DecidableEq α]
    (whole left right : Finset α)
    (hwhole : whole = left ∪ right)
    (hdisjoint : Disjoint left right) :
    whole.card = left.card + right.card := by
  subst whole
  exact Finset.card_union_of_disjoint hdisjoint

end AEGIS.EpistemicAccountingV1

#print axioms AEGIS.EpistemicAccountingV1.left_uncertainty_le_of_loss
#print axioms AEGIS.EpistemicAccountingV1.right_uncertainty_le_of_loss
#print axioms AEGIS.EpistemicAccountingV1.card_disjoint_partition
