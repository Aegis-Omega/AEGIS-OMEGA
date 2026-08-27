(*
  AEGIS Ω — QForm normalized quotient error algebra on the production O0
  constructive-real carrier.

  Scope:
  - direct proof over O0RealsV1 = CRealConstructive;
  - no rational theorem used as authority;
  - no Gaussian-tail theorem;
  - no quadrature theorem;
  - no formula-to-Weil or RH promotion.
*)

Require Import AnalyticDefinitions.
From Coq Require Import Reals.Abstract.ConstructiveReals.
From Coq Require Import Reals.Abstract.ConstructiveAbs.
From Coq Require Import Ring.

Local Open Scope ConstructiveReals.

Add Ring O0Ring : (CRisRing O0RealsV1).

Definition o0_error_hypotheses_v1
    (a ahat b bhat ea eb m : O0RealV1) : Prop :=
  O0LeV1 O0ZeroV1 a /\
  O0LeV1 O0ZeroV1 ahat /\
  O0LeV1 O0ZeroV1 b /\
  O0LeV1 O0ZeroV1 bhat /\
  O0LeV1 O0ZeroV1 ea /\
  O0LeV1 O0ZeroV1 eb /\
  O0LtPropV1 O0ZeroV1 m /\
  O0LeV1 m b /\
  O0LeV1 m bhat /\
  O0LeV1 (O0AbsV1 (O0MinusV1 ahat a)) ea /\
  O0LeV1 (O0AbsV1 (O0MinusV1 bhat b)) eb.

Definition o0_cross_budget_v1
    (a b ea eb : O0RealV1) : O0RealV1 :=
  CRplus O0RealsV1
    (CRmult O0RealsV1 ea b)
    (CRmult O0RealsV1 a eb).

Definition o0_lt_set_v1
    (x y : O0RealV1)
    (H : O0LtPropV1 x y) : O0LtV1 x y :=
  CRltEpsilon O0RealsV1 x y H.

Definition o0_div_by_positive_v1
    (x y : O0RealV1)
    (Hy : O0LtPropV1 O0ZeroV1 y) : O0RealV1 :=
  CRmult O0RealsV1 x
    (CRinv O0RealsV1 y
      (inr (o0_lt_set_v1 O0ZeroV1 y Hy))).

Definition o0_square_positive_prop_v1
    (m : O0RealV1)
    (Hm : O0LtPropV1 O0ZeroV1 m)
    : O0LtPropV1 O0ZeroV1 (CRmult O0RealsV1 m m) :=
  CRltForget O0RealsV1 O0ZeroV1 (CRmult O0RealsV1 m m)
    (CRmult_lt_0_compat O0RealsV1 m m
      (o0_lt_set_v1 O0ZeroV1 m Hm)
      (o0_lt_set_v1 O0ZeroV1 m Hm)).

Definition o0_normalized_quotient_cross_error_v1
    (a ahat b bhat ea eb m : O0RealV1) : Prop :=
  o0_error_hypotheses_v1 a ahat b bhat ea eb m /\
  O0LeV1
    (O0AbsV1
      (O0MinusV1
        (CRmult O0RealsV1 ahat b)
        (CRmult O0RealsV1 a bhat)))
    (o0_cross_budget_v1 a b ea eb).

Definition o0_normalized_quotient_stability_v1
    (a ahat b bhat ea eb m : O0RealV1) : Prop :=
  o0_error_hypotheses_v1 a ahat b bhat ea eb m /\
  forall
    (Hm : O0LtPropV1 O0ZeroV1 m)
    (Hb : O0LtPropV1 O0ZeroV1 b)
    (Hbhat : O0LtPropV1 O0ZeroV1 bhat),
    O0LeV1
      (O0AbsV1
        (O0MinusV1
          (o0_div_by_positive_v1 ahat bhat Hbhat)
          (o0_div_by_positive_v1 a b Hb)))
      (o0_div_by_positive_v1
        (o0_cross_budget_v1 a b ea eb)
        (CRmult O0RealsV1 m m)
        (o0_square_positive_prop_v1 m Hm)).

Theorem o0_normalized_quotient_cross_error_sound_v1 :
  forall a ahat b bhat ea eb m : O0RealV1,
    o0_error_hypotheses_v1 a ahat b bhat ea eb m ->
    o0_normalized_quotient_cross_error_v1
      a ahat b bhat ea eb m.
Proof.
  intros a ahat b bhat ea eb m H.
  split; [exact H|].
  unfold o0_error_hypotheses_v1 in H.
  destruct H as
    [Ha [Hahat [Hb [Hbhat [Hea [Heb [Hm [Hmb [Hmbhat [Hda Hdb]]]]]]]]]].
  unfold o0_cross_budget_v1.
  unfold O0LeV1, O0AbsV1, O0MinusV1, O0OppV1, O0ZeroV1 in *.

  setoid_replace
    (ahat * b - a * bhat)
    with ((ahat - a) * b + a * (b - bhat)).
  2: ring.

  eapply CRle_trans.
  - apply CRabs_triang.
  - rewrite CRabs_mult, CRabs_mult.
    rewrite (CRabs_right b Hb), (CRabs_right a Ha).
    apply CRplus_le_compat.
    + apply CRmult_le_compat_r; assumption.
    + rewrite CRabs_minus_sym.
      apply CRmult_le_compat_l; assumption.
