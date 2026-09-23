import MultiAgentConservativeConsensusV1

namespace AEGIS.ConservativeConsensusCRDTV1

open AEGIS.NoFreeEpistemicGainV1
open AEGIS.MultiAgentConservativeConsensusV1

def SafetyLE {α : Type} [DecidableEq α]
    (x y : EpistemicState α) : Prop :=
  EpistemicLE y x

def merge {α : Type} [DecidableEq α]
    (x y : EpistemicState α) : EpistemicState α :=
  conservativeMeet x y

theorem merge_upper_left {α : Type} [DecidableEq α]
    (x y : EpistemicState α) :
    SafetyLE x (merge x y) := by
  exact meet_le_left x y

theorem merge_upper_right {α : Type} [DecidableEq α]
    (x y : EpistemicState α) :
    SafetyLE y (merge x y) := by
  exact meet_le_right x y

theorem merge_least_upper_bound
    {α : Type} [DecidableEq α]
    {x y z : EpistemicState α}
    (hxz : SafetyLE x z)
    (hyz : SafetyLE y z) :
    SafetyLE (merge x y) z := by
  exact le_meet hxz hyz

theorem merge_comm {α : Type} [DecidableEq α]
    (x y : EpistemicState α) :
    merge x y = merge y x := by
  exact AEGIS.NoFreeEpistemicGainV1.meet_comm x y

theorem merge_assoc {α : Type} [DecidableEq α]
    (x y z : EpistemicState α) :
    merge (merge x y) z = merge x (merge y z) := by
  exact AEGIS.NoFreeEpistemicGainV1.meet_assoc x y z

theorem merge_idem {α : Type} [DecidableEq α]
    (x : EpistemicState α) :
    merge x x = x := by
  exact AEGIS.NoFreeEpistemicGainV1.meet_idem x

def SafeLocalUpdate {α : Type} [DecidableEq α]
    (old new : EpistemicState α) : Prop :=
  SafetyLE old new

theorem safe_update_components
    {α : Type} [DecidableEq α]
    {old new : EpistemicState α}
    (h : SafeLocalUpdate old new) :
    new.claims ⊆ old.claims ∧
    new.authority ≤ old.authority ∧
    old.uncertainty ≤ new.uncertainty := by
  exact h

end AEGIS.ConservativeConsensusCRDTV1

#print axioms AEGIS.ConservativeConsensusCRDTV1.merge_least_upper_bound
#print axioms AEGIS.ConservativeConsensusCRDTV1.merge_comm
#print axioms AEGIS.ConservativeConsensusCRDTV1.merge_assoc
#print axioms AEGIS.ConservativeConsensusCRDTV1.merge_idem
#print axioms AEGIS.ConservativeConsensusCRDTV1.safe_update_components
