import Mathlib.Data.Nat.Lattice
import Mathlib.Tactic

namespace AEGIS.ConservativeEpistemicSemilatticeV1

abbrev EpistemicState := Nat × Nat

def merge (x y : EpistemicState) : EpistemicState :=
  (min x.1 y.1, max x.2 y.2)

theorem merge_comm (x y : EpistemicState) :
    merge x y = merge y x := by
  simp [merge, min_comm, max_comm]

theorem merge_assoc (x y z : EpistemicState) :
    merge (merge x y) z = merge x (merge y z) := by
  simp [merge, min_assoc, max_assoc]

theorem merge_idem (x : EpistemicState) :
    merge x x = x := by
  simp [merge]

theorem merge_authority_le_left (x y : EpistemicState) :
    (merge x y).1 ≤ x.1 := by
  simp [merge]

theorem merge_authority_le_right (x y : EpistemicState) :
    (merge x y).1 ≤ y.1 := by
  simp [merge]

theorem left_uncertainty_le_merge (x y : EpistemicState) :
    x.2 ≤ (merge x y).2 := by
  simp [merge]

theorem right_uncertainty_le_merge (x y : EpistemicState) :
    y.2 ≤ (merge x y).2 := by
  simp [merge]

end AEGIS.ConservativeEpistemicSemilatticeV1

#print axioms AEGIS.ConservativeEpistemicSemilatticeV1.merge_assoc
#print axioms AEGIS.ConservativeEpistemicSemilatticeV1.merge_comm
#print axioms AEGIS.ConservativeEpistemicSemilatticeV1.merge_idem
