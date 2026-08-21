(* ============================================================ *)
(* AEGIS Ω — Trace Constraint Refinement                        *)
(* Knowledge Genesis: KG-2026-08-21-004                         *)
(*                                                              *)
(* This theorem connects a semantically sound resolver relation  *)
(* to the abstract ConstraintCarryingTransformation chain.       *)
(* It does not prove Python/Coq compiler correspondence,         *)
(* external-effect atomicity, or distributed linearizability.    *)
(* ============================================================ *)

Require Import Coq.Lists.List.
Require Import ConstraintCarryingTransformation.
Import ListNotations.

Section TraceConstraintRefinement.

Context {Artifact Evidence Restriction Capability : Type}.

Variable provenance : Artifact -> Evidence -> Prop.
Variable restrictions : Artifact -> Restriction -> Prop.
Variable authority : Artifact -> Capability -> Prop.

(* resolved_edge is the abstract semantic relation produced by a resolver.
   The Python implementation is tested separately; no correspondence axiom is
   introduced here. *)
Variable resolved_edge : Artifact -> Artifact -> Prop.

Definition resolver_valid : Prop :=
  forall parent child,
    resolved_edge parent child ->
    constraint_carrying provenance restrictions authority parent child.

Theorem resolver_valid_edge_is_constraint_carrying :
  resolver_valid ->
  forall parent child,
    resolved_edge parent child ->
    constraint_carrying provenance restrictions authority parent child.
Proof.
  intros Hvalid parent child Hedge.
  apply Hvalid. exact Hedge.
Qed.

(* Concrete trace paths are represented independently from the abstract
   transform_chain.  Refinement is therefore a theorem, not a definition by
   alias. *)
Inductive trace_path : Artifact -> list Artifact -> Artifact -> Prop :=
  | trace_path_refl : forall x,
      trace_path x [] x
  | trace_path_step : forall x y tail z,
      resolved_edge x y ->
      trace_path y tail z ->
      trace_path x (y :: tail) z.

Theorem trace_path_refines_transform_chain :
  resolver_valid ->
  forall start mids finish,
    trace_path start mids finish ->
    transform_chain provenance restrictions authority start mids finish.
Proof.
  intros Hvalid start mids finish Hpath.
  induction Hpath.
  - apply chain_refl.
  - apply chain_step with (y := y).
    + apply Hvalid. exact H.
    + exact IHHpath.
Qed.

Theorem trace_path_constraint_closure :
  resolver_valid ->
  forall start mids finish,
    trace_path start mids finish ->
    constraint_carrying provenance restrictions authority start finish.
Proof.
  intros Hvalid start mids finish Hpath.
  apply chain_constraint_closure with (mids := mids).
  apply trace_path_refines_transform_chain; assumption.
Qed.

Corollary resolver_valid_path_preserves_provenance :
  resolver_valid ->
  forall start mids finish e,
    trace_path start mids finish ->
    provenance start e ->
    provenance finish e.
Proof.
  intros Hvalid start mids finish e Hpath He.
  pose proof (trace_path_constraint_closure Hvalid start mids finish Hpath) as Hclosure.
  destruct Hclosure as [HP [HR HA]].
  unfold provenance_preserved in HP.
  apply HP. exact He.
Qed.

Corollary resolver_valid_path_preserves_restrictions :
  resolver_valid ->
  forall start mids finish r,
    trace_path start mids finish ->
    restrictions start r ->
    restrictions finish r.
Proof.
  intros Hvalid start mids finish r Hpath Hr.
  pose proof (trace_path_constraint_closure Hvalid start mids finish Hpath) as Hclosure.
  destruct Hclosure as [HP [HR HA]].
  unfold restrictions_preserved in HR.
  apply HR. exact Hr.
Qed.

Corollary resolver_valid_path_nonamplifies_authority :
  resolver_valid ->
  forall start mids finish c,
    trace_path start mids finish ->
    authority finish c ->
    authority start c.
Proof.
  intros Hvalid start mids finish c Hpath Hc.
  pose proof (trace_path_constraint_closure Hvalid start mids finish Hpath) as Hclosure.
  destruct Hclosure as [HP [HR HA]].
  unfold authority_non_amplifying in HA.
  apply HA. exact Hc.
Qed.

End TraceConstraintRefinement.
