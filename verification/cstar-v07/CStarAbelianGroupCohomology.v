From Coq Require Import List.
Import ListNotations.

(**
  CSTAR v0.6 abstract-abelian-coefficient theorem lane.

  Scope:
  - arbitrary group carrier G with associative multiplication and two-sided identity;
  - arbitrary abelian coefficient carrier A presented additively;
  - arbitrary G-action on A preserving zero, addition, inverse, identity and composition;
  - low-dimensional inhomogeneous group-cohomology differentials.

  No ring structure, order, finiteness, decidable equality, or embedding into Z is assumed.
*)

Section AbstractAbelianCoefficients.

Context {G A : Type}.

Variable e : G.
Variable mul : G -> G -> G.

Hypothesis mul_assoc : forall g h k : G,
  mul (mul g h) k = mul g (mul h k).
Hypothesis mul_left_id : forall g : G, mul e g = g.
Hypothesis mul_right_id : forall g : G, mul g e = g.

Variable zero : A.
Variable add : A -> A -> A.
Variable opp : A -> A.

Hypothesis add_assoc : forall x y z : A,
  add (add x y) z = add x (add y z).
Hypothesis add_comm : forall x y : A,
  add x y = add y x.
Hypothesis add_zero_l : forall x : A,
  add zero x = x.
Hypothesis add_opp_l : forall x : A,
  add (opp x) x = zero.

Variable act : G -> A -> A.
Hypothesis act_zero : forall g : G, act g zero = zero.
Hypothesis act_add : forall (g : G) (x y : A),
  act g (add x y) = add (act g x) (act g y).
Hypothesis act_opp : forall (g : G) (x : A),
  act g (opp x) = opp (act g x).
Hypothesis act_comp : forall (g h : G) (x : A),
  act (mul g h) x = act g (act h x).
Hypothesis act_id : forall x : A, act e x = x.

Lemma add_zero_r : forall x : A, add x zero = x.
Proof.
  intro x.
  rewrite add_comm.
  apply add_zero_l.
Qed.

Lemma add_opp_r : forall x : A, add x (opp x) = zero.
Proof.
  intro x.
  rewrite add_comm.
  apply add_opp_l.
Qed.

Lemma swap_head : forall x y z : A,
  add x (add y z) = add y (add x z).
Proof.
  intros x y z.
  transitivity (add (add x y) z).
  - symmetry. apply add_assoc.
  - rewrite (add_comm x y).
    apply add_assoc.
Qed.

Fixpoint add_prefix (xs : list A) (tail : A) : A :=
  match xs with
  | [] => tail
  | x :: rest => add x (add_prefix rest tail)
  end.

Lemma cancel_across_prefix_pos :
  forall (x : A) (xs : list A) (z : A),
    add x (add_prefix xs (add (opp x) z)) = add_prefix xs z.
Proof.
  intros x xs.
  induction xs as [|y ys IH]; intro z; simpl.
  - rewrite <- add_assoc.
    rewrite add_opp_r.
    apply add_zero_l.
  - rewrite (swap_head x y (add_prefix ys (add (opp x) z))).
    f_equal.
    apply IH.
Qed.

Lemma cancel_across_prefix_neg :
  forall (x : A) (xs : list A) (z : A),
    add (opp x) (add_prefix xs (add x z)) = add_prefix xs z.
Proof.
  intros x xs.
  induction xs as [|y ys IH]; intro z; simpl.
  - rewrite <- add_assoc.
    rewrite add_opp_l.
    apply add_zero_l.
  - rewrite (swap_head (opp x) y (add_prefix ys (add x z))).
    f_equal.
    apply IH.
Qed.

Lemma inverse_unique_l : forall x y : A,
  add y x = zero -> y = opp x.
Proof.
  intros x y H.
  transitivity (add y zero).
  - symmetry. apply add_zero_r.
  - transitivity (add y (add x (opp x))).
    + f_equal. symmetry. apply add_opp_r.
    + transitivity (add (add y x) (opp x)).
      * symmetry. apply add_assoc.
      * rewrite H. apply add_zero_l.
Qed.

Lemma opp_involutive : forall x : A, opp (opp x) = x.
Proof.
  intro x.
  symmetry.
  apply inverse_unique_l.
  apply add_opp_r.
Qed.

Lemma opp_zero : opp zero = zero.
Proof.
  symmetry.
  apply inverse_unique_l.
  apply add_zero_l.
Qed.

Lemma opp_add : forall x y : A,
  opp (add x y) = add (opp x) (opp y).
Proof.
  intros x y.
  symmetry.
  apply inverse_unique_l.
  rewrite add_assoc.
  change (add (opp x) (add_prefix [opp y] (add x y)) = zero).
  rewrite cancel_across_prefix_neg.
  simpl.
  apply add_opp_l.
Qed.

Lemma medial : forall a b c d : A,
  add (add a b) (add c d) = add (add a c) (add b d).
Proof.
  intros a b c d.
  rewrite add_assoc.
  rewrite (swap_head b c d).
  rewrite <- add_assoc.
  reflexivity.
