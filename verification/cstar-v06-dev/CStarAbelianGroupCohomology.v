From Coq Require Import Classes.RelationClasses.
From AAC_tactics Require Import AAC.

(**
  CSTAR v0.6 arbitrary-abelian-coefficient theorem candidate.

  Scope:
  - arbitrary group carrier G with associative multiplication and two-sided identity;
  - arbitrary abelian coefficient group A, presented by (zero, add, opp);
  - arbitrary G-action on A preserving the abelian-group operations, identity, and composition;
  - low-dimensional inhomogeneous group-cohomology differentials.

  AAC_tactics is used only as a proof-producing AC normalizer for the declared
  coefficient addition. It does not change theorem assumptions or semantics.
*)

Section ArbitraryAbelianCoefficients.

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
  add x (add y z) = add (add x y) z.
Hypothesis add_comm : forall x y : A, add x y = add y x.
Hypothesis add_zero_l : forall x : A, add zero x = x.
Hypothesis add_opp_l : forall x : A, add (opp x) x = zero.

#[local] Instance aac_add_assoc : Associative eq add := add_assoc.
#[local] Instance aac_add_comm : Commutative eq add := add_comm.
#[local] Instance aac_add_unit : Unit eq add zero.
Proof.
  constructor.
  - exact add_zero_l.
  - intro x. rewrite add_comm. apply add_zero_l.
Defined.

Lemma add_zero_r : forall x : A, add x zero = x.
Proof.
  intro x. rewrite add_comm. apply add_zero_l.
Qed.

Lemma add_opp_r : forall x : A, add x (opp x) = zero.
Proof.
  intro x. rewrite add_comm. apply add_opp_l.
Qed.

Lemma inverse_unique_left :
  forall x y : A, add y x = zero -> y = opp x.
Proof.
  intros x y H.
  rewrite <- (add_zero_r y).
  rewrite <- (add_opp_r x).
  rewrite add_assoc.
  rewrite H.
  apply add_zero_l.
Qed.

Lemma opp_involutive : forall x : A, opp (opp x) = x.
Proof.
  intro x.
  symmetry.
  apply inverse_unique_left.
  apply add_opp_r.
Qed.

Lemma opp_add : forall x y : A, opp (add x y) = add (opp x) (opp y).
Proof.
  intros x y.
  symmetry.
  apply inverse_unique_left.
  repeat aac_rewrite add_opp_l.
  aac_reflexivity.
Qed.

Definition sub (x y : A) : A := add x (opp y).

Variable act : G -> A -> A.
Hypothesis act_zero : forall g : G, act g zero = zero.
Hypothesis act_add : forall (g : G) (x y : A),
  act g (add x y) = add (act g x) (act g y).
Hypothesis act_opp : forall (g : G) (x : A),
  act g (opp x) = opp (act g x).
Hypothesis act_comp : forall (g h : G) (x : A),
  act (mul g h) x = act g (act h x).
Hypothesis act_id : forall x : A, act e x = x.

Definition C2_A_action := G -> G -> A.
Definition C3_A_action := G -> G -> G -> A.
Definition C4_A_action := G -> G -> G -> G -> A.

Definition delta2_A_action (b : C2_A_action) : C3_A_action :=
  fun g h k =>
    add
      (sub (act g (b h k)) (b (mul g h) k))
      (sub (b g (mul h k)) (b g h)).

Definition delta3_A_action (a : C3_A_action) : C4_A_action :=
  fun g h k l =>
    add
      (sub (act g (a h k l)) (a (mul g h) k l))
      (add
         (sub (a g (mul h k) l) (a g h (mul k l)))
         (a g h k)).

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

Theorem delta3_delta2_zero_A_action :
  forall (b : C2_A_action) (g h k l : G),
    delta3_A_action (delta2_A_action b) g h k l = zero.
Proof.
  intros b g h k l.
  unfold delta3_A_action, delta2_A_action, sub.
  repeat rewrite act_add.
  repeat rewrite act_opp.
  repeat rewrite opp_add.
  repeat rewrite opp_involutive.
  repeat rewrite <- act_comp.
  repeat rewrite mul_assoc.
  repeat aac_rewrite add_opp_l.
  aac_reflexivity.
Qed.

Theorem delta2_preserves_normalization_A_action :
  forall b : C2_A_action,
    normalized2_A_action b ->
    normalized3_A_action (delta2_A_action b).
Proof.
  intros b [Hleft Hright].
  unfold normalized3_A_action.
  split.
  - intros g h.
    unfold delta2_A_action, sub.
    rewrite act_id.
    rewrite mul_left_id.
    rewrite Hleft.
    rewrite Hleft.
    repeat aac_rewrite add_opp_l.
    aac_reflexivity.
  - split.
    + intros g h.
      unfold delta2_A_action, sub.
      rewrite Hleft.
      rewrite act_zero.
      rewrite mul_right_id.
      rewrite mul_left_id.
      rewrite Hright.
      repeat aac_rewrite add_opp_l.
      aac_reflexivity.
    + intros g h.
      unfold delta2_A_action, sub.
      rewrite Hright.
      rewrite act_zero.
      rewrite Hright.
      rewrite mul_right_id.
      repeat aac_rewrite add_opp_l.
      aac_reflexivity.
Qed.

Lemma delta3_additive_A_action :
  forall (a c : C3_A_action) (g h k l : G),
    delta3_A_action (add3_A_action a c) g h k l =
    add (delta3_A_action a g h k l) (delta3_A_action c g h k l).
Proof.
  intros a c g h k l.
  unfold delta3_A_action, add3_A_action, sub.
  repeat rewrite act_add.
  repeat rewrite opp_add.
  aac_reflexivity.
Qed.

Theorem gauge_preserves_three_cocycle_A_action :
  forall (a : C3_A_action) (b : C2_A_action),
    three_cocycle_A_action a ->
    three_cocycle_A_action (gauge_transform_A_action a b).
Proof.
  intros a b Ha g h k l.
  unfold gauge_transform_A_action.
  rewrite delta3_additive_A_action.
  rewrite (Ha g h k l).
  rewrite delta3_delta2_zero_A_action.
  aac_reflexivity.
Qed.

Theorem pentagon_iff_three_cocycle_A_action :
  forall a : C3_A_action,
    pentagon_holds_A_action a <-> three_cocycle_A_action a.
Proof.
  intro a.
  split; intro H; exact H.
Qed.

End ArbitraryAbelianCoefficients.
