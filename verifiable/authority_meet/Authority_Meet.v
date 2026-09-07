(* ========================================================================= *)
(* AEGIS Ω Module: Authority_Meet.v                                          *)
(* Formal Proof of Non-Escalation Authority Property via Bounded Meet Lattice*)
(* ========================================================================= *)

Require Import Coq.Lists.List.
Import ListNotations.

Section AuthorityPoset.

  (* Definisanje apstraktnog skupa autoriteta sa parcijalnim poretkom i meet operacijom *)
  Variable A : Type.
  Variable le : A -> A -> Prop.
  Variable meet : A -> A -> A.
  Variable top : A.

  Infix "<=" := le.
  Infix "/\" := meet (at level 40, left associativity).

  (* Aksijomi Donje Polumreže (Lower Semi-Lattice axioms) *)
  Hypothesis le_refl : forall x, x <= x.
  Hypothesis le_trans : forall x y z, x <= y -> y <= z -> x <= z.
  Hypothesis le_antisym : forall x y, x <= y -> y <= x -> x = y.

  Hypothesis meet_lb1 : forall x y, x /\ y <= x.
  Hypothesis meet_lb2 : forall x y, x /\ y <= y.
  Hypothesis meet_glb : forall x y z, z <= x -> z <= y -> z <= (x /\ y).

  Hypothesis top_max : forall x, x <= top.

  (* Ekstenzija meet operacije na liste (sekvence obaveznih premisa / ivica) *)
  Fixpoint fold_meet (l : list A) : A :=
    match l with
    | [] => top
    | h :: t => h /\ (fold_meet t)
    end.

  (* LEMA 1: Presjek liste je uvek manji ili jednaka bilo kom pojedinačnom elementu u listi *)
  Lemma fold_meet_in_le : forall (l : list A) (x : A),
    In x l -> fold_meet l <= x.
  Proof.
    induction l as [| h t IH]; intros x Hin.
    - destruct Hin.
    - destruct Hin as [Hhead | Htail].
      + subst h. simpl. apply meet_lb1.
      + simpl. apply le_trans with (y := fold_meet t).
        * apply meet_lb2.
        * apply IH. apply Htail.
  Qed.

  (* Definisanje minimalne karike autoriteta čvora:
     a_s(v) = g_s(v) /\ q_s(v) /\ fold_meet(obavezne_ivice) *)
  Definition compute_node_authority (g_v q_v : A) (edge_authorities : list A) : A :=
    g_v /\ q_v /\ (fold_meet edge_authorities).

  (* TEOREM 1: Bilo koja izvedena vrijednost autoriteta čvora ne može nadmašiti
     autoritet bilo koje obavezne ulazne ivice (Dokaz Neeskalacije) *)
  Theorem authority_non_escalation : forall (g_v q_v e_i : A) (edges : list A),
    In e_i edges ->
    (compute_node_authority g_v q_v edges) <= e_i.
  Proof.
    intros g_v q_v e_i edges Hin.
    unfold compute_node_authority.
    (* Step 1: (g_v /\ q_v /\ fold_meet) <= (fold_meet) *)
    apply le_trans with (y := fold_meet edges).
    - apply le_trans with (y := q_v /\ fold_meet edges).
      + apply meet_lb2.
      + apply meet_lb2.
    - (* Step 2: fold_meet edges <= e_i *)
      apply fold_meet_in_le. apply Hin.
  Qed.

  (* TEOREM 2: Ako je bar jedna obavezna ivica otkazala ili fali (nivo Bot = Fail-Closed),
     rezultujući autoritet čvora se neizbježno spušta na taj nivo *)
  Variable bot : A.
  Hypothesis bot_min : forall x, bot <= x.
  Hypothesis meet_bot_l : forall x, bot /\ x = bot.
  Hypothesis meet_bot_r : forall x, x /\ bot = bot.

  Theorem fail_closed_propagation : forall (g_v q_v : A) (edges : list A),
    In bot edges ->
    compute_node_authority g_v q_v edges <= bot.
  Proof.
    intros g_v q_v edges Hin.
    apply authority_non_escalation with (g_v := g_v) (q_v := q_v).
    apply Hin.
  Qed.

End AuthorityPoset.