Qed.

Definition r5 (a b c d e0 : A) : A :=
  add a (add b (add c (add d e0))).

Lemma r5_pointwise_add : forall a1 a2 a3 a4 a5 c1 c2 c3 c4 c5 : A,
  r5 (add a1 c1) (add a2 c2) (add a3 c3) (add a4 c4) (add a5 c5) =
  add (r5 a1 a2 a3 a4 a5) (r5 c1 c2 c3 c4 c5).
Proof.
  intros a1 a2 a3 a4 a5 c1 c2 c3 c4 c5.
  unfold r5.
  rewrite (medial a4 c4 a5 c5).
  rewrite (medial a3 c3 (add a4 a5) (add c4 c5)).
  rewrite (medial a2 c2 (add a3 (add a4 a5)) (add c3 (add c4 c5))).
  rewrite (medial a1 c1 (add a2 (add a3 (add a4 a5)))
                     (add c2 (add c3 (add c4 c5)))).
  reflexivity.
Qed.

Lemma twenty_term_boundary_cancel :
  forall A0 B0 C0 D0 E0 F0 G0 H0 I0 J0 : A,
    add_prefix
      [A0; opp B0; C0; opp D0; opp A0; E0; opp F0; G0; B0; opp E0;
       H0; opp I0; opp C0; F0; opp H0; J0; D0; opp G0; I0]
      (opp J0) = zero.
Proof.
  intros A0 B0 C0 D0 E0 F0 G0 H0 I0 J0.

  change
    (add A0
      (add_prefix [opp B0; C0; opp D0]
        (add (opp A0)
          (add_prefix [E0; opp F0; G0; B0; opp E0; H0; opp I0; opp C0;
                       F0; opp H0; J0; D0; opp G0; I0]
                      (opp J0)))) = zero).
  rewrite cancel_across_prefix_pos.

  change
    (add (opp B0)
      (add_prefix [C0; opp D0; E0; opp F0; G0]
        (add B0
          (add_prefix [opp E0; H0; opp I0; opp C0; F0; opp H0; J0; D0;
                       opp G0; I0]
                      (opp J0)))) = zero).
  rewrite cancel_across_prefix_neg.

  change
    (add C0
      (add_prefix [opp D0; E0; opp F0; G0; opp E0; H0; opp I0]
        (add (opp C0)
          (add_prefix [F0; opp H0; J0; D0; opp G0; I0]
                      (opp J0)))) = zero).
  rewrite cancel_across_prefix_pos.

  change
    (add (opp D0)
      (add_prefix [E0; opp F0; G0; opp E0; H0; opp I0; F0; opp H0; J0]
        (add D0
          (add_prefix [opp G0; I0] (opp J0)))) = zero).
  rewrite cancel_across_prefix_neg.

  change
    (add E0
      (add_prefix [opp F0; G0]
        (add (opp E0)
          (add_prefix [H0; opp I0; F0; opp H0; J0; opp G0; I0]
                      (opp J0)))) = zero).
  rewrite cancel_across_prefix_pos.

  change
    (add (opp F0)
      (add_prefix [G0; H0; opp I0]
        (add F0
          (add_prefix [opp H0; J0; opp G0; I0] (opp J0)))) = zero).
  rewrite cancel_across_prefix_neg.

  change
    (add G0
      (add_prefix [H0; opp I0; opp H0; J0]
        (add (opp G0)
          (add_prefix [I0] (opp J0)))) = zero).
  rewrite cancel_across_prefix_pos.

  change
    (add H0
      (add_prefix [opp I0]
        (add (opp H0)
          (add_prefix [J0; I0] (opp J0)))) = zero).
  rewrite cancel_across_prefix_pos.

  change
    (add (opp I0)
      (add_prefix [J0]
        (add I0 (opp J0))) = zero).
  rewrite cancel_across_prefix_neg.

  simpl.
  apply add_opp_r.
Qed.

Definition C2_A_action := G -> G -> A.
Definition C3_A_action := G -> G -> G -> A.
Definition C4_A_action := G -> G -> G -> G -> A.

Definition delta2_A_action (b : C2_A_action) : C3_A_action :=
  fun g h k =>
    add (act g (b h k))
      (add (opp (b (mul g h) k))
        (add (b g (mul h k))
             (opp (b g h)))).

Definition delta3_A_action (a : C3_A_action) : C4_A_action :=
  fun g h k l =>
    add (act g (a h k l))
      (add (opp (a (mul g h) k l))
        (add (a g (mul h k) l)
          (add (opp (a g h (mul k l)))
               (a g h k)))).

Definition normalized2_A_action (b : C2_A_action) : Prop :=
  (forall g : G, b e g = zero) /\
  (forall g : G, b g e = zero).

Definition normalized3_A_action (a : C3_A_action) : Prop :=
  (forall g h : G, a e g h = zero) /\
  (forall g h : G, a g e h = zero) /\
  (forall g h : G, a g h e = zero).

