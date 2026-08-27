(*
  AEGIS Ω — QForm normalized quotient error algebra v1

  Scope:
  - exact rational algebra only;
  - no transcendental evaluation;
  - no constructive-real transport;
  - no Gaussian-tail or quadrature theorem;
  - no Weil/RH promotion.

  The public *_v1 constants are proposition-valued interfaces so concrete
  falsifiers can instantiate and reduce them.  Machine authority is carried by
  the corresponding *_sound_v1 theorems below, not by mere typechecking of the
  interfaces.
*)

From Coq Require Import QArith.
From Coq Require Import Qabs.
From Coq Require Import Qfield.
From Coq Require Import Psatz.

Open Scope Q_scope.

Definition qform_error_hypotheses_v1
    (a ahat b bhat ea eb m : Q) : Prop :=
  0 <= a /\
  0 <= ahat /\
  0 <= b /\
  0 <= bhat /\
  0 <= ea /\
  0 <= eb /\
  0 < m /\
  m <= b /\
  m <= bhat /\
  Qabs (ahat - a) <= ea /\
  Qabs (bhat - b) <= eb.

Definition qform_cross_budget_v1
    (a b ea eb : Q) : Q :=
  ea * b + a * eb.

Definition normalized_quotient_cross_error_v1
    (a ahat b bhat ea eb m : Q) : Prop :=
  qform_error_hypotheses_v1 a ahat b bhat ea eb m /\
  Qabs (ahat * b - a * bhat) <= qform_cross_budget_v1 a b ea eb.

Definition normalized_quotient_stability_v1
    (a ahat b bhat ea eb m : Q) : Prop :=
  normalized_quotient_cross_error_v1 a ahat b bhat ea eb m /\
  Qabs (ahat / bhat - a / b)
    <= qform_cross_budget_v1 a b ea eb / (m * m).

Theorem normalized_quotient_cross_error_sound_v1 :
  forall a ahat b bhat ea eb m : Q,
    qform_error_hypotheses_v1 a ahat b bhat ea eb m ->
    normalized_quotient_cross_error_v1 a ahat b bhat ea eb m.
Proof.
  intros a ahat b bhat ea eb m H.
  split; [exact H|].
  unfold qform_error_hypotheses_v1 in H.
  unfold qform_cross_budget_v1.
  destruct H as
    [Ha [Hahat [Hb [Hbhat [Hea [Heb [Hm [Hmb [Hmbhat [Hda Hdb]]]]]]]]]].
  apply Qabs_diff_Qle_condition in Hda.
  apply Qabs_diff_Qle_condition in Hdb.
  apply (proj2 (Qabs_Qle_condition
    (ahat * b - a * bhat) (ea * b + a * eb))).
  destruct Hda as [Hda_lo Hda_hi].
  destruct Hdb as [Hdb_lo Hdb_hi].
  split; nra.
Qed.

Lemma qform_abs_quotient_cross_identity_v1 :
  forall a ahat b bhat : Q,
    0 < b ->
    0 < bhat ->
    Qabs (ahat / bhat - a / b)
      == Qabs (ahat * b - a * bhat) / (b * bhat).
Proof.
  intros a ahat b bhat Hb Hbhat.
  setoid_replace (ahat / bhat - a / b)
    with ((ahat * b - a * bhat) / (b * bhat)).
  2: { field; nra. }
  unfold Qdiv at 1 2.
  setoid_rewrite Qabs_Qmult.
  setoid_rewrite Qabs_Qinv.
  setoid_replace (Qabs (b * bhat)) with (b * bhat).
  2: { apply Qabs_pos; nra. }
  reflexivity.
Qed.

Theorem normalized_quotient_stability_sound_v1 :
  forall a ahat b bhat ea eb m : Q,
    qform_error_hypotheses_v1 a ahat b bhat ea eb m ->
    normalized_quotient_stability_v1 a ahat b bhat ea eb m.
Proof.
  intros a ahat b bhat ea eb m Hhyp.
  assert (Hcross : normalized_quotient_cross_error_v1
    a ahat b bhat ea eb m).
  { apply normalized_quotient_cross_error_sound_v1. exact Hhyp. }
  split; [exact Hcross|].

  unfold normalized_quotient_cross_error_v1 in Hcross.
  destruct Hcross as [_ Hcross].
  unfold qform_error_hypotheses_v1 in Hhyp.
  destruct Hhyp as
    [Ha [Hahat [Hb [Hbhat [Hea [Heb [Hm [Hmb [Hmbhat [Hda Hdb]]]]]]]]]].
  unfold qform_cross_budget_v1 in *.

  assert (Hbpos : 0 < b) by nra.
  assert (Hbhatpos : 0 < bhat) by nra.
  assert (HDpos : 0 < b * bhat) by nra.
  assert (HMpos : 0 < m * m) by nra.
  assert (HE : 0 <= ea * b + a * eb) by nra.
  assert (HMD : m * m <= b * bhat) by nra.

  setoid_replace (Qabs (ahat / bhat - a / b))
    with (Qabs (ahat * b - a * bhat) / (b * bhat)).
  2: { apply qform_abs_quotient_cross_identity_v1; assumption. }

  apply Qle_shift_div_r; [exact HDpos|].
  eapply Qle_trans; [exact Hcross|].
  setoid_replace
    ((ea * b + a * eb) / (m * m) * (b * bhat))
    with (((ea * b + a * eb) * (b * bhat)) / (m * m)).
  2: { field; nra. }
  apply Qle_shift_div_l; [exact HMpos|].
  nra.
Qed.
