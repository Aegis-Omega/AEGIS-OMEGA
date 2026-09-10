From Coq Require Import ZArith Ring.

Open Scope Z_scope.

(**
  CSTAR v0.4 formal theorem lane.

  This file proves the low-dimensional group-cohomology identities used by the
  finite skeletal coherent-2-group model, for an arbitrary group carrier and
  trivial action on integer coefficients.  It does NOT identify the historical
  normalized-trace phase proxy with a Postnikov invariant.
*)

Section TrivialIntegerCoefficients.

Context {G : Type}.
Variable e : G.
Variable mul : G -> G -> G.

Hypothesis mul_assoc : forall g h k : G,
  mul (mul g h) k = mul g (mul h k).
Hypothesis mul_left_id : forall g : G, mul e g = g.
Hypothesis mul_right_id : forall g : G, mul g e = g.

Definition C2_Z := G -> G -> Z.
Definition C3_Z := G -> G -> G -> Z.
Definition C4_Z := G -> G -> G -> G -> Z.

Definition delta2_Z (b : C2_Z) : C3_Z :=
  fun g h k =>
    b h k
    - b (mul g h) k
    + b g (mul h k)
    - b g h.

Definition delta3_Z (a : C3_Z) : C4_Z :=
  fun g h k l =>
    a h k l
    - a (mul g h) k l
    + a g (mul h k) l
    - a g h (mul k l)
    + a g h k.

Definition normalized2_Z (b : C2_Z) : Prop :=
  (forall g : G, b e g = 0) /\
  (forall g : G, b g e = 0).

Definition normalized3_Z (a : C3_Z) : Prop :=
  (forall g h : G, a e g h = 0) /\
  (forall g h : G, a g e h = 0) /\
  (forall g h : G, a g h e = 0).

Definition three_cocycle_Z (a : C3_Z) : Prop :=
  forall g h k l : G, delta3_Z a g h k l = 0.

Definition pentagon_holds_Z (a : C3_Z) : Prop :=
  forall g h k l : G, delta3_Z a g h k l = 0.

Definition add3_Z (a c : C3_Z) : C3_Z :=
  fun g h k => a g h k + c g h k.

Definition gauge_transform_Z (a : C3_Z) (b : C2_Z) : C3_Z :=
  add3_Z a (delta2_Z b).

Theorem delta3_delta2_zero_Z_trivial :
  forall (b : C2_Z) (g h k l : G),
    delta3_Z (delta2_Z b) g h k l = 0.
Proof.
  intros b g h k l.
  unfold delta3_Z, delta2_Z.
  repeat rewrite mul_assoc.
  ring.
Qed.

Theorem delta2_preserves_normalization_Z_trivial :
  forall b : C2_Z,
    normalized2_Z b -> normalized3_Z (delta2_Z b).
Proof.
  intros b [Hleft Hright].
  unfold normalized3_Z.
  split.
  - intros g h.
    unfold delta2_Z.
    rewrite (mul_left_id g).
    rewrite (Hleft (mul g h)).
    rewrite (Hleft g).
    ring.
  - split.
    + intros g h.
      unfold delta2_Z.
      rewrite (Hleft h).
      rewrite (mul_right_id g).
      rewrite (mul_left_id h).
      rewrite (Hright g).
      ring.
    + intros g h.
      unfold delta2_Z.
      rewrite (Hright h).
      rewrite (Hright (mul g h)).
      rewrite (mul_right_id h).
      ring.
Qed.

Lemma delta3_additive_Z_trivial :
  forall (a c : C3_Z) (g h k l : G),
    delta3_Z (add3_Z a c) g h k l =
    delta3_Z a g h k l + delta3_Z c g h k l.
Proof.
  intros a c g h k l.
  unfold delta3_Z, add3_Z.
  ring.
Qed.

Theorem gauge_preserves_three_cocycle_Z_trivial :
  forall (a : C3_Z) (b : C2_Z),
    three_cocycle_Z a -> three_cocycle_Z (gauge_transform_Z a b).
Proof.
  intros a b Ha g h k l.
  unfold gauge_transform_Z.
  rewrite delta3_additive_Z_trivial.
  rewrite (Ha g h k l).
  rewrite delta3_delta2_zero_Z_trivial.
  ring.
Qed.

Theorem pentagon_iff_three_cocycle_Z_trivial :
  forall a : C3_Z,
    pentagon_holds_Z a <-> three_cocycle_Z a.
Proof.
  intro a.
  split; intro H; exact H.
Qed.

End TrivialIntegerCoefficients.
