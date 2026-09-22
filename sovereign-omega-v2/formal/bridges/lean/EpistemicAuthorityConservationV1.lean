import Mathlib.Data.List.Basic
import Mathlib.Data.Nat.Basic
import Mathlib.Tactic

namespace AEGIS.EpistemicAuthorityConservationV1

def stepAuthority (source transform policy : Nat) : Nat :=
  min source (min transform policy)

def chainAuthority : Nat → List (Nat × Nat) → Nat
  | initial, [] => initial
  | initial, gate :: rest =>
      chainAuthority (stepAuthority initial gate.1 gate.2) rest

theorem stepAuthority_le_source
    (source transform policy : Nat) :
    stepAuthority source transform policy ≤ source := by
  simpa [stepAuthority] using
    (min_le_left source (min transform policy))

theorem stepAuthority_le_transform
    (source transform policy : Nat) :
    stepAuthority source transform policy ≤ transform := by
  exact le_trans
    (by
      simpa [stepAuthority] using
        (min_le_right source (min transform policy)))
    (min_le_left transform policy)

theorem stepAuthority_le_policy
    (source transform policy : Nat) :
    stepAuthority source transform policy ≤ policy := by
  exact le_trans
    (by
      simpa [stepAuthority] using
        (min_le_right source (min transform policy)))
    (min_le_right transform policy)

theorem chainAuthority_le_initial
    (initial : Nat) (gates : List (Nat × Nat)) :
    chainAuthority initial gates ≤ initial := by
  induction gates generalizing initial with
  | nil =>
      simp [chainAuthority]
  | cons gate rest ih =>
      exact le_trans
        (ih (stepAuthority initial gate.1 gate.2))
        (stepAuthority_le_source initial gate.1 gate.2)

theorem zero_is_absorbing
    (gates : List (Nat × Nat)) :
    chainAuthority 0 gates = 0 := by
  induction gates with
  | nil =>
      rfl
  | cons gate rest ih =>
      simpa [chainAuthority, stepAuthority] using ih

end AEGIS.EpistemicAuthorityConservationV1

#print axioms AEGIS.EpistemicAuthorityConservationV1.chainAuthority_le_initial
#print axioms AEGIS.EpistemicAuthorityConservationV1.zero_is_absorbing
