import NoFreeEpistemicGainV1

namespace AEGIS.ProofCarryingEpistemicPromotionV1

open AEGIS.NoFreeEpistemicGainV1

theorem claim_gain_not_common_lower_bound
    {α : Type} [DecidableEq α]
    {z x y : EpistemicState α}
    {claim : α}
    (hclaim : claim ∈ z.claims)
    (hgain : claim ∉ (conservativeMeet x y).claims) :
    ¬ (EpistemicLE z x ∧ EpistemicLE z y) := by
  intro hcommon
  have hzmeet : EpistemicLE z (conservativeMeet x y) :=
    le_meet hcommon.1 hcommon.2
  exact hgain (hzmeet.1 hclaim)

theorem authority_gain_not_common_lower_bound
    {α : Type} [DecidableEq α]
    {z x y : EpistemicState α}
    (hgain :
      (conservativeMeet x y).authority < z.authority) :
    ¬ (EpistemicLE z x ∧ EpistemicLE z y) := by
  intro hcommon
  have hzmeet : EpistemicLE z (conservativeMeet x y) :=
    le_meet hcommon.1 hcommon.2
  exact (not_lt_of_ge hzmeet.2.1) hgain

theorem uncertainty_reduction_not_common_lower_bound
    {α : Type} [DecidableEq α]
    {z x y : EpistemicState α}
    (hgain :
      z.uncertainty < (conservativeMeet x y).uncertainty) :
    ¬ (EpistemicLE z x ∧ EpistemicLE z y) := by
  intro hcommon
  have hzmeet : EpistemicLE z (conservativeMeet x y) :=
    le_meet hcommon.1 hcommon.2
  exact (not_lt_of_ge hzmeet.2.2) hgain

def HasEpistemicGain {α : Type} [DecidableEq α]
    (z x y : EpistemicState α) : Prop :=
  (∃ claim, claim ∈ z.claims ∧
    claim ∉ (conservativeMeet x y).claims) ∨
  (conservativeMeet x y).authority < z.authority ∨
  z.uncertainty < (conservativeMeet x y).uncertainty

theorem gain_not_common_lower_bound
    {α : Type} [DecidableEq α]
    {z x y : EpistemicState α}
    (hgain : HasEpistemicGain z x y) :
    ¬ (EpistemicLE z x ∧ EpistemicLE z y) := by
  rcases hgain with hclaim | hauthority | huncertainty
  · rcases hclaim with ⟨claim, hz, hnot⟩
    exact claim_gain_not_common_lower_bound hz hnot
  · exact authority_gain_not_common_lower_bound hauthority
  · exact uncertainty_reduction_not_common_lower_bound huncertainty

end AEGIS.ProofCarryingEpistemicPromotionV1

#print axioms AEGIS.ProofCarryingEpistemicPromotionV1.claim_gain_not_common_lower_bound
#print axioms AEGIS.ProofCarryingEpistemicPromotionV1.authority_gain_not_common_lower_bound
#print axioms AEGIS.ProofCarryingEpistemicPromotionV1.uncertainty_reduction_not_common_lower_bound
#print axioms AEGIS.ProofCarryingEpistemicPromotionV1.gain_not_common_lower_bound
