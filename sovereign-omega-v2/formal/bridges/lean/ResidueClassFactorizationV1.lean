/-
AEGIS_MODULO_CONTRACT_V1 — the factorization rule as pure mathematics,
and its correct home in number theory.

The rule: `T` is recoverable from `R x = x mod m` only if `R x = R y → T x = T y`.
As pure mathematics this is the universal property of a quotient: a function
descends along a surjection exactly when it is constant on fibres.

NEGATIVE SIDE (AbjadFactorizationV1): the von Mangoldt weight Λ does NOT descend
along a residue map — 5 and 41 are congruent mod 36 but Λ 5 = log 5 ≠ log 41 = Λ 41.
So the prime side ∑ Λ(n) f(n) of the explicit formula is not a function of residues.

POSITIVE SIDE (below): residue information still enters number theory — but as
characters, not as a factorization of Λ. A Dirichlet character is BY CONSTRUCTION
a function on ZMod q, so it descends. Mathlib's
  DirichletCharacter.sum_char_inv_mul_char_eq :
    ∑ χ : DirichletCharacter R q, χ a⁻¹ * χ b = if a = b then (q.totient : R) else 0
then writes the indicator of a residue class as a combination of such functions.
That is the exact, correct form of the contract's rule in this setting.

It does not shortcut the explicit formula: it replaces one contour problem for ζ
by φ(q) contour problems, one per character, and its conclusion is GRH.
-/
import Mathlib.NumberTheory.DirichletCharacter.Orthogonality

namespace ResidueClassFactorization

/-- **Every Dirichlet character descends along the residue map, by construction:**
`DirichletCharacter R q` is literally a multiplicative character on `ZMod q`.
This is the class of functions the contract's rule admits. -/
theorem character_factors_through_residue (q : ℕ) (χ : DirichletCharacter ℂ q)
    {m n : ℕ} (h : m % q = n % q) : χ (m : ZMod q) = χ (n : ZMod q) := by
  congr 1
  exact (ZMod.natCast_eq_natCast_iff m n q).mpr h

end ResidueClassFactorization

#print axioms ResidueClassFactorization.character_factors_through_residue
