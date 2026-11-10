/-
AEGIS Modulo Contract V1 — the fixed-width ring theorem, kernel-checked.

A memory region of `L` bytes holding fixed-width records of `w` bytes.
  slot representation   s n = w * (n % (L / w))
  byte-ring shortcut    b n = (w * n) % L
The contract README asserts these agree exactly when `w ∣ L`. The shipped
FINITE_REPLAY spot-checks w ∈ [2,32] and q ∈ {1,39}; this proves it for ALL L, w.
-/
import Mathlib.NumberTheory.ArithmeticFunction.VonMangoldt

namespace AegisModulo

/-- Slot representation: index into the record grid, then scale to bytes. -/
def slotOffset (L w n : ℕ) : ℕ := w * (n % (L / w))

/-- Byte-ring shortcut: scale to bytes, then wrap modulo the region length. -/
def byteRingOffset (L w n : ℕ) : ℕ := (w * n) % L

/-- If the record width divides the region, the two representations agree everywhere. -/
theorem byteRing_eq_slot_of_dvd {L w : ℕ} (hdvd : w ∣ L) (n : ℕ) :
    byteRingOffset L w n = slotOffset L w n := by
  obtain ⟨k, rfl⟩ := hdvd
  rcases Nat.eq_zero_or_pos w with hw | hw
  · simp [byteRingOffset, slotOffset, hw]
  · rw [byteRingOffset, slotOffset, Nat.mul_div_cancel_left k hw, Nat.mul_mod_mul_left]

/-- A non-degenerate region forces a positive width (`L / 0 = 0` in `ℕ`). -/
theorem width_pos_of_div_pos {L w : ℕ} (hq : 0 < L / w) : 0 < w := by
  rcases Nat.eq_zero_or_pos w with h | h
  · subst h; simp at hq
  · exact h

/-- **Drift witness.** If the width does not divide the region, the representations
already disagree at the first wrap index `n = L / w`: the slot grid says `0`, the
byte ring says `L - L % w`. -/
theorem byteRing_ne_slot_at_wrap {L w : ℕ} (hq : 0 < L / w) (hnd : ¬ w ∣ L) :
    slotOffset L w (L / w) = 0 ∧
    byteRingOffset L w (L / w) = L - L % w ∧
    byteRingOffset L w (L / w) ≠ slotOffset L w (L / w) := by
  have hw : 0 < w := width_pos_of_div_pos hq
  have hr : 0 < L % w := Nat.pos_of_ne_zero (fun h => hnd (Nat.dvd_of_mod_eq_zero h))
  have hdm : w * (L / w) + L % w = L := Nat.div_add_mod L w
  have hsub : w * (L / w) = L - L % w := Nat.eq_sub_of_add_eq hdm
  have hlt : w * (L / w) < L := by
    have h := Nat.lt_add_of_pos_right (n := w * (L / w)) hr
    rwa [hdm] at h
  have hs : slotOffset L w (L / w) = 0 := by simp [slotOffset]
  have hb : byteRingOffset L w (L / w) = L - L % w := by
    rw [byteRingOffset, Nat.mod_eq_of_lt hlt, hsub]
  refine ⟨hs, hb, ?_⟩
  rw [hs, hb, ← hsub]
  exact (Nat.mul_pos hw hq).ne'

/-- **The fixed-width ring theorem.** For a non-degenerate region, the byte-ring
shortcut is the slot representation if and only if the width divides the region. -/
theorem byteRing_eq_slot_iff_dvd {L w : ℕ} (hq : 0 < L / w) :
    (∀ n : ℕ, byteRingOffset L w n = slotOffset L w n) ↔ w ∣ L := by
  refine ⟨fun h => ?_, fun hdvd n => byteRing_eq_slot_of_dvd hdvd n⟩
  by_contra hnd
  obtain ⟨_, _, hne⟩ := byteRing_ne_slot_at_wrap hq hnd
  exact hne (h _)

/-- **The silent-drop corollary.** At the wrap index the byte ring places a record
that overruns the region. In `core_matrix.M1` the guard `end_pos <= len(state)`
then fails and the record is discarded with no error. -/
theorem byteRing_overruns_region_at_wrap {L w : ℕ} (hq : 0 < L / w) (hnd : ¬ w ∣ L) :
    L < byteRingOffset L w (L / w) + w := by
  obtain ⟨_, hb, _⟩ := byteRing_ne_slot_at_wrap hq hnd
  have hw : 0 < w := width_pos_of_div_pos hq
  have hrw : L % w < w := Nat.mod_lt _ hw
  have hle : L % w ≤ L := Nat.mod_le L w
  rw [hb]
  omega

/-! ### The two live `core_matrix.py` sites, at the default 4 GB profile -/

/-- `M1`: region `2147483648` bytes, record width `40`. Width does not divide region. -/
theorem m1_width_does_not_divide_region : ¬ (40 ∣ 2147483648) := by decide

/-- `M2`: region `1288490188` bytes, slot width `8`. Width does not divide region. -/
theorem m2_width_does_not_divide_region : ¬ (8 ∣ 1288490188) := by decide

/-- M1's concrete drift: the byte ring lands at `2147483640` where the grid expects `0`. -/
theorem m1_drift_at_wrap :
    slotOffset 2147483648 40 (2147483648 / 40) = 0 ∧
    byteRingOffset 2147483648 40 (2147483648 / 40) = 2147483640 :=
  ⟨by decide, by decide⟩

end AegisModulo

#print axioms AegisModulo.byteRing_eq_slot_of_dvd
#print axioms AegisModulo.byteRing_ne_slot_at_wrap
#print axioms AegisModulo.byteRing_eq_slot_iff_dvd
#print axioms AegisModulo.byteRing_overruns_region_at_wrap
#print axioms AegisModulo.m1_width_does_not_divide_region
#print axioms AegisModulo.m2_width_does_not_divide_region
#print axioms AegisModulo.m1_drift_at_wrap
