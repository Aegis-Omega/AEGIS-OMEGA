From Coq Require Import Bool.Bool.

(**
  CSTAR v0.6 non-integer coefficient reference model.

  G = Z/2 represented by bool/xor.
  A = Z/2 represented by bool/xor, an abelian group not identified with Z.
  The G-action is trivial, and the cubic cochain is 1 exactly on (1,1,1).
*)

Definition z2_mul_b (g h : bool) : bool := xorb g h.
Definition a_zero_b : bool := false.
Definition a_add_b (x y : bool) : bool := xorb x y.
Definition a_opp_b (x : bool) : bool := x.
Definition trivial_act_b (_g x : bool) : bool := x.

Definition C2_bool := bool -> bool -> bool.
Definition C3_bool := bool -> bool -> bool -> bool.

Definition normalized2_bool (b : C2_bool) : Prop :=
  (forall g : bool, b false g = false) /\
  (forall g : bool, b g false = false).

Definition normalized3_bool (a : C3_bool) : Prop :=
  (forall g h : bool, a false g h = false) /\
  (forall g h : bool, a g false h = false) /\
  (forall g h : bool, a g h false = false).

Definition delta2_bool (b : C2_bool) (g h k : bool) : bool :=
  xorb (b h k)
    (xorb (b (z2_mul_b g h) k)
      (xorb (b g (z2_mul_b h k))
            (b g h))).

Definition delta3_bool (a : C3_bool) (g h k l : bool) : bool :=
  xorb (a h k l)
    (xorb (a (z2_mul_b g h) k l)
      (xorb (a g (z2_mul_b h k) l)
        (xorb (a g h (z2_mul_b k l))
              (a g h k)))).

Definition three_cocycle_bool (a : C3_bool) : Prop :=
  forall g h k l : bool, delta3_bool a g h k l = false.

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
    ~ (forall g h k : bool, delta2_bool b g h k = cubic_bool g h k).
Proof.
  intros b [Hleft Hright] Hcob.
  specialize (Hcob true true true).
  unfold delta2_bool, z2_mul_b, cubic_bool in Hcob.
  simpl in Hcob.
  rewrite (Hleft true) in Hcob.
  rewrite (Hright true) in Hcob.
  destruct (b true true); discriminate.
Qed.
