/-
AEGIS Ω — the universal property of the quotient, kernel-checked.  (d)

`FACTORISATION.md` in `aegis-core-loop-v1` states this result and proves it in
prose, and says of itself: *"Ovo je matematički dokaz u tekstu; u ovom paketu
nije kernel-provjeren."*  This module supplies exactly the missing thing and
nothing else: the same statement, checked by the Lean kernel.

THE STATEMENT

For `p : X → S` and `g : X → Y`, a function `f` on the IMAGE of `p` with
`g = f ∘ p` exists and is unique **iff** `g` is constant on the fibres of `p`:

    p x = p x'  →  g x = g x'

The scope restriction is the content, not a technicality.  Uniqueness holds on
`Set.range p` only; off the image `f` is unconstrained, so on all of `S` there
is existence but no uniqueness.  `no_uniqueness_off_the_image` proves that the
restriction cannot be dropped, by exhibiting two total extensions that differ.

WHY THIS THEOREM AND NOT ANOTHER

It is the common shape behind four separate results in this repository's
history, each of which was previously established only by its own witness:

  * `no_abjad_function_gives_vonMangoldt` — `Λ` does not factor through
    `n mod 36`; witness `5` and `41`.
  * the dual-profile impossibility — `e_G` does not factor through `(e_M, u)`;
    witness `[1,60]` and `[2,9]`, both `(20,4)`, needing `96` and `20`.
  * the reconstruction impossibility — the sequence does not factor through
    `(e_M, e_G, u)`; witness `[1,2]` and `[3,1]`, both `(5,5,4)`.
  * the mod-12 router — `4`, `40`, `400` share a residue.

Each is an instance of `not_factors_of_witness` below.  The theorem does NOT
identify those four projections with each other; it only says they fail for one
reason, and supplies the single criterion each of them is a witness against.

WHAT THIS IS NOT

This kernel-checks the factorisation criterion.  It does not check the Rust
engine, the `⋆` monoid implementation, the receipts, or any run of
`aegis-core-loop-v1`.  It asserts nothing about the Voynich manuscript, the
Riemann Hypothesis, or any empirical claim.  `AUTHORITY_EFFECT = NONE`.
-/
import Mathlib.Data.Set.Basic
import Mathlib.Logic.Function.Basic
import Mathlib.Tactic

namespace AEGIS.FactorisationV1

variable {X S Y : Type*}

/-- `f`, defined on the image of `p`, reproduces `g`. -/
def FactorsThrough (p : X → S) (g : X → Y) (f : Set.range p → Y) : Prop :=
  ∀ x : X, f ⟨p x, Set.mem_range_self x⟩ = g x

/-- `g` is constant on each fibre of `p`. -/
def ConstantOnFibres (p : X → S) (g : X → Y) : Prop :=
  ∀ x x' : X, p x = p x' → g x = g x'

/-! ### The theorem -/

