import NoFreeEpistemicGainV1

namespace AEGIS.MultiAgentConservativeConsensusV1

open AEGIS.NoFreeEpistemicGainV1

def consensus {α : Type} [DecidableEq α] :
    EpistemicState α → List (EpistemicState α) → EpistemicState α
  | initial, [] => initial
  | initial, state :: rest =>
      consensus (conservativeMeet initial state) rest

def CommonLowerBound {α : Type} [DecidableEq α]
    (z initial : EpistemicState α)
    (rest : List (EpistemicState α)) : Prop :=
  EpistemicLE z initial ∧
  ∀ state ∈ rest, EpistemicLE z state

theorem consensus_le_initial {α : Type} [DecidableEq α]
    (initial : EpistemicState α)
    (rest : List (EpistemicState α)) :
    EpistemicLE (consensus initial rest) initial := by
  induction rest generalizing initial with
  | nil =>
      exact epistemic_le_refl initial
  | cons state tail ih =>
      exact epistemic_le_trans
        (ih (conservativeMeet initial state))
        (meet_le_left initial state)

theorem consensus_le_member {α : Type} [DecidableEq α]
    (initial : EpistemicState α)
    {state : EpistemicState α}
    {rest : List (EpistemicState α)}
    (hmem : state ∈ rest) :
    EpistemicLE (consensus initial rest) state := by
  induction rest generalizing initial with
  | nil =>
      simp at hmem
  | cons first tail ih =>
      simp only [List.mem_cons] at hmem
      cases hmem with
      | inl hEq =>
          subst state
          exact epistemic_le_trans
            (consensus_le_initial (conservativeMeet initial first) tail)
            (meet_le_right initial first)
      | inr hTail =>
          exact ih (initial := conservativeMeet initial first) hTail

theorem common_lower_bound_le_consensus
    {α : Type} [DecidableEq α]
    {z initial : EpistemicState α}
    {rest : List (EpistemicState α)}
    (hcommon : CommonLowerBound z initial rest) :
    EpistemicLE z (consensus initial rest) := by
  induction rest generalizing initial with
  | nil =>
      exact hcommon.1
  | cons state tail ih =>
      apply ih
      constructor
      · exact le_meet hcommon.1 (hcommon.2 state (by simp))
      · intro other hother
        exact hcommon.2 other (by simp [hother])

theorem consensus_is_common_lower_bound
    {α : Type} [DecidableEq α]
    (initial : EpistemicState α)
    (rest : List (EpistemicState α)) :
    CommonLowerBound (consensus initial rest) initial rest := by
  constructor
  · exact consensus_le_initial initial rest
  · intro state hstate
    exact consensus_le_member initial hstate

theorem consensus_greatest_lower_bound
    {α : Type} [DecidableEq α]
    {z initial : EpistemicState α}
    {rest : List (EpistemicState α)}
    (hcommon : CommonLowerBound z initial rest) :
    EpistemicLE z (consensus initial rest) :=
  common_lower_bound_le_consensus hcommon

end AEGIS.MultiAgentConservativeConsensusV1

#print axioms AEGIS.MultiAgentConservativeConsensusV1.consensus_le_initial
#print axioms AEGIS.MultiAgentConservativeConsensusV1.consensus_le_member
#print axioms AEGIS.MultiAgentConservativeConsensusV1.consensus_greatest_lower_bound
