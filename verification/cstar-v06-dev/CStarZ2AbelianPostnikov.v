From Coq Require Import Bool.Bool.
From AAC_tactics Require Import AAC.
Require Import CStarAbelianGroupCohomology.

(**
  CSTAR v0.6 reference model:
  G = Z/2 represented by bool/xor.
  A = Z/2 represented by bool/xor as an arbitrary abelian group.
  The G-action on A is trivial.
*)

Definition z2_mul (g h : bool) : bool := xorb g h.
Definition a_zero : bool := false.
Definition a_add (x y : bool) : bool := xorb x y.
Definition a_opp (x : bool) : bool := x.
Definition trivial_act (_g x : bool) : bool := x.

Lemma z2_mul_assoc : forall g h k,
  z2_mul (z2_mul g h) k = z2_mul g (z2_mul h k).
Proof. intros [] [] []; reflexivity. Qed.

Lemma z2_mul_left_id : forall g, z2_mul false g = g.
Proof. intros []; reflexivity. Qed.

Lemma z2_mul_right_id : forall g, z2_mul g false = g.
Proof. intros []; reflexivity. Qed.

Lemma a_add_assoc : forall x y z,
  a_add x (a_add y z) = a_add (a_add x y) z.
Proof. intros [] [] []; reflexivity. Qed.

Lemma a_add_comm : forall x y, a_add x y = a_add y x.
Proof. intros [] []; reflexivity. Qed.

Lemma a_add_zero_l : forall x, a_add a_zero x = x.
Proof. intros []; reflexivity. Qed.

Lemma a_add_opp_l : forall x, a_add (a_opp x) x = a_zero.
Proof. intros []; reflexivity. Qed.

Lemma trivial_act_zero : forall g, trivial_act g a_zero = a_zero.
Proof. reflexivity. Qed.

Lemma trivial_act_add : forall g x y,
  trivial_act g (a_add x y) = a_add (trivial_act g x) (trivial_act g y).
Proof. reflexivity. Qed.

Lemma trivial_act_opp : forall g x,
  trivial_act g (a_opp x) = a_opp (trivial_act g x).
Proof. reflexivity. Qed.

Lemma trivial_act_comp : forall g h x,
  trivial_act (z2_mul g h) x = trivial_act g (trivial_act h x).
Proof. reflexivity. Qed.

Lemma trivial_act_id : forall x, trivial_act false x = x.
Proof. reflexivity. Qed.

Definition C2_bool := bool -> bool -> bool.
Definition C3_bool := bool -> bool -> bool -> bool.

Definition normalized2_bool (b : C2_bool) : Prop :=
  (forall g, b false g = false) /\
  (forall g, b g false = false).

Definition normalized3_bool (a : C3_bool) : Prop :=
  (forall g h, a false g h = false) /\
  (forall g h, a g false h = false) /\
  (forall g h, a g h false = false).

Definition delta2_bool (b : C2_bool) (g h k : bool) : bool :=
  xorb
    (xorb (trivial_act g (b h k)) (a_opp (b (z2_mul g h) k)))
    (xorb (b g (z2_mul h k)) (a_opp (b g h))).

Definition delta3_bool (a : C3_bool) (g h k l : bool) : bool :=
  xorb
    (xorb (trivial_act g (a h k l)) (a_opp (a (z2_mul g h) k l)))
    (xorb
      (xorb (a g (z2_mul h k) l) (a_opp (a g h (z2_mul k l))))
      (a g h k)).

Definition three_cocycle_bool (a : C3_bool) : Prop :=
  forall g h k l, delta3_bool a g h k l = false.

Definition cubic_bool (g h k : bool) : bool := andb g (andb h k).

Theorem z2_bool_cubic_normalized : normalized3_bool cubic_bool.
Proof.
  unfold normalized3_bool, cubic_bool.
  split.
  - intros g h. reflexivity.
  - split.
    + intros g h. destruct g; reflexivity.
    + intros g h. destruct g, h; reflexivity.
Qed.

Theorem z2_bool_cubic_three_cocycle : three_cocycle_bool cubic_bool.
Proof.
  intros g h k l.
  destruct g, h, k, l; reflexivity.
Qed.

Theorem z2_bool_cubic_not_normalized_coboundary :
  forall b : C2_bool,
    normalized2_bool b ->
    ~ (forall g h k, delta2_bool b g h k = cubic_bool g h k).
Proof.
  intros b [Hleft Hright] Hcob.
  specialize (Hcob true true true).
  unfold delta2_bool, z2_mul, trivial_act, a_opp, cubic_bool in Hcob.
  simpl in Hcob.
  rewrite (Hleft true) in Hcob.
  rewrite (Hright true) in Hcob.
  destruct (b true true); discriminate.
Qed.
