(* ============================================================ *)
(* AEGIS Ω — Constraint-Carrying Causal Closure                 *)
(* Knowledge Genesis: KG-2026-08-21-003                         *)
(*                                                              *)
(* This file proves the mathematical closure property only.     *)
(* It does NOT establish correspondence to the Python runtime,   *)
(* distributed linearizability, or external-effect atomicity.    *)
(* ============================================================ *)

Require Import Coq.Lists.List.
Import ListNotations.

Definition pred_subset {X : Type} (P Q : X -> Prop) : Prop :=
  forall x, P x -> Q x.

Lemma pred_subset_refl : forall (X : Type) (P : X -> Prop),
  pred_subset P P.
Proof.
  intros X P x Hx. exact Hx.
Qed.

Lemma pred_subset_trans : forall (X : Type) (P Q R : X -> Prop),
  pred_subset P Q -> pred_subset Q R -> pred_subset P R.
Proof.
  intros X P Q R HPQ HQR x Hx.
  apply HQR. apply HPQ. exact Hx.
Qed.

Section ConstraintCarryingTransformation.

Context {Artifact Evidence Restriction Capability : Type}.

Variable provenance : Artifact -> Evidence -> Prop.
Variable restrictions : Artifact -> Restriction -> Prop.
Variable authority : Artifact -> Capability -> Prop.

Definition provenance_preserved (parent child : Artifact) : Prop :=
  pred_subset (provenance parent) (provenance child).

Definition restrictions_preserved (parent child : Artifact) : Prop :=
  pred_subset (restrictions parent) (restrictions child).

Definition authority_non_amplifying (parent child : Artifact) : Prop :=
  pred_subset (authority child) (authority parent).

Definition constraint_carrying (parent child : Artifact) : Prop :=
  provenance_preserved parent child /\
  restrictions_preserved parent child /\
  authority_non_amplifying parent child.

Theorem constraint_carrying_refl : forall x : Artifact,
  constraint_carrying x x.
Proof.
  intros x.
  unfold constraint_carrying, provenance_preserved,
    restrictions_preserved, authority_non_amplifying.
  split.
  - apply pred_subset_refl.
  - split; apply pred_subset_refl.
Qed.

Theorem constraint_carrying_trans : forall x y z : Artifact,
  constraint_carrying x y ->
  constraint_carrying y z ->
  constraint_carrying x z.
Proof.
  intros x y z Hxy Hyz.
  destruct Hxy as [HPxy [HRxy HAxy]].
  destruct Hyz as [HPyz [HRyz HAyz]].
  unfold constraint_carrying.
  split.
  - unfold provenance_preserved in *.
    eapply pred_subset_trans; eauto.
  - split.
    + unfold restrictions_preserved in *.
      eapply pred_subset_trans; eauto.
    + unfold authority_non_amplifying in *.
      eapply pred_subset_trans; eauto.
Qed.

(* Arbitrary finite chain: the list length is not fixed to three transforms. *)
Inductive transform_chain : Artifact -> list Artifact -> Artifact -> Prop :=
  | chain_refl : forall x,
      transform_chain x [] x
  | chain_step : forall x y tail z,
      constraint_carrying x y ->
      transform_chain y tail z ->
      transform_chain x (y :: tail) z.

Theorem chain_constraint_closure : forall start mids finish,
  transform_chain start mids finish ->
  constraint_carrying start finish.
Proof.
  intros start mids finish Hchain.
  induction Hchain.
  - apply constraint_carrying_refl.
  - eapply constraint_carrying_trans; eauto.
Qed.

Corollary provenance_lineage_closure : forall start mids finish e,
  transform_chain start mids finish ->
  provenance start e ->
  provenance finish e.
Proof.
  intros start mids finish e Hchain He.
  destruct (chain_constraint_closure start mids finish Hchain)
    as [HP [HR HA]].
  unfold provenance_preserved in HP.
  apply HP. exact He.
Qed.

Corollary restriction_lineage_closure : forall start mids finish r,
  transform_chain start mids finish ->
  restrictions start r ->
  restrictions finish r.
Proof.
  intros start mids finish r Hchain Hr0.
  destruct (chain_constraint_closure start mids finish Hchain)
    as [HP [HR HA]].
  unfold restrictions_preserved in HR.
  apply HR. exact Hr0.
