From Coq Require Import ZArith Ring.

Open Scope Z_scope.

(**
  CSTAR v0.5 twisted-integer formal theorem lane.

  Scope:
  - arbitrary group carrier with associative multiplication and two-sided identity;
  - integer coefficients Z;
  - an arbitrary G-action on Z preserving 0, +, -, identity and composition;
  - low-dimensional inhomogeneous group-cohomology differentials.

  This strictly generalizes the v0.4 trivial-action theorem lane while keeping
  coefficient algebra inside Coq's native integer ring.  Arbitrary abelian
  coefficient groups remain an explicit later theorem obligation.
*)

Section TwistedIntegerCoefficients.

Context {G : Type}.
Variable e : G.
Variable mul : G -> G -> G.

Hypothesis mul_assoc : forall g h k : G,
  mul (mul g h) k = mul g (mul h k).
Hypothesis mul_left_id : forall g : G, mul e g = g.
Hypothesis mul_right_id : forall g : G, mul g e = g.

Variable act : G -> Z -> Z.
Hypothesis act_zero : forall g : G, act g 0 = 0.
Hypothesis act_add : forall (g : G) (x y : Z),
  act g (x + y) = act g x + act g y.
Hypothesis act_sub : forall (g : G) (x y : Z),
  act g (x - y) = act g x - act g y.
Hypothesis act_comp : forall (g h : G) (x : Z),
  act (mul g h) x = act g (act h x).
Hypothesis act_id : forall x : Z, act e x = x.

Definition C2_Z_action := G -> G -> Z.
Definition C3_Z_action := G -> G -> G -> Z.
Definition C4_Z_action := G -> G -> G -> G -> Z.

Definition delta2_Z_action (b : C2_Z_action) : C3_Z_action :=
  fun g h k =>
    act g (b h k)
    - b (mul g h) k
    + b g (mul h k)
    - b g h.

Definition delta3_Z_action (a : C3_Z_action) : C4_Z_action :=
  fun g h k l =>
    act g (a h k l)
    - a (mul g h) k l
    + a g (mul h k) l
    - a g h (mul k l)
    + a g h k.

Definition normalized2_Z_action (b : C2_Z_action) : Prop :=
  (forall g : G, b e g = 0) /\
  (forall g : G, b g e = 0).

Definition normalized3_Z_action (a : C3_Z_action) : Prop :=
  (forall g h : G, a e g h = 0) /\
  (forall g h : G, a g e h = 0) /\
  (forall g h : G, a g h e = 0).

Definition three_cocycle_Z_action (a : C3_Z_action) : Prop :=
  forall g h k l : G, delta3_Z_action a g h k l = 0.

Definition pentagon_holds_Z_action (a : C3_Z_action) : Prop :=
  forall g h k l : G, delta3_Z_action a g h k l = 0.

Definition add3_Z_action (a c : C3_Z_action) : C3_Z_action :=
  fun g h k => a g h k + c g h k.

Definition gauge_transform_Z_action (a : C3_Z_action) (b : C2_Z_action) : C3_Z_action :=
  add3_Z_action a (delta2_Z_action b).

Theorem delta3_delta2_zero_Z_action :
  forall (b : C2_Z_action) (g h k l : G),
    delta3_Z_action (delta2_Z_action b) g h k l = 0.
Proof.
  intros b g h k l.
  unfold delta3_Z_action, delta2_Z_action.
  repeat rewrite act_add.
  repeat rewrite act_sub.
  repeat rewrite <- act_comp.
  repeat rewrite mul_assoc.
  ring.
Qed.

Theorem delta2_preserves_normalization_Z_action :
  forall b : C2_Z_action,
    normalized2_Z_action b -> normalized3_Z_action (delta2_Z_action b).
Proof.
  intros b [Hleft Hright].
  unfold normalized3_Z_action.
  split.
  - intros g h.
    unfold delta2_Z_action.
    rewrite act_id.
    rewrite mul_left_id.
    rewrite Hleft.
    rewrite Hleft.
    ring.
  - split.
    + intros g h.
      unfold delta2_Z_action.
      rewrite Hleft.
      rewrite act_zero.
      rewrite mul_right_id.
      rewrite mul_left_id.
      rewrite Hright.
      ring.
    + intros g h.
      unfold delta2_Z_action.
      rewrite Hright.
      rewrite act_zero.
      rewrite Hright.
      rewrite mul_right_id.
      ring.
Qed.

Lemma delta3_additive_Z_action :
  forall (a c : C3_Z_action) (g h k l : G),
    delta3_Z_action (add3_Z_action a c) g h k l =
    delta3_Z_action a g h k l + delta3_Z_action c g h k l.
Proof.
  intros a c g h k l.
  unfold delta3_Z_action, add3_Z_action.
  repeat rewrite act_add.
  ring.
Qed.

Theorem gauge_preserves_three_cocycle_Z_action :
  forall (a : C3_Z_action) (b : C2_Z_action),
    three_cocycle_Z_action a -> three_cocycle_Z_action (gauge_transform_Z_action a b).
Proof.
  intros a b Ha g h k l.
  unfold gauge_transform_Z_action.
  rewrite delta3_additive_Z_action.
  rewrite (Ha g h k l).
  rewrite delta3_delta2_zero_Z_action.
  ring.
Qed.

Theorem pentagon_iff_three_cocycle_Z_action :
  forall a : C3_Z_action,
    pentagon_holds_Z_action a <-> three_cocycle_Z_action a.
Proof.
  intro a.
  split; intro H; exact H.
Qed.

End TwistedIntegerCoefficients.
