/-
AEGIS Ω — the abstract-QW obstruction, stated against Mathlib's RiemannHypothesis.

`SemanticBridgeObstruction.v` establishes, in Coq, that an arbitrary abstract
quadratic form is not a semantic identification with the classical Weil
functional: the zero form already satisfies abstract global positivity, so a
bridge premised on abstract positivity alone is satisfied by a trivial model.

The RH formal-conjectures bridge records that result as
`ABSTRACT_QW_REQUIRES_CONCRETE_WEIL_IDENTIFICATION`, and keeps the gate
`aegis_weil_semantics_mapped_to_mathlib` OPEN.  That gate lives in the Lean
lane, against Mathlib's own `RiemannHypothesis`.  This module states the
obstruction there, so the Lean side of the gate is no longer only prose.

WHAT IS PROVED

`abstract_bridge_carries_all_of_rh` is the load-bearing statement: a bridge of
the shape

    (∃ Q, AbstractGlobalPositivity Q) → RiemannHypothesis

yields `RiemannHypothesis` outright, because its hypothesis is a theorem.  So
such a bridge is not a step towards RH; it carries the whole of RH.  Anything
that discharges it has already proved RH by other means.

The statement is formally shallow — once the witness exists it is modus ponens
— and that shallowness is the content.  What does the work is the witness
together with the non-vacuity control below.

NON-VACUITY

`abstract_positivity_is_not_universal` is the control that keeps the predicate
from being trivially true of everything: a form taking a negative value fails
it.  Without that control the result above would be empty.

SCOPE

This is the Lean-side ANALOGUE of the Coq obstruction, not a transport of it.
`GlobalWeilPositivityV1` exists only in Coq; nothing here imports or
reconstructs it.  `AbstractForm` and `AbstractGlobalPositivity` model the
generality a bridge gets when it declines to identify its object with the
classical Weil functional.

WHAT THIS IS NOT

This does not close `aegis_weil_semantics_mapped_to_mathlib`, and does not
touch RH.  Closing that gate requires identifying the concrete Weil functional
with Mathlib's `riemannZeta`, whose mathematical content is the Weil explicit
formula.  Mathlib at revision 0df444a3 has no explicit formula, no
zero-counting function and no Weil theory; the only occurrences of "Weil" in
it are the author name Felix Weilacher and the Henstock-Kurzweil integral.
The AEGIS side is moreover in Coq while the target is in Lean, so the gate
also spans a cross-prover transport.  This module states where the gap is; it
does not narrow it.  AUTHORITY_EFFECT = NONE.
-/
import Mathlib.NumberTheory.LSeries.RiemannZeta
import Mathlib.Tactic

namespace AEGIS.WeilSemanticBridgeObstructionV1

/-- An abstract real-valued form on an arbitrary index type.  This is exactly
the generality a bridge gets when it does not identify its object with the
classical Weil functional. -/
def AbstractForm (ι : Type*) : Type _ := ι → ℝ

/-- Abstract global positivity: nonnegative on every argument. -/
def AbstractGlobalPositivity {ι : Type*} (Q : AbstractForm ι) : Prop :=
  ∀ f : ι, 0 ≤ Q f

/-- The zero form satisfies abstract global positivity — the trivial model. -/
theorem zero_form_is_abstractly_positive (ι : Type*) :
    AbstractGlobalPositivity (fun _ : ι => (0 : ℝ)) :=
  fun _ => le_refl 0

/-- Hence the hypothesis of any abstract bridge is a theorem, not a constraint. -/
theorem exists_abstractly_positive_form (ι : Type*) :
    ∃ Q : AbstractForm ι, AbstractGlobalPositivity Q :=
  ⟨fun _ => 0, zero_form_is_abstractly_positive ι⟩

/-- Non-vacuity control: the predicate is discriminating.  A form taking a
negative value is not abstractly positive, so the statement above is not an
artefact of a predicate that holds of everything. -/
theorem abstract_positivity_is_not_universal :
    ¬ ∀ Q : AbstractForm ℕ, AbstractGlobalPositivity Q := by
  intro h
  have hneg := h (fun _ => (-1 : ℝ)) 0
  norm_num at hneg

/-- THE OBSTRUCTION, against Mathlib's own `RiemannHypothesis`.

A bridge from abstract global positivity to RH discharges RH outright, since
its hypothesis is provable.  Such a bridge therefore carries the entire
difficulty and is not progress towards RH. -/
theorem abstract_bridge_carries_all_of_rh
    (bridge : (∃ Q : AbstractForm ℕ, AbstractGlobalPositivity Q) → RiemannHypothesis) :
    RiemannHypothesis :=
  bridge (exists_abstractly_positive_form ℕ)

end AEGIS.WeilSemanticBridgeObstructionV1