Definition three_cocycle_A_action (a : C3_A_action) : Prop :=
  forall g h k l : G, delta3_A_action a g h k l = zero.

Definition pentagon_holds_A_action (a : C3_A_action) : Prop :=
  forall g h k l : G, delta3_A_action a g h k l = zero.

Definition add3_A_action (a c : C3_A_action) : C3_A_action :=
  fun g h k => add (a g h k) (c g h k).

Definition gauge_transform_A_action (a : C3_A_action) (b : C2_A_action) : C3_A_action :=
  add3_A_action a (delta2_A_action b).

Theorem delta3_delta2_zero_abelian_action :
  forall (b : C2_A_action) (g h k l : G),
    delta3_A_action (delta2_A_action b) g h k l = zero.
Proof.
  intros b g h k l.
  unfold delta3_A_action, delta2_A_action.
  repeat (rewrite act_add || rewrite act_opp).
  repeat rewrite opp_add.
  repeat rewrite opp_involutive.
  repeat rewrite <- act_comp.
  repeat rewrite mul_assoc.
  repeat rewrite add_assoc.

  set (A0 := act (mul g h) (b k l)).
  set (B0 := act g (b (mul h k) l)).
  set (C0 := act g (b h (mul k l))).
  set (D0 := act g (b h k)).
  set (E0 := b (mul g (mul h k)) l).
  set (F0 := b (mul g h) (mul k l)).
  set (G0 := b (mul g h) k).
  set (H0 := b g (mul h (mul k l))).
  set (I0 := b g (mul h k)).
  set (J0 := b g h).

  change
    (add_prefix
      [A0; opp B0; C0; opp D0; opp A0; E0; opp F0; G0; B0; opp E0;
       H0; opp I0; opp C0; F0; opp H0; J0; D0; opp G0; I0]
      (opp J0) = zero).
  apply twenty_term_boundary_cancel.
Qed.

Theorem delta2_preserves_normalization_abelian_action :
  forall b : C2_A_action,
    normalized2_A_action b -> normalized3_A_action (delta2_A_action b).
Proof.
  intros b [Hleft Hright].
  unfold normalized3_A_action.
  split.
  - intros g h.
    unfold delta2_A_action.
    rewrite act_id.
    rewrite mul_left_id.
    rewrite (Hleft (mul g h)).
    rewrite (Hleft g).
    rewrite opp_zero.
    rewrite add_zero_l.
    rewrite add_zero_r.
    apply add_opp_r.
  - split.
    + intros g h.
      unfold delta2_A_action.
      rewrite Hleft.
      rewrite act_zero.
      rewrite mul_right_id.
      rewrite mul_left_id.
      rewrite Hright.
      rewrite opp_zero.
      rewrite add_zero_r.
      rewrite add_opp_l.
      apply add_zero_l.
    + intros g h.
      unfold delta2_A_action.
      rewrite Hright.
      rewrite act_zero.
      rewrite Hright.
      rewrite mul_right_id.
      rewrite opp_zero.
      repeat rewrite add_zero_l.
      apply add_opp_r.
Qed.

Lemma delta3_additive_abelian_action :
  forall (a c : C3_A_action) (g h k l : G),
    delta3_A_action (add3_A_action a c) g h k l =
    add (delta3_A_action a g h k l) (delta3_A_action c g h k l).
Proof.
  intros a c g h k l.
  unfold delta3_A_action, add3_A_action.
  rewrite act_add.
  repeat rewrite opp_add.

  set (a1 := act g (a h k l)).
  set (a2 := opp (a (mul g h) k l)).
  set (a3 := a g (mul h k) l).
  set (a4 := opp (a g h (mul k l))).
  set (a5 := a g h k).
  set (c1 := act g (c h k l)).
  set (c2 := opp (c (mul g h) k l)).
  set (c3 := c g (mul h k) l).
  set (c4 := opp (c g h (mul k l))).
  set (c5 := c g h k).

  change
    (r5 (add a1 c1) (add a2 c2) (add a3 c3) (add a4 c4) (add a5 c5) =
     add (r5 a1 a2 a3 a4 a5) (r5 c1 c2 c3 c4 c5)).
  apply r5_pointwise_add.
Qed.

Theorem gauge_preserves_three_cocycle_abelian_action :
  forall (a : C3_A_action) (b : C2_A_action),
    three_cocycle_A_action a ->
    three_cocycle_A_action (gauge_transform_A_action a b).
Proof.
  intros a b Ha g h k l.
  unfold gauge_transform_A_action.
  rewrite delta3_additive_abelian_action.
  rewrite (Ha g h k l).
  rewrite delta3_delta2_zero_abelian_action.
  apply add_zero_l.
Qed.

Theorem pentagon_iff_three_cocycle_abelian_action :
  forall a : C3_A_action,
    pentagon_holds_A_action a <-> three_cocycle_A_action a.
Proof.
  intro a.
  split; intro H; exact H.
Qed.

End AbstractAbelianCoefficients.
