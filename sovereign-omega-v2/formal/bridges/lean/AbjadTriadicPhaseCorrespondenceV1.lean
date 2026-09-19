/-
AEGIS Ω — the abjad-triadic phase correspondence, and its exact limit, V1.

The proposed target was:

    r ∈ {0,3,6,9} ↦ ζ₁₂^r ∈ {1, i, -1, -i}

followed by "a proof that the four-phase criterion is identical to the
Abjad-triadic criterion".  Both are proved here.  This module also proves the
two facts that bound what they are worth, because the correspondence alone is
easy to over-read.

WHAT IS PROVED

1. `abjad_triadic_phase_correspondence` — the correspondence itself.  It is an
   isomorphism of ℤ/4 onto μ₄, restricted from the unique order-4 subgroup
   {0,3,6,9} of ℤ/12.

2. `abjad_indexed_bound` — the "identity of criteria".  Note HOW it is proved:
   it is derived from the four-phase lemma in three lines by rewriting through
   (1).  That derivation is the point.  The abjad-indexed hypothesis is not a
   new hypothesis; it is the same hypothesis under a different name, and it
   yields exactly the same conclusion and nothing more.

3. `triadic_residue_meets_primes_only_at_three` — the limit.  Every element of
   {0,3,6,9} ⊂ ℤ/12 is divisible by 3, so the triadic residue class set meets
   the primes in the single point p = 3.  The abjad-triadic node set therefore
   cannot index the prime side at all.  This is stronger than saying it loses
   information: it barely touches the primes.

WHAT IS NOT PROVED, AND CANNOT BE REACHED FROM HERE

