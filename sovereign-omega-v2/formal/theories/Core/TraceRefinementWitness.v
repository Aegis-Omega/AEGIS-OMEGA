(* ============================================================ *)
(* AEGIS Ω — Proof-Producing Trace Refinement Witness            *)
(* Knowledge Genesis: KG-2026-08-21-005                         *)
(*                                                              *)
(* The Python side may emit candidate witness data. This file    *)
(* is the fixed checker. A boolean ACCEPT is proved sound with   *)
(* respect to the existing ConstraintCarryingTransformation     *)
(* predicate. No Python/Coq interpreter-equivalence axiom is     *)
(* introduced.                                                   *)
(* ============================================================ *)

From Coq Require Import List String Bool.
Require Import ConstraintCarryingTransformation.
Import ListNotations.
Open Scope string_scope.

Record ConcreteEdge : Type := {
  edge_parent_id : string;
  edge_child_id : string;
  edge_parent_provenance : list string;
  edge_child_provenance : list string;
  edge_parent_restrictions : list string;
  edge_child_restrictions : list string;
  edge_parent_authority : list string;
  edge_child_authority : list string
}.

Fixpoint memb (x : string) (xs : list string) : bool :=
  match xs with
  | [] => false
  | y :: ys => if String.eqb x y then true else memb x ys
  end.

Fixpoint subsetb (xs ys : list string) : bool :=
  match xs with
  | [] => true
  | x :: tail => memb x ys && subsetb tail ys
  end.

Lemma memb_sound : forall x xs,
  memb x xs = true -> In x xs.
Proof.
  intros x xs.
  induction xs as [| y ys IH].
  - simpl. discriminate.
  - simpl. destruct (String.eqb x y) eqn:Heq.
    + intros _. apply String.eqb_eq in Heq. subst. left. reflexivity.
    + intros H. right. apply IH. exact H.
Qed.

Lemma subsetb_sound : forall xs ys,
  subsetb xs ys = true ->
  forall x, In x xs -> In x ys.
Proof.
  intros xs ys.
  induction xs as [| a tail IH].
  - simpl. intros _ x Hin. contradiction.
  - simpl. intros H x Hin.
    apply andb_true_iff in H as [Ha Htail].
    destruct Hin as [Hx | Hx].
    + subst. apply memb_sound. exact Ha.
    + apply IH.
      * exact Htail.
      * exact Hx.
Qed.

Definition edge_okb (e : ConcreteEdge) : bool :=
  subsetb (edge_parent_provenance e) (edge_child_provenance e) &&
  subsetb (edge_parent_restrictions e) (edge_child_restrictions e) &&
  subsetb (edge_child_authority e) (edge_parent_authority e).

Definition edge_constraint_semantics (e : ConcreteEdge) : Prop :=
  (forall x, In x (edge_parent_provenance e) ->
             In x (edge_child_provenance e)) /\
  (forall x, In x (edge_parent_restrictions e) ->
             In x (edge_child_restrictions e)) /\
  (forall x, In x (edge_child_authority e) ->
             In x (edge_parent_authority e)).

Theorem edge_okb_sound : forall e,
  edge_okb e = true -> edge_constraint_semantics e.
Proof.
  intros e H.
  unfold edge_okb in H.
  repeat rewrite andb_true_iff in H.
  destruct H as [[HP HR] HA].
  unfold edge_constraint_semantics.
  split.
  - intros x Hx. eapply subsetb_sound; eauto.
  - split.
    + intros x Hx. eapply subsetb_sound; eauto.
    + intros x Hx. eapply subsetb_sound; eauto.
Qed.

Inductive Endpoint : Type := Parent | Child.

Definition edge_provenance (e : ConcreteEdge) (a : Endpoint) (x : string) : Prop :=
  match a with
  | Parent => In x (edge_parent_provenance e)
  | Child => In x (edge_child_provenance e)
  end.

Definition edge_restrictions (e : ConcreteEdge) (a : Endpoint) (x : string) : Prop :=
  match a with
  | Parent => In x (edge_parent_restrictions e)
  | Child => In x (edge_child_restrictions e)
  end.

Definition edge_authority (e : ConcreteEdge) (a : Endpoint) (x : string) : Prop :=
  match a with
  | Parent => In x (edge_parent_authority e)
  | Child => In x (edge_child_authority e)
  end.

Definition edge_refines_cct (e : ConcreteEdge) : Prop :=
  @constraint_carrying Endpoint string string string
    (edge_provenance e)
    (edge_restrictions e)
    (edge_authority e)
    Parent Child.

Theorem edge_okb_refines_cct : forall e,
  edge_okb e = true -> edge_refines_cct e.
Proof.
  intros e H.
  pose proof (edge_okb_sound e H) as Hsem.
  destruct Hsem as [HP [HR HA]].
  unfold edge_refines_cct, constraint_carrying,
    provenance_preserved, restrictions_preserved,
    authority_non_amplifying, pred_subset,
    edge_provenance, edge_restrictions, edge_authority.
  simpl.
  repeat split; assumption.
Qed.

Fixpoint all_edges_okb (edges : list ConcreteEdge) : bool :=
  match edges with
  | [] => true
  | e :: tail => edge_okb e && all_edges_okb tail
  end.

Theorem all_edges_refine_cct : forall edges,
  all_edges_okb edges = true -> Forall edge_refines_cct edges.
Proof.
  intros edges.
  induction edges as [| e tail IH].
  - simpl. intros _. constructor.
  - simpl. intros H.
    apply andb_true_iff in H as [He Htail].
    constructor.
    + apply edge_okb_refines_cct. exact He.
    + apply IH. exact Htail.
Qed.

(* Counterexamples ensure the checker is not vacuous. *)
Definition h1 := "1111111111111111111111111111111111111111111111111111111111111111".
Definition h2 := "2222222222222222222222222222222222222222222222222222222222222222".
Definition h3 := "3333333333333333333333333333333333333333333333333333333333333333".

Definition valid_edge : ConcreteEdge :=
  {| edge_parent_id := "p";
     edge_child_id := "c";
     edge_parent_provenance := [h1];
     edge_child_provenance := [h1; h2];
     edge_parent_restrictions := [h2];
     edge_child_restrictions := [h2; h3];
     edge_parent_authority := [h1; h2];
     edge_child_authority := [h1] |}.

Definition provenance_laundered_edge : ConcreteEdge :=
  {| edge_parent_id := "p";
     edge_child_id := "c";
     edge_parent_provenance := [h1];
     edge_child_provenance := [];
     edge_parent_restrictions := [h2];
     edge_child_restrictions := [h2];
     edge_parent_authority := [h1];
     edge_child_authority := [h1] |}.

Definition authority_amplified_edge : ConcreteEdge :=
  {| edge_parent_id := "p";
     edge_child_id := "c";
     edge_parent_provenance := [h1];
     edge_child_provenance := [h1];
     edge_parent_restrictions := [h2];
     edge_child_restrictions := [h2];
     edge_parent_authority := [h1];
     edge_child_authority := [h1; h3] |}.

Example valid_edge_accepts : edge_okb valid_edge = true.
Proof. vm_compute; reflexivity. Qed.

Example provenance_laundering_rejected : edge_okb provenance_laundered_edge = false.
Proof. vm_compute; reflexivity. Qed.

Example authority_amplification_rejected : edge_okb authority_amplified_edge = false.
Proof. vm_compute; reflexivity. Qed.

Print Assumptions edge_okb_refines_cct.
Print Assumptions all_edges_refine_cct.