Qed.

Theorem o0_normalized_quotient_stability_sound_v1 :
  forall a ahat b bhat ea eb m : O0RealV1,
    o0_error_hypotheses_v1 a ahat b bhat ea eb m ->
    o0_normalized_quotient_stability_v1
      a ahat b bhat ea eb m.
Proof.
  intros a ahat b bhat ea eb m Hhyp.
  split; [exact Hhyp|].
  intros HmProp HbProp HbhatProp.

  pose proof
    (o0_normalized_quotient_cross_error_sound_v1
      a ahat b bhat ea eb m Hhyp) as HcrossPair.
  destruct HcrossPair as [_ Hcross].

  unfold o0_error_hypotheses_v1 in Hhyp.
  destruct Hhyp as
    [Ha [Hahat [Hb [Hbhat [Hea [Heb [HmHyp [Hmb [Hmbhat [Hda Hdb]]]]]]]]]].

  pose proof (o0_lt_set_v1 O0ZeroV1 m HmProp) as Hm.
  pose proof (o0_lt_set_v1 O0ZeroV1 b HbProp) as HbS.
  pose proof (o0_lt_set_v1 O0ZeroV1 bhat HbhatProp) as HbhatS.
  pose proof
    (o0_lt_set_v1 O0ZeroV1 (m * m)
      (o0_square_positive_prop_v1 m HmProp)) as Hm2.

  assert (Hden : O0LtV1 O0ZeroV1 (b * bhat)).
  { apply CRmult_lt_0_compat; assumption. }
  assert (HmNonneg : O0LeV1 O0ZeroV1 m).
  { apply CRlt_asym, Hm. }
  assert (HbNonneg : O0LeV1 O0ZeroV1 b).
  { exact Hb. }
  assert (HdenNonneg : O0LeV1 O0ZeroV1 (b * bhat)).
  { apply CRlt_asym, Hden. }
  assert (Hm2leDen : O0LeV1 (m * m) (b * bhat)).
  {
    eapply CRle_trans.
    - apply CRmult_le_compat_r; [exact HmNonneg|exact Hmb].
    - apply CRmult_le_compat_l; [exact HbNonneg|exact Hmbhat].
  }
  assert (HbudgetNonneg :
    O0LeV1 O0ZeroV1 (o0_cross_budget_v1 a b ea eb)).
  {
    unfold o0_cross_budget_v1, O0LeV1, O0ZeroV1 in *.
    apply CRplus_le_compat.
    - apply CRmult_le_0_compat; assumption.
    - apply CRmult_le_0_compat; assumption.
  }

  unfold o0_div_by_positive_v1.
  unfold O0LeV1, O0AbsV1, O0MinusV1, O0OppV1 in *.

  apply (CRmult_le_reg_r (b * bhat)).
  - exact Hden.
  - setoid_replace
      (CRabs O0RealsV1
        (ahat * CRinv O0RealsV1 bhat
                  (inr (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) bhat HbhatProp))
         - a * CRinv O0RealsV1 b
                  (inr (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) b HbProp)))
       * (b * bhat))
      with (CRabs O0RealsV1 (ahat * b - a * bhat)).
    2: {
      rewrite <- (CRabs_right (b * bhat) HdenNonneg).
      rewrite <- CRabs_mult.
      apply CRabs_morph.
      setoid_replace
        ((ahat * CRinv O0RealsV1 bhat
                    (inr (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) bhat HbhatProp))
          - a * CRinv O0RealsV1 b
                    (inr (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) b HbProp)))
         * (b * bhat))
        with
        (ahat * b *
           (CRinv O0RealsV1 bhat
             (inr (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) bhat HbhatProp)) * bhat)
         - a * bhat *
           (CRinv O0RealsV1 b
             (inr (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) b HbProp)) * b)).
      2: ring.
      rewrite
        (CRinv_l bhat
          (inr (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) bhat HbhatProp))),
        (CRinv_l b
          (inr (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) b HbProp))).
      ring.
    }

    eapply CRle_trans; [exact Hcross|].

    unfold o0_cross_budget_v1.
    setoid_replace
      ((ea * b + a * eb) *
         CRinv O0RealsV1 (m * m)
           (inr
             (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) (m * m)
               (o0_square_positive_prop_v1 m HmProp)))
       * (b * bhat))
      with
      ((ea * b + a * eb) *
        (CRinv O0RealsV1 (m * m)
          (inr
            (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) (m * m)
              (o0_square_positive_prop_v1 m HmProp)))
         * (b * bhat))).
    2: ring.

    rewrite <- (CRmult_1_r (ea * b + a * eb)).
    apply CRmult_le_compat_l.
    + exact HbudgetNonneg.
    + setoid_replace
        (CR_of_Q O0RealsV1 1)
        with
        (CRinv O0RealsV1 (m * m)
          (inr
            (o0_lt_set_v1 (CR_of_Q O0RealsV1 0) (m * m)
              (o0_square_positive_prop_v1 m HmProp)))
         * (m * m)).
      2: {
        symmetry.
        apply CRinv_l.
      }
      apply CRmult_le_compat_l.
      * apply CRlt_asym.
        apply CRinv_0_lt_compat.
        exact Hm2.
      * exact Hm2leDen.
Qed.
