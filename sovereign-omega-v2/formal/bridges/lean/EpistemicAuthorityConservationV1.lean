import Mathlib.Data.List.Basic
import Mathlib.Data.Nat.Basic

namespace AEGIS.EpistemicAuthorityConservationV1

def stepAuthority (source transform policy : Nat) : Nat :=
  min source (min transform policy)

def chainAuthority (initial : Nat) (gates : List (Nat × Nat)) : Nat :=
  gates.foldl (fun current gate => stepAuthority current gate.1 gate.2) initial

theorem stepAuthority_le_source
    (source transform policy : Nat) :
    stepAuthority source transform policy ≤ source := by
  simp [stepAuthority]

theorem stepAuthority_le_transform
    (source transform policy : Nat) :
    stepAuthority source transform policy ≤ transform := by
  simp [stepAuthority, Nat.min_le_right, Nat.le_trans]

theorem stepAuthority_le_policy
    (source transform policy : Nat) :
    stepAuthority source transform policy ≤ policy := by
  simp [stepAuthority]

theorem chainAuthority_le_initial
    (initial : Nat) (gates : List (Nat × Nat)) :
    chainAuthority initial gates ≤ initial := by
  induction gates generalizing initial with
  | nil =>
      simp [chainAuthority]
  | cons gate rest ih =>
      simp [chainAuthority]
      exact Nat.le_trans (ih (stepAuthority initial gate.1 gate.2))
        (stepAuthority_le_source initial gate.1 gate.2)

theorem zero_is_absorbing
    (gates : List (Nat × Nat)) :
    chainAuthority 0 gates = 0 := by
  induction gates with
  | nil =>
      simp [chainAuthority]
  | cons gate rest ih =>
      simp [chainAuthority, stepAuthority, ih]

end AEGIS.EpistemicAuthorityConservationV1

#print axioms AEGIS.EpistemicAuthorityConservationV1.chainAuthority_le_initial
#print axioms AEGIS.EpistemicAuthorityConservationV1.zero_is_absorbing