/-- **Necessity.**  If `g` factors through `p` at all, it is constant on fibres. -/
theorem constantOnFibres_of_factors {p : X → S} {g : X → Y} {f : Set.range p → Y}
    (hf : FactorsThrough p g f) : ConstantOnFibres p g := by
  intro x x' h
  rw [← hf x, ← hf x']
  exact congrArg f (Subtype.ext h)

/-- **Sufficiency.**  Constancy on fibres builds the factor. -/
theorem exists_factors_of_constantOnFibres {p : X → S} {g : X → Y}
    (h : ConstantOnFibres p g) : ∃ f : Set.range p → Y, FactorsThrough p g f := by
  refine ⟨fun s => g (Classical.choose s.2), fun x => ?_⟩
  exact h _ x (Classical.choose_spec (⟨x, rfl⟩ : ∃ y, p y = p x))

/-- **Uniqueness on the image.**  Two factors agree everywhere on `range p`. -/
theorem factors_unique {p : X → S} {g : X → Y} {f₁ f₂ : Set.range p → Y}
    (h₁ : FactorsThrough p g f₁) (h₂ : FactorsThrough p g f₂) : f₁ = f₂ := by
  funext s
  obtain ⟨x, hx⟩ := s.2
  have hs : s = ⟨p x, Set.mem_range_self x⟩ := Subtype.ext hx.symm
  rw [hs, h₁ x, h₂ x]

/-- **The universal property**, as a single `∃!`. -/
theorem factors_iff_constantOnFibres (p : X → S) (g : X → Y) :
    (∃! f : Set.range p → Y, FactorsThrough p g f) ↔ ConstantOnFibres p g := by
  constructor
  · rintro ⟨f, hf, -⟩
    exact constantOnFibres_of_factors hf
  · intro h
    obtain ⟨f, hf⟩ := exists_factors_of_constantOnFibres h
    exact ⟨f, hf, fun f' hf' => factors_unique hf' hf⟩

/-! ### The contrapositive — the form every witness in this repository takes -/

/-- **A single conflicting pair refutes factorisation.**  This is the shape of
`no_abjad_function_gives_vonMangoldt`, the dual-profile impossibility, the
reconstruction impossibility and the mod-12 router collapse. -/
theorem not_factors_of_witness {p : X → S} {g : X → Y} (x x' : X)
    (hp : p x = p x') (hg : g x ≠ g x') :
    ¬ ∃ f : Set.range p → Y, FactorsThrough p g f := by
  rintro ⟨f, hf⟩
  exact hg (constantOnFibres_of_factors hf x x' hp)

/-! ### The scope restriction is real -/

/-- **The image restriction cannot be dropped.**  Off `range p` a total factor
is unconstrained, so uniqueness fails on `S` whenever something is missed and
`Y` has two distinct values.  Witness: two total functions agreeing on the
image and differing outside it. -/
theorem no_uniqueness_off_the_image
    {p : X → S} {g : X → Y} {s₀ : S} (hs₀ : s₀ ∉ Set.range p)
    {y₁ y₂ : Y} (hy : y₁ ≠ y₂)
    (F : S → Y) (hF : ∀ x, F (p x) = g x) :
    ∃ F₁ F₂ : S → Y,
      (∀ x, F₁ (p x) = g x) ∧ (∀ x, F₂ (p x) = g x) ∧ F₁ ≠ F₂ := by
  classical
  refine ⟨Function.update F s₀ y₁, Function.update F s₀ y₂, ?_, ?_, ?_⟩
  · intro x
    have hne : p x ≠ s₀ := fun h => hs₀ ⟨x, h⟩
    rw [Function.update_of_ne hne, hF]
  · intro x
    have hne : p x ≠ s₀ := fun h => hs₀ ⟨x, h⟩
    rw [Function.update_of_ne hne, hF]
  · intro hcon
    apply hy
    have := congrFun hcon s₀
    rwa [Function.update_self, Function.update_self] at this

/-! ### Controls -/

/-- CONTROL (non-vacuity of the criterion): when `p` is injective the condition
holds for every `g`, so the theorem is not secretly empty. -/
theorem constantOnFibres_of_injective {p : X → S} (hp : Function.Injective p)
    (g : X → Y) : ConstantOnFibres p g :=
  fun _ _ h => congrArg g (hp h)

/-- CONTROL (the criterion really can fail): a concrete refutation instance. -/
theorem parity_not_factors_through_mod_two_of_value :
    ¬ ∃ f : Set.range (fun n : ℕ => n % 2) → ℕ, FactorsThrough (fun n : ℕ => n % 2) id f :=
  not_factors_of_witness 0 2 (by norm_num) (by norm_num)

end AEGIS.FactorisationV1

#print axioms AEGIS.FactorisationV1.constantOnFibres_of_factors
#print axioms AEGIS.FactorisationV1.exists_factors_of_constantOnFibres
#print axioms AEGIS.FactorisationV1.factors_unique
#print axioms AEGIS.FactorisationV1.factors_iff_constantOnFibres
#print axioms AEGIS.FactorisationV1.not_factors_of_witness
#print axioms AEGIS.FactorisationV1.no_uniqueness_off_the_image
#print axioms AEGIS.FactorisationV1.constantOnFibres_of_injective
#print axioms AEGIS.FactorisationV1.parity_not_factors_through_mod_two_of_value
