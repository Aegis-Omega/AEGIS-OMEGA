import Mathlib.Data.Finset.Lattice.Basic
import Mathlib.Data.Finset.Image

namespace AEGIS.VerifiedSemanticQuotientConsensusV1

def quotientClaims
    {α β : Type}
    [DecidableEq β]
    (q : α → β)
    (claims : Finset α) : Finset β :=
  claims.image q

def quotientConsensus
    {α β : Type}
    [DecidableEq β]
    (q : α → β)
    (left right : Finset α) : Finset β :=
  quotientClaims q left ∩ quotientClaims q right

theorem retained_class_has_sound_pair
    {α β : Type}
    [DecidableEq α]
    [DecidableEq β]
    (q : α → β)
    (SemEq : α → α → Prop)
    (hsound : ∀ a b, q a = q b → SemEq a b)
    {left right : Finset α}
    {cls : β}
    (hcls : cls ∈ quotientConsensus q left right) :
    ∃ a ∈ left, ∃ b ∈ right,
      q a = cls ∧ q b = cls ∧ SemEq a b := by
  have hparts := Finset.mem_inter.mp hcls
  rcases Finset.mem_image.mp hparts.1 with ⟨a, ha, hqa⟩
  rcases Finset.mem_image.mp hparts.2 with ⟨b, hb, hqb⟩
  refine ⟨a, ha, b, hb, hqa, hqb, ?_⟩
  exact hsound a b (hqa.trans hqb.symm)

theorem no_retained_class_without_left_witness
    {α β : Type}
    [DecidableEq α]
    [DecidableEq β]
    (q : α → β)
    {left right : Finset α}
    {cls : β}
    (hcls : cls ∈ quotientConsensus q left right) :
    ∃ a ∈ left, q a = cls := by
  have hleft := (Finset.mem_inter.mp hcls).1
  exact Finset.mem_image.mp hleft

theorem no_retained_class_without_right_witness
    {α β : Type}
    [DecidableEq α]
    [DecidableEq β]
    (q : α → β)
    {left right : Finset α}
    {cls : β}
    (hcls : cls ∈ quotientConsensus q left right) :
    ∃ b ∈ right, q b = cls := by
  have hright := (Finset.mem_inter.mp hcls).2
  exact Finset.mem_image.mp hright

end AEGIS.VerifiedSemanticQuotientConsensusV1

#print axioms AEGIS.VerifiedSemanticQuotientConsensusV1.retained_class_has_sound_pair
#print axioms AEGIS.VerifiedSemanticQuotientConsensusV1.no_retained_class_without_left_witness
#print axioms AEGIS.VerifiedSemanticQuotientConsensusV1.no_retained_class_without_right_witness