`WeilFourPhaseV1` is a CLOSED four-element definition in
`WeilTwoPointPositivityV1.lean` (lane #491, dcfa2a51), and the four-phase bound
there is already proved unconditionally.  The four phases enter as four
instantiations of a hypothesis followed by `linarith`.  There was no open
enumeration gap for this correspondence to close.

The open obligation on that lane is `universal_arithmetic_nonpositivity`:

    ∀ g, WeilMomentConditionsV1 g →
      (WeilExplicitRightSideV1 (WeilAutocorrelationV1 g)).re ≤ 0

Weil's criterion is an *equivalence*, so that inequality over a class sufficient
for equivalence IS the Riemann Hypothesis.  Nothing in this module moves it.
This module proves no part of it, asserts no sign, and proves nothing about RH.
-/
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic
import Mathlib.Analysis.Complex.Trigonometric
import Mathlib.Tactic

open Complex

namespace AEGIS.AbjadTriadicPhaseCorrespondenceV1

/-- Primitive 12th root of unity, written concretely. -/
noncomputable def zeta12 : ℂ := Complex.exp (2 * (Real.pi : ℂ) * Complex.I / 12)

/-! ### The four triadic powers -/

theorem zeta12_pow_zero : zeta12 ^ 0 = 1 := pow_zero _

theorem zeta12_pow_three : zeta12 ^ 3 = Complex.I := by
  have h : ((3 : ℕ) : ℂ) * (2 * (Real.pi : ℂ) * Complex.I / 12)
      = ((Real.pi : ℂ) / 2) * Complex.I := by
    push_cast; ring
  rw [zeta12, ← Complex.exp_nat_mul, h, Complex.exp_mul_I,
    Complex.cos_pi_div_two, Complex.sin_pi_div_two]
  ring

theorem zeta12_pow_six : zeta12 ^ 6 = -1 := by
  have h : zeta12 ^ 6 = (zeta12 ^ 3) ^ 2 := by ring
  rw [h, zeta12_pow_three, Complex.I_sq]

theorem zeta12_pow_nine : zeta12 ^ 9 = -Complex.I := by
  have h : zeta12 ^ 9 = (zeta12 ^ 3) ^ 2 * zeta12 ^ 3 := by ring
  rw [h, zeta12_pow_three, Complex.I_sq]
  ring

/-! ### The four-phase predicate, restated verbatim from lane #491

`WeilTwoPointPositivityV1.lean` @ `dcfa2a51`.  Restated rather than imported
because that module is not in this compilation unit; the definitions are
byte-identical to the source. -/

def WeilFourPhaseV1 (c : ℂ) : Prop :=
  c = 1 ∨ c = -1 ∨ c = I ∨ c = -I

def WeilTwoPointValueV1 (a : ℝ) (z c : ℂ) : ℝ :=
  a * (1 + normSq c) + 2 * (c * z).re

/-- The four-phase bound, restated from lane #491.  Proved there and here
unconditionally: the four phases are four instantiations of `h`, then linear
arithmetic.  There is no search and no enumeration gap. -/
theorem weil_four_phase_bound (a : ℝ) (z : ℂ)
    (h : ∀ c : ℂ, WeilFourPhaseV1 c → 0 ≤ WeilTwoPointValueV1 a z c) :
    |z.re| ≤ a ∧ |z.im| ≤ a := by
  have hp := h 1 (Or.inl rfl)
  have hn := h (-1) (Or.inr (Or.inl rfl))
  have hi := h I (Or.inr (Or.inr (Or.inl rfl)))
  have hni := h (-I) (Or.inr (Or.inr (Or.inr rfl)))
  simp [WeilTwoPointValueV1, Complex.normSq_apply, Complex.mul_re] at hp hn hi hni
  constructor
  · exact abs_le.mpr ⟨by linarith, by linarith⟩
  · exact abs_le.mpr ⟨by linarith, by linarith⟩

/-! ### 1. The correspondence -/

/-- **The proposed target.**  `r ∈ {0,3,6,9} ↦ ζ₁₂^r` enumerates exactly the
four phases.  This is the isomorphism ℤ/4 ≅ μ₄ restricted from ℤ/12. -/
theorem abjad_triadic_phase_correspondence (c : ℂ) :
    WeilFourPhaseV1 c ↔ ∃ r ∈ ({0, 3, 6, 9} : Finset ℕ), c = zeta12 ^ r := by
  constructor
  · rintro (rfl | rfl | rfl | rfl)
    · exact ⟨0, by decide, zeta12_pow_zero.symm⟩
    · exact ⟨6, by decide, zeta12_pow_six.symm⟩
    · exact ⟨3, by decide, zeta12_pow_three.symm⟩
    · exact ⟨9, by decide, zeta12_pow_nine.symm⟩
  · rintro ⟨r, hr, rfl⟩
    fin_cases hr
    · exact Or.inl zeta12_pow_zero
    · exact Or.inr (Or.inr (Or.inl zeta12_pow_three))
    · exact Or.inr (Or.inl zeta12_pow_six)
    · exact Or.inr (Or.inr (Or.inr zeta12_pow_nine))

/-- CONTROL (non-vacuity): the four phases are pairwise distinct, so the
correspondence is a genuine bijection onto a four-element set and does not
collapse. -/
theorem zeta12_phases_distinct :
    zeta12 ^ 0 ≠ zeta12 ^ 3 ∧ zeta12 ^ 0 ≠ zeta12 ^ 6 ∧ zeta12 ^ 0 ≠ zeta12 ^ 9 ∧
      zeta12 ^ 3 ≠ zeta12 ^ 6 ∧ zeta12 ^ 3 ≠ zeta12 ^ 9 ∧ zeta12 ^ 6 ≠ zeta12 ^ 9 := by
  rw [zeta12_pow_zero, zeta12_pow_three, zeta12_pow_six, zeta12_pow_nine]
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_⟩ <;>
    norm_num [Complex.ext_iff]

/-! ### 2. The "identity of criteria" — and why it adds nothing -/

/-- **The second half of the proposed target.**  The abjad-indexed criterion
gives the same bound as the four-phase criterion.

The proof is the content: it rewrites the hypothesis through the
correspondence and calls the existing lemma.  No new analytic input is
consumed and no stronger conclusion is produced.  The abjad indexing is a
change of name for the index set, not a change of theorem. -/
theorem abjad_indexed_bound (a : ℝ) (z : ℂ)
    (h : ∀ r ∈ ({0, 3, 6, 9} : Finset ℕ), 0 ≤ WeilTwoPointValueV1 a z (zeta12 ^ r)) :
    |z.re| ≤ a ∧ |z.im| ≤ a := by
  refine weil_four_phase_bound a z ?_
  intro c hc
  obtain ⟨r, hr, rfl⟩ := (abjad_triadic_phase_correspondence c).mp hc
  exact h r hr

/-- And the converse direction, for completeness: the four-phase hypothesis is
recovered from the abjad-indexed one.  The two hypotheses are interderivable,
which is exactly what "the criteria are identical" means — and exactly why
proving it moves no open obligation. -/
theorem four_phase_hypothesis_iff_abjad_indexed (a : ℝ) (z : ℂ) :
    (∀ c : ℂ, WeilFourPhaseV1 c → 0 ≤ WeilTwoPointValueV1 a z c) ↔
      (∀ r ∈ ({0, 3, 6, 9} : Finset ℕ), 0 ≤ WeilTwoPointValueV1 a z (zeta12 ^ r)) := by
  constructor
  · intro h r hr
    exact h _ ((abjad_triadic_phase_correspondence _).mpr ⟨r, hr, rfl⟩)
  · intro h c hc
    obtain ⟨r, hr, rfl⟩ := (abjad_triadic_phase_correspondence c).mp hc
    exact h r hr

/-! ### 3. The limit: the triadic node set barely meets the primes -/

/-- **NO-GO.**  Every element of `{0,3,6,9} ⊂ ℤ/12` is divisible by 3, so a
prime whose index lies in a triadic residue class must be `3` itself.  The
abjad-triadic node set therefore cannot index the prime side: it meets the
primes in exactly one point. -/
theorem triadic_residue_meets_primes_only_at_three {p : ℕ} (hp : p.Prime)
    (h : p % 12 = 0 ∨ p % 12 = 3 ∨ p % 12 = 6 ∨ p % 12 = 9) : p = 3 := by
  have hmm : p % 3 = p % 12 % 3 := (Nat.mod_mod_of_dvd p (by norm_num)).symm
  have h3 : p % 3 = 0 := by rcases h with h | h | h | h <;> rw [hmm, h]
  have hdvd : (3 : ℕ) ∣ p := Nat.dvd_of_mod_eq_zero h3
  exact ((Nat.prime_dvd_prime_iff_eq Nat.prime_three hp).mp hdvd).symm

/-- CONTROL: the no-go is not vacuous — `3` really does sit in a triadic class,
so the intersection is exactly `{3}` and not empty. -/
theorem three_is_triadic : (3 : ℕ) % 12 = 3 := by norm_num

end AEGIS.AbjadTriadicPhaseCorrespondenceV1

#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.zeta12_pow_three
#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.zeta12_pow_six
#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.zeta12_pow_nine
#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.abjad_triadic_phase_correspondence
#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.zeta12_phases_distinct
#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.weil_four_phase_bound
#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.abjad_indexed_bound
#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.four_phase_hypothesis_iff_abjad_indexed
#print axioms AEGIS.AbjadTriadicPhaseCorrespondenceV1.triadic_residue_meets_primes_only_at_three