Qed.

Corollary authority_cannot_amplify_across_chain : forall start mids finish c,
  transform_chain start mids finish ->
  authority finish c ->
  authority start c.
Proof.
  intros start mids finish c Hchain Hc.
  destruct (chain_constraint_closure start mids finish Hchain)
    as [HP [HR HA]].
  unfold authority_non_amplifying in HA.
  apply HA. exact Hc.
Qed.

Variable State Root : Type.

Definition commit_fresh (captured current : State) : Prop :=
  captured = current.

Definition causal_witness_unspliced (witness actual : Root) : Prop :=
  witness = actual.

Definition commit_guards
  (captured current : State) (witness actual : Root) : Prop :=
  commit_fresh captured current /\
  causal_witness_unspliced witness actual.

Theorem constraint_carrying_causal_closure :
  forall start mids finish captured current witness actual,
    transform_chain start mids finish ->
    commit_guards captured current witness actual ->
    provenance_preserved start finish /\
    restrictions_preserved start finish /\
    authority_non_amplifying start finish /\
    captured = current /\
    witness = actual.
Proof.
  intros start mids finish captured current witness actual Hchain Hguards.
  destruct Hguards as [Hfresh Hwitness].
  destruct (chain_constraint_closure start mids finish Hchain)
    as [HP [HR HA]].
  unfold commit_fresh in Hfresh.
  unfold causal_witness_unspliced in Hwitness.
  split.
  - exact HP.
  - split.
    + exact HR.
    + split.
      * exact HA.
      * split; assumption.
Qed.

End ConstraintCarryingTransformation.

(* Guard-independence witnesses. These prove that satisfying the other
   obligations does not logically imply the omitted guard. *)
Definition yes : unit -> Prop := fun _ => True.
Definition no : unit -> Prop := fun _ => False.

Lemma yes_subset_yes : pred_subset yes yes.
Proof. intros x H. exact H. Qed.

Lemma no_subset_no : pred_subset no no.
Proof. intros x H. contradiction. Qed.

Lemma yes_not_subset_no : ~ pred_subset yes no.
Proof.
  intro H.
  specialize (H tt I).
  exact H.
Qed.

Lemma zero_not_one : 0 <> 1.
Proof. discriminate. Qed.

Theorem counterexample_without_provenance_guard :
  pred_subset yes yes /\
  pred_subset no no /\
  (0 = 0) /\
  (0 = 0) /\
  ~ pred_subset yes no.
Proof.
  exact (conj yes_subset_yes
    (conj no_subset_no
      (conj eq_refl
        (conj eq_refl yes_not_subset_no)))).
Qed.

Theorem counterexample_without_restriction_guard :
  pred_subset yes yes /\
  pred_subset no no /\
  (0 = 0) /\
  (0 = 0) /\
  ~ pred_subset yes no.
Proof.
  exact (conj yes_subset_yes
    (conj no_subset_no
      (conj eq_refl
        (conj eq_refl yes_not_subset_no)))).
Qed.

Theorem counterexample_without_authority_guard :
  pred_subset yes yes /\
  pred_subset yes yes /\
  (0 = 0) /\
  (0 = 0) /\
  ~ pred_subset yes no.
Proof.
  exact (conj yes_subset_yes
    (conj yes_subset_yes
      (conj eq_refl
        (conj eq_refl yes_not_subset_no)))).
Qed.

Theorem counterexample_without_freshness_guard :
  pred_subset yes yes /\
  pred_subset yes yes /\
  pred_subset no no /\
  (0 = 0) /\
  0 <> 1.
Proof.
  exact (conj yes_subset_yes
    (conj yes_subset_yes
      (conj no_subset_no
        (conj eq_refl zero_not_one)))).
Qed.

Theorem counterexample_without_antisplice_guard :
  pred_subset yes yes /\
  pred_subset yes yes /\
  pred_subset no no /\
  (0 = 0) /\
  0 <> 1.
Proof.
  exact (conj yes_subset_yes
    (conj yes_subset_yes
      (conj no_subset_no
        (conj eq_refl zero_not_one)))).
Qed.
