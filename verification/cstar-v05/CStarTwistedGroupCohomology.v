From Coq Require Import Ring.

(**
  CSTAR v0.5 twisted-coefficient formal theorem lane.

  Scope:
  - arbitrary group carrier with associative multiplication and two-sided identity;
  - arbitrary commutative-ring coefficient carrier A;
  - a G-action on A preserving 0, +, -, and composition;
  - low-dimensional inhomogeneous group-cohomology differentials.

  The multiplicative ring structure on A is used only to register the additive
  commutative-group laws with Coq's ring normalization tactic.  The cochain
  definitions below use only the additive operations and the G-action.

  This file does NOT identify the historical normalized-trace phase proxy with
  a Postnikov invariant, and it grants no physical quantum authority.
*)

Section TwistedCommutativeRingCoefficients.

Context {G A : Type}.

Variable e : G.
Variable gmul : G -> G -> G.

Hypothesis gmul_assoc : forall g h k : G,
  gmul (gmul g h) k = gmul g (gmul h k).
Hypothesis gmul_left_id : forall g : G, gmul e g = g.
Hypothesis gmul_right_id : forall g : G, gmul g e = g.

Variable Azero Aone : A.
Variable Aadd Amul Asub : A -> A -> A.
Variable Aopp : A -> A.

Hypothesis A_ring : ring_theory Azero Aone Aadd Amul Asub Aopp eq.
Add Ring ARing : A_ring.

Local Infix "+" := Aadd.
Local Infix "-" := Asub.

Variable act : G -> A -> A.
Hypothesis act_zero : forall g : G, act g Azero = Azero.
Hypothesis act_add : forall (g : G) (x y : A),
  act g (x + y) = act g x + act g y.
Hypothesis act_sub : forall (g : G) (x y : A),
  act g (x - y) = act g x - act g y.
Hypothesis act_comp : forall (g h : G) (x : A),
  act (gmul g h) x = act g (act h x).
Hypothesis act_id : forall x : A, act e x = x.

Definition C2_A := G -> G -> A.
Definition C3_A := G -> G -> G -> A.
Definition C4_A := G -> G -> G -> G -> A.

Definition delta2_A (b : C2_A) : C3_A :=
  fun g h k =>
    act g (b h k)
    - b (gmul g h) k
    + b g (gmul h k)
    - b g h.

Definition delta3_A (a : C3_A) : C4_A :=
  fun g h k l =>
    act g (a h k l)
    - a (gmul g h) k l
    + a g (gmul h k) l
    - a g h (gmul k l)
    + a g h k.

Definition normalized2_A (b : C2_A) : Prop :=
  (forall g : G, b e g = Azero) /\
  (forall g : G, b g e = Azero).

Definition normalized3_A (a : C3_A) : Prop :=
  (forall g h : G, a e g h = Azero) /\
  (forall g h : G, a g e h = Azero) /\
  (forall g h : G, a g h e = Azero).

Definition three_cocycle_A (a : C3_A) : Prop :=
  forall g h k l : G, delta3_A a g h k l = Azero.

Definition pentagon_holds_A (a : C3_A) : Prop :=
  forall g h k l : G, delta3_A a g h k l = Azero.

Definition add3_A (a c : C3_A) : C3_A :=
  fun g h k => a g h k + c g h k.

Definition gauge_transform_A (a : C3_A) (b : C2_A) : C3_A :=
  add3_A a (delta2_A b).

Theorem delta3_delta2_zero_A_action :
  forall (b : C2_A) (g h k l : G),
    delta3_A (delta2_A b) g h k l = Azero.
Proof.
  intros b g h k l.
  unfold delta3_A, delta2_A.
  repeat rewrite act_add.
  repeat rewrite act_sub.
  repeat rewrite <- act_comp.
  repeat rewrite gmul_assoc.
  ring.
Qed.

Theorem delta2_preserves_normalization_A_action :
  forall b : C2_A,
    normalized2_A b -> normalized3_A (delta2_A b).
Proof.
  intros b [Hleft Hright].
  unfold normalized3_A.
  split.
  - intros g h.
    unfold delta2_A.
    rewrite act_id.
    rewrite gmul_left_id.
    rewrite Hleft.
    rewrite Hleft.
    ring.
  - split.
    + intros g h.
      unfold delta2_A.
      rewrite Hleft.
      rewrite act_zero.
      rewrite gmul_right_id.
      rewrite gmul_left_id.
      rewrite Hright.
      ring.
    + intros g h.
      unfold delta2_A.
      rewrite Hright.
      rewrite act_zero.
      rewrite Hright.
      rewrite gmul_right_id.
      ring.
Qed.

Lemma delta3_additive_A_action :
  forall (a c : C3_A) (g h k l : G),
    delta3_A (add3_A a c) g h k l =
    delta3_A a g h k l + delta3_A c g h k l.
Proof.
  intros a c g h k l.
  unfold delta3_A, add3_A.
  repeat rewrite act_add.
  ring.
Qed.

Theorem gauge_preserves_three_cocycle_A_action :
  forall (a : C3_A) (b : C2_A),
    three_cocycle_A a -> three_cocycle_A (gauge_transform_A a b).
Proof.
  intros a b Ha g h k l.
  unfold gauge_transform_A.
  rewrite delta3_additive_A_action.
  rewrite (Ha g h k l).
  rewrite delta3_delta2_zero_A_action.
  ring.
Qed.

Theorem pentagon_iff_three_cocycle_A_action :
  forall a : C3_A,
    pentagon_holds_A a <-> three_cocycle_A a.
Proof.
  intro a.
  split; intro H; exact H.
Qed.

End TwistedCommutativeRingCoefficients.
