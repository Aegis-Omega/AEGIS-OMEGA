/-
AEGIS — does the abjad encoding carry the prime side of the explicit formula?

The encoder's arithmetic content is exactly `n % 36`:
  digital_root = n % 9,  dodecagon_node = n % 12,  name_node = sum % 12,
and since 9 ∣ 36, 12 ∣ 36 with ℤ/36 → ℤ/9 × ℤ/12 injective, nothing else survives.

AEGIS_MODULO_CONTRACT_V1, semantic factorization rule:
  R(x) = F(x) mod m may be read as a target T only if R x = R y → T x = T y.

This file applies that rule to the objects the explicit formula actually needs.
-/
import Mathlib.NumberTheory.ArithmeticFunction.VonMangoldt

open ArithmeticFunction

namespace AbjadFactorization

/-- The total arithmetic content the abjad encoder retains about `n`. -/
def abjadResidue (n : ℕ) : ℕ := n % 36

/-- A target factors through the encoder exactly when it is constant on residue
fibres — equivalently, when it is periodic with period 36. -/
theorem factors_iff_constant_on_fibres (F : ℕ → ℝ) :
    (∃ T : ℕ → ℝ, ∀ n, F n = T (abjadResidue n)) ↔
      (∀ a b, abjadResidue a = abjadResidue b → F a = F b) := by
  constructor
  · rintro ⟨T, hT⟩ a b hab
    rw [hT a, hT b, hab]
  · intro h
    exact ⟨fun r => F r, fun n => h n (n % 36) (by simp [abjadResidue])⟩

/-- **The von Mangoldt weight does not factor through the abjad encoding.**
`5` and `41` are both prime and share every abjad output — same digital root,
same dodecagon node, same opposite node — yet `Λ 5 = log 5 ≠ log 41 = Λ 41`. -/
theorem vonMangoldt_not_factors :
    ∃ a b : ℕ, abjadResidue a = abjadResidue b ∧ Λ a ≠ Λ b := by
  refine ⟨5, 41, by decide, ?_⟩
  have h5 : Λ 5 = Real.log 5 := by
    have := vonMangoldt_apply_prime (p := 5) (by decide)
    simpa using this
  have h41 : Λ 41 = Real.log 41 := by
    have := vonMangoldt_apply_prime (p := 41) (by decide)
    simpa using this
  rw [h5, h41]
  exact ne_of_lt (Real.log_lt_log (by norm_num) (by norm_num))

/-- **Primality itself does not factor through the abjad encoding.**
`5` and `77` share every abjad output; `5` is prime, `77 = 7 · 11` is not. -/
theorem primality_not_factors :
    ∃ a b : ℕ, abjadResidue a = abjadResidue b ∧ Nat.Prime a ∧ ¬ Nat.Prime b :=
  ⟨5, 77, by decide, by decide, by decide⟩

/-- Consequently no function of the abjad encoding reproduces `Λ`, so the prime
side `∑ Λ(n) f(n)` of the explicit formula cannot be recovered from abjad data. -/
theorem no_abjad_function_gives_vonMangoldt :
    ¬ ∃ T : ℕ → ℝ, ∀ n : ℕ, Λ n = T (abjadResidue n) := by
  rw [factors_iff_constant_on_fibres]
  intro h
  obtain ⟨a, b, hab, hne⟩ := vonMangoldt_not_factors
  exact hne (h a b hab)

end AbjadFactorization

#print axioms AbjadFactorization.factors_iff_constant_on_fibres
#print axioms AbjadFactorization.vonMangoldt_not_factors
#print axioms AbjadFactorization.primality_not_factors
#print axioms AbjadFactorization.no_abjad_function_gives_vonMangoldt
