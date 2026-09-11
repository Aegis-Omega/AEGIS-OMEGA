From Coq Require Import Morphisms RelationClasses.
From AAC_tactics Require Import AAC.
From mathcomp Require Import all_ssreflect all_algebra.

Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

Import GRing.Theory.
Local Open Scope ring_scope.

(**
  CSTAR v0.6 arbitrary-abelian-coefficient theorem candidate.

  Coefficients are an arbitrary MathComp zmodType: an additive abelian group.
  The G-action is represented by additive endomorphisms of that zmodType.
  No multiplication, ring unit, or scalar-field structure is assumed on A.
*)

Section TwistedZmodCoefficients.

Context {G : Type}.
Variable e : G.
Variable mul : G -> G -> G.
Hypothesis mul_assoc : forall g h k : G,
  mul (mul g h) k = mul g (mul h k).
Hypothesis mul_left_id : forall g : G, mul e g = g.
Hypothesis mul_right_id : forall g : G, mul g e = g.

Variable A : zmodType.
Variable act : G -> {additive A -> A}.
Hypothesis act_comp : forall (g h : G) (x : A),
  act (mul g h) x = act g (act h x).
Hypothesis act_id : forall x : A, act e x = x.

Definition C2_zmod := G -> G -> A.
Definition C3_zmod := G -> G -> G -> A.
Definition C4_zmod := G -> G -> G -> G -> A.

Definition delta2_zmod (b : C2_zmod) : C3_zmod :=
  fun g h k =>
    act g (b h k)
    - b (mul g h) k
    + b g (mul h k)
    - b g h.

Definition delta3_zmod (a : C3_zmod) : C4_zmod :=
  fun g h k l =>
    act g (a h k l)
    - a (mul g h) k l
    + a g (mul h k) l
    - a g h (mul k l)
    + a g h k.

Definition normalized2_zmod (b : C2_zmod) : Prop :=
  (forall g : G, b e g = 0) /\
  (forall g : G, b g e = 0).

Definition normalized3_zmod (a : C3_zmod) : Prop :=
  (forall g h : G, a e g h = 0) /\
  (forall g h : G, a g e h = 0) /\
  (forall g h : G, a g h e = 0).

Definition three_cocycle_zmod (a : C3_zmod) : Prop :=
  forall g h k l : G, delta3_zmod a g h k l = 0.

Definition pentagon_holds_zmod (a : C3_zmod) : Prop :=
  forall g h k l : G, delta3_zmod a g h k l = 0.

Definition add3_zmod (a c : C3_zmod) : C3_zmod :=
  fun g h k => a g h k + c g h k.

Definition gauge_transform_zmod (a : C3_zmod) (b : C2_zmod) : C3_zmod :=
  add3_zmod a (delta2_zmod b).

(* AAC is used only to reorder the additive abelian-group expression. *)
#[local] Instance zmod_add_proper : Proper (eq ==> eq ==> eq) (+%R : A -> A -> A).
Proof. by move=> x x' -> y y' ->. Qed.

#[local] Instance zmod_add_assoc : Associative eq (+%R : A -> A -> A).
Proof. exact: addrA. Qed.

#[local] Instance zmod_add_comm : Commutative eq (+%R : A -> A -> A).
Proof. exact: addrC. Qed.

Lemma cancel_twisted_boundary_zmod
    (x1 x2 x3 x4 x5 x6 x7 x8 x9 x10 : A) :
  x1 - x2 + x3 - x4
  - x1 + x5 - x6 + x7
  + x2 - x5 + x9 - x8
  - x3 + x6 - x9 + x10
  + x4 - x7 + x8 - x10 = 0.
Proof.
  have Hreorder :
    x1 - x2 + x3 - x4
    - x1 + x5 - x6 + x7
    + x2 - x5 + x9 - x8
    - x3 + x6 - x9 + x10
    + x4 - x7 + x8 - x10 =
    (x1 - x1) + (x2 - x2) + (x3 - x3) + (x4 - x4) +
    (x5 - x5) + (x6 - x6) + (x7 - x7) + (x8 - x8) +
    (x9 - x9) + (x10 - x10).
  - aac_reflexivity.
  - rewrite Hreorder.
    by rewrite !subrr !add0r.
Qed.

Theorem delta3_delta2_zero_zmod_action :
  forall (b : C2_zmod) (g h k l : G),
    delta3_zmod (delta2_zmod b) g h k l = 0.
Proof.
  move=> b g h k l.
  rewrite /delta3_zmod /delta2_zmod !raddfB !raddfD !raddfN.
  rewrite -!act_comp !mul_assoc !opprK.
  transitivity (
    act (mul g h) (b k l)
    - act g (b (mul h k) l)
    + act g (b h (mul k l))
    - act g (b h k)
    - act (mul g h) (b k l)
    + b (mul g (mul h k)) l
    - b (mul g h) (mul k l)
    + b (mul g h) k
    + act g (b (mul h k) l)
    - b (mul g (mul h k)) l
    + b g (mul h (mul k l))
    - b g (mul h k)
    - act g (b h (mul k l))
    + b (mul g h) (mul k l)
    - b g (mul h (mul k l))
    + b g h
    + act g (b h k)
    - b (mul g h) k
    + b g (mul h k)
    - b g h
  ).
  - aac_reflexivity.
  - exact: cancel_twisted_boundary_zmod.
Qed.

Theorem delta2_preserves_normalization_zmod_action :
  forall b : C2_zmod,
    normalized2_zmod b -> normalized3_zmod (delta2_zmod b).
Proof.
  move=> b [Hleft Hright].
  rewrite /normalized3_zmod.
  split.
  - move=> g h.
    rewrite /delta2_zmod act_id mul_left_id Hleft Hleft subrr add0r.
  - split.
    + move=> g h.
      rewrite /delta2_zmod Hleft raddf0 mul_right_id mul_left_id Hright.
      by rewrite subr0 subrr.
    + move=> g h.
      rewrite /delta2_zmod Hright raddf0 Hright mul_right_id.
      by rewrite sub0r addrN.
Qed.

Lemma delta3_additive_zmod_action :
  forall (a c : C3_zmod) (g h k l : G),
    delta3_zmod (add3_zmod a c) g h k l =
    delta3_zmod a g h k l + delta3_zmod c g h k l.
Proof.
  move=> a c g h k l.
  rewrite /delta3_zmod /add3_zmod !raddfD.
  repeat aac_rewrite addrN.
  aac_reflexivity.
Qed.

Theorem gauge_preserves_three_cocycle_zmod_action :
  forall (a : C3_zmod) (b : C2_zmod),
    three_cocycle_zmod a -> three_cocycle_zmod (gauge_transform_zmod a b).
Proof.
  move=> a b Ha g h k l.
  rewrite /gauge_transform_zmod delta3_additive_zmod_action.
  rewrite (Ha g h k l) delta3_delta2_zero_zmod_action add0r.
  reflexivity.
Qed.

Theorem pentagon_iff_three_cocycle_zmod_action :
  forall a : C3_zmod,
    pentagon_holds_zmod a <-> three_cocycle_zmod a.
Proof. by []. Qed.

End TwistedZmodCoefficients.
