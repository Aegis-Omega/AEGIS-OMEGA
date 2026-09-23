import Mathlib.Data.Finset.Lattice.Basic
import Mathlib.Data.Nat.Lattice
import Mathlib.Tactic

namespace AEGIS.NoFreeEpistemicGainV1

structure EpistemicState (α : Type) where
  claims : Finset α
  authority : Nat
  uncertainty : Nat

def EpistemicLE {α : Type} [DecidableEq α]
    (x y : EpistemicState α) : Prop :=
  x.claims ⊆ y.claims ∧
  x.authority ≤ y.authority ∧
  y.uncertainty ≤ x.uncertainty

def conservativeMeet {α : Type} [DecidableEq α]
    (x y : EpistemicState α) : EpistemicState α where
  claims := x.claims ∩ y.claims
  authority := min x.authority y.authority
  uncertainty := max x.uncertainty y.uncertainty

theorem epistemic_le_refl {α : Type} [DecidableEq α]
    (x : EpistemicState α) :
    EpistemicLE x x := by
  exact ⟨fun _ h => h, le_rfl, le_rfl⟩

theorem epistemic_le_trans {α : Type} [DecidableEq α]
    {x y z : EpistemicState α}
    (hxy : EpistemicLE x y)
    (hyz : EpistemicLE y z) :
    EpistemicLE x z := by
  constructor
  · intro a ha
    exact hyz.1 (hxy.1 ha)
  constructor
  · exact le_trans hxy.2.1 hyz.2.1
  · exact le_trans hyz.2.2 hxy.2.2

theorem meet_le_left {α : Type} [DecidableEq α]
    (x y : EpistemicState α) :
    EpistemicLE (conservativeMeet x y) x := by
  constructor
  · intro a ha
    exact (Finset.mem_inter.mp ha).1
  constructor
  · exact min_le_left _ _
  · exact le_max_left _ _

theorem meet_le_right {α : Type} [DecidableEq α]
    (x y : EpistemicState α) :
    EpistemicLE (conservativeMeet x y) y := by
  constructor
  · intro a ha
    exact (Finset.mem_inter.mp ha).2
  constructor
  · exact min_le_right _ _
  · exact le_max_right _ _

theorem le_meet {α : Type} [DecidableEq α]
    {z x y : EpistemicState α}
    (hzx : EpistemicLE z x)
    (hzy : EpistemicLE z y) :
    EpistemicLE z (conservativeMeet x y) := by
  constructor
  · intro a ha
    exact Finset.mem_inter.mpr ⟨hzx.1 ha, hzy.1 ha⟩
  constructor
  · exact le_min hzx.2.1 hzy.2.1
  · exact max_le hzx.2.2 hzy.2.2

theorem le_meet_iff {α : Type} [DecidableEq α]
    (z x y : EpistemicState α) :
    EpistemicLE z (conservativeMeet x y) ↔
      EpistemicLE z x ∧ EpistemicLE z y := by
  constructor
  · intro hz
    exact ⟨
      epistemic_le_trans hz (meet_le_left x y),
      epistemic_le_trans hz (meet_le_right x y)
    ⟩
  · rintro ⟨hzx, hzy⟩
    exact le_meet hzx hzy

theorem no_free_epistemic_gain {α : Type} [DecidableEq α]
    {z x y : EpistemicState α}
    (hzx : EpistemicLE z x)
    (hzy : EpistemicLE z y) :
    z.claims ⊆ x.claims ∩ y.claims ∧
    z.authority ≤ min x.authority y.authority ∧
    max x.uncertainty y.uncertainty ≤ z.uncertainty := by
  exact le_meet hzx hzy

theorem meet_comm {α : Type} [DecidableEq α]
    (x y : EpistemicState α) :
    conservativeMeet x y = conservativeMeet y x := by
  ext <;> simp [conservativeMeet, min_comm, max_comm, inter_comm]

theorem meet_assoc {α : Type} [DecidableEq α]
    (x y z : EpistemicState α) :
    conservativeMeet (conservativeMeet x y) z =
      conservativeMeet x (conservativeMeet y z) := by
  ext <;> simp [conservativeMeet, min_assoc, max_assoc, inter_assoc]

theorem meet_idem {α : Type} [DecidableEq α]
    (x : EpistemicState α) :
    conservativeMeet x x = x := by
  ext <;> simp [conservativeMeet]

end AEGIS.NoFreeEpistemicGainV1

#print axioms AEGIS.NoFreeEpistemicGainV1.le_meet_iff
#print axioms AEGIS.NoFreeEpistemicGainV1.no_free_epistemic_gain
#print axioms AEGIS.NoFreeEpistemicGainV1.meet_assoc
