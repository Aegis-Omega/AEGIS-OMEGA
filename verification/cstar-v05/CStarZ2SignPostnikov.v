From Coq Require Import Bool.Bool ZArith Lia Ring.

Open Scope Z_scope.

(**
  CSTAR v0.5 nontrivial-action reference model.

  G = Z/2 represented by bool/xor.
  A = Z with the sign action: the nonidentity group element acts by x |-> -x.
  The normalized cubic cochain is 1 exactly on (1,1,1).

  The proofs below establish:
  - the sign map is a genuine Z/2 action on Z;
  - the cubic cochain is normalized;
  - it satisfies the twisted 3-cocycle/pentagon equation;
  - it is not a normalized twisted 2-coboundary.
*)

Definition z2_mul (g h : bool) : bool := xorb g h.
Definition sign_act (g : bool) (x : Z) : Z := if g then -x else x.

Lemma sign_act_zero : forall g : bool, sign_act g 0 = 0.
Proof. intros []; reflexivity. Qed.

Lemma sign_act_add : forall (g : bool) (x y : Z),
  sign_act g (x + y) = sign_act g x + sign_act g y.
Proof. intros [] x y; simpl; ring. Qed.

Lemma sign_act_sub : forall (g : bool) (x y : Z),
  sign_act g (x - y) = sign_act g x - sign_act g y.
Proof. intros [] x y; simpl; ring. Qed.

Lemma sign_act_id : forall x : Z, sign_act false x = x.
Proof. reflexivity. Qed.

Lemma sign_act_comp : forall (g h : bool) (x : Z),
  sign_act (z2_mul g h) x = sign_act g (sign_act h x).
Proof. intros [] [] x; simpl; ring. Qed.

Definition C2_sign := bool -> bool -> Z.
Definition C3_sign := bool -> bool -> bool -> Z.

Definition normalized2_sign (b : C2_sign) : Prop :=
  (forall g : bool, b false g = 0) /\
  (forall g : bool, b g false = 0).

Definition normalized3_sign (a : C3_sign) : Prop :=
  (forall g h : bool, a false g h = 0) /\
  (forall g h : bool, a g false h = 0) /\
  (forall g h : bool, a g h false = 0).

Definition delta2_sign (b : C2_sign) (g h k : bool) : Z :=
  sign_act g (b h k)
  - b (z2_mul g h) k
  + b g (z2_mul h k)
  - b g h.

Definition delta3_sign (a : C3_sign) (g h k l : bool) : Z :=
  sign_act g (a h k l)
  - a (z2_mul g h) k l
  + a g (z2_mul h k) l
  - a g h (z2_mul k l)
  + a g h k.

Definition three_cocycle_sign (a : C3_sign) : Prop :=
  forall g h k l : bool, delta3_sign a g h k l = 0.

Definition cubic_sign (g h k : bool) : Z :=
  if andb g (andb h k) then 1 else 0.

Theorem z2_sign_cubic_normalized : normalized3_sign cubic_sign.
Proof.
  unfold normalized3_sign, cubic_sign.
  split.
  - intros g h. reflexivity.
  - split.
    + intros g h. destruct g; reflexivity.
    + intros g h. destruct g, h; reflexivity.
Qed.

Theorem z2_sign_cubic_three_cocycle : three_cocycle_sign cubic_sign.
Proof.
  intros g h k l.
  destruct g, h, k, l; reflexivity.
Qed.

Theorem z2_sign_cubic_not_normalized_coboundary :
  forall b : C2_sign,
    normalized2_sign b ->
    ~ (forall g h k : bool, delta2_sign b g h k = cubic_sign g h k).
Proof.
  intros b [Hleft Hright] Hcob.
  specialize (Hcob true true true).
  unfold delta2_sign, z2_mul, cubic_sign, sign_act in Hcob.
  simpl in Hcob.
  rewrite (Hleft true) in Hcob.
  rewrite (Hright true) in Hcob.
  lia.
Qed.
