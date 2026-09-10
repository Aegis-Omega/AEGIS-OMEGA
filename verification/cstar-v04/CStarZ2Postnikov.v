From Coq Require Import Bool.Bool.

(**
  A finite reference proof for G = Z/2 and A = Z/2 with trivial action.
  Group and coefficient addition are represented by xor.  The cubic 3-cochain
  is one exactly on (1,1,1).  The theorem below proves that this normalized
  3-cocycle is not the coboundary of any normalized 2-cochain.
*)

Definition z2_mul (g h : bool) : bool := xorb g h.

Definition C2_Z2 := bool -> bool -> bool.
Definition C3_Z2 := bool -> bool -> bool -> bool.

Definition normalized2_Z2 (b : C2_Z2) : Prop :=
  (forall g : bool, b false g = false) /\
  (forall g : bool, b g false = false).

Definition normalized3_Z2 (a : C3_Z2) : Prop :=
  (forall g h : bool, a false g h = false) /\
  (forall g h : bool, a g false h = false) /\
  (forall g h : bool, a g h false = false).

(** In characteristic two, subtraction equals addition, hence xor in every slot. *)
Definition delta2_Z2 (b : C2_Z2) (g h k : bool) : bool :=
  xorb (b h k)
    (xorb (b (z2_mul g h) k)
      (xorb (b g (z2_mul h k))
            (b g h))).

Definition delta3_Z2 (a : C3_Z2) (g h k l : bool) : bool :=
  xorb (a h k l)
    (xorb (a (z2_mul g h) k l)
      (xorb (a g (z2_mul h k) l)
        (xorb (a g h (z2_mul k l))
              (a g h k)))).

Definition three_cocycle_Z2 (a : C3_Z2) : Prop :=
  forall g h k l : bool, delta3_Z2 a g h k l = false.

Definition cubic_Z2 (g h k : bool) : bool :=
  andb g (andb h k).

Theorem z2_cubic_normalized : normalized3_Z2 cubic_Z2.
Proof.
  unfold normalized3_Z2, cubic_Z2.
  split.
  - intros g h. reflexivity.
  - split.
    + intros g h. destruct g; reflexivity.
    + intros g h. destruct g, h; reflexivity.
Qed.

Theorem z2_cubic_three_cocycle : three_cocycle_Z2 cubic_Z2.
Proof.
  intros g h k l.
  destruct g, h, k, l; reflexivity.
Qed.

Theorem z2_cubic_not_normalized_coboundary :
  forall b : C2_Z2,
    normalized2_Z2 b ->
    ~ (forall g h k : bool, delta2_Z2 b g h k = cubic_Z2 g h k).
Proof.
  intros b [Hleft Hright] Hcob.
  specialize (Hcob true true true).
  unfold delta2_Z2, z2_mul, cubic_Z2 in Hcob.
  simpl in Hcob.
  rewrite (Hleft true) in Hcob.
  rewrite (Hright true) in Hcob.
  destruct (b true true); discriminate.
Qed.
