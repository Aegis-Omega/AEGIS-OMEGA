Require Import CStarAbelianGroupCohomology.

(**
  CSTAR v0.7: surjective H3 normalization direction only.

  Scope:
  - every degree-3 cocycle in the v0.6 abstract abelian coefficient/action
    model admits a normalized gauge transform;
  - no uniqueness, injectivity, or quasi-isomorphism claim;
  - authority_effect = NONE.

  The imported v0.6 core is the exact byte-copy introduced by probe head
  14854a53ba47792f4b7dca7c4200544e479c5410.
*)

Section H3NormalizationSurjective.

Context {G A : Type}.

Variable e : G.
Variable mul : G -> G -> G.

Hypothesis mul_assoc : forall g h k : G,
  mul (mul g h) k = mul g (mul h k).
Hypothesis mul_left_id : forall g : G, mul e g = g.
Hypothesis mul_right_id : forall g : G, mul g e = g.

Variable zero : A.
Variable add : A -> A -> A.
Variable opp : A -> A.

Hypothesis add_assoc : forall x y z : A,
  add (add x y) z = add x (add y z).
Hypothesis add_comm : forall x y : A,
  add x y = add y x.
Hypothesis add_zero_l : forall x : A,
  add zero x = x.
Hypothesis add_opp_l : forall x : A,
  add (opp x) x = zero.

Variable act : G -> A -> A.
Hypothesis act_zero : forall g : G, act g zero = zero.
Hypothesis act_add : forall (g : G) (x y : A),
  act g (add x y) = add (act g x) (act g y).
Hypothesis act_opp : forall (g : G) (x : A),
  act g (opp x) = opp (act g x).
Hypothesis act_comp : forall (g h : G) (x : A),
  act (mul g h) x = act g (act h x).
Hypothesis act_id : forall x : A, act e x = x.

Theorem h3_normalization_surjective_abelian_action :
  forall a : @C3_A_action G A,
    @three_cocycle_A_action G A mul zero add opp act a ->
    exists b : @C2_A_action G A,
      @normalized3_A_action G A e zero
        (@gauge_transform_A_action G A mul add opp act a b).
Proof.
  intros a Ha.

  pose proof (@add_zero_r A zero add add_comm add_zero_l) as Hadd_zero_r.
  pose proof (@add_opp_r A zero add opp add_comm add_opp_l) as Hadd_opp_r.
  pose proof (@opp_zero A zero add opp
    add_assoc add_comm add_zero_l add_opp_l) as Hopp_zero.
  pose proof (@opp_involutive A zero add opp
    add_assoc add_comm add_zero_l add_opp_l) as Hopp_involutive.
  pose proof (@opp_add A zero add opp
    add_assoc add_comm add_zero_l add_opp_l) as Hopp_add.
  pose proof (@swap_head A add add_assoc add_comm) as Hswap_head.

  assert (Hcancel_pos : forall x z : A,
    add x (add (opp x) z) = z).
  {
    intros x z.
    rewrite <- add_assoc.
    rewrite Hadd_opp_r.
    apply add_zero_l.
  }

  assert (Hcancel_neg : forall x z : A,
    add (opp x) (add x z) = z).
  {
    intros x z.
    rewrite <- add_assoc.
    rewrite add_opp_l.
    apply add_zero_l.
  }

  assert (Hedge : forall x : G, a e x e = zero).
  {
    intro x.
    pose proof (Ha e e x e) as H.
    unfold delta3_A_action in H.
    rewrite act_id in H.
    repeat rewrite mul_left_id in H.
    rewrite mul_right_id in H.
    rewrite add_opp_l in H.
    rewrite Hadd_zero_r in H.
    rewrite add_opp_l in H.
    rewrite Hadd_zero_r in H.
    exact H.
  }

  set (b := (fun g h => add (a g h e) (opp (a e g h))) :
    @C2_A_action G A).
  exists b.

  unfold normalized3_A_action.
  split.

  - intros g h.
    pose proof (Ha e e g h) as Hleft.
    unfold delta3_A_action in Hleft.
    rewrite act_id in Hleft.
    repeat rewrite mul_left_id in Hleft.
    rewrite Hcancel_pos in Hleft.

    unfold gauge_transform_A_action, add3_A_action, delta2_A_action.
    rewrite act_id.
    repeat rewrite mul_left_id.
    rewrite Hcancel_pos.
    unfold b.
    rewrite (Hedge (mul g h)).
    rewrite (Hedge g).
    repeat rewrite add_zero_l.
    rewrite Hopp_involutive.
    exact Hleft.

  - split.

    + intros g h.
      pose proof (Ha g e e h) as Hmid.
      unfold delta3_A_action in Hmid.
      rewrite mul_right_id in Hmid.
      repeat rewrite mul_left_id in Hmid.
      rewrite Hcancel_neg in Hmid.

      pose proof (f_equal opp Hmid) as Hmid_neg.
      rewrite Hopp_zero in Hmid_neg.
      repeat rewrite Hopp_add in Hmid_neg.
      repeat rewrite Hopp_involutive in Hmid_neg.

      unfold gauge_transform_A_action, add3_A_action, delta2_A_action.
      rewrite mul_right_id.
      repeat rewrite mul_left_id.
      rewrite Hcancel_neg.
      unfold b.
      rewrite (Hedge h).
      rewrite (Hedge g).
      repeat rewrite add_zero_l.
      rewrite Hopp_zero.
      rewrite Hadd_zero_r.
      rewrite act_opp.
      rewrite (Hswap_head
        (a g e h)
        (opp (act g (a e e h)))
        (opp (a g e e))).
      exact Hmid_neg.

    + intros g h.
      pose proof (Ha g h e e) as Hright.
      unfold delta3_A_action in Hright.
      repeat rewrite mul_right_id in Hright.
      rewrite Hcancel_pos in Hright.

      unfold gauge_transform_A_action, add3_A_action, delta2_A_action.
      repeat rewrite mul_right_id.
      rewrite Hadd_opp_r.
      rewrite Hadd_zero_r.
      unfold b.
      rewrite (Hedge h).
      rewrite (Hedge (mul g h)).
      repeat rewrite Hopp_zero.
      repeat rewrite Hadd_zero_r.
      rewrite (Hswap_head
        (a g h e)
        (act g (a h e e))
        (opp (a (mul g h) e e))).
      rewrite (add_comm
        (a g h e)
        (opp (a (mul g h) e e))).
      exact Hright.
Qed.

End H3NormalizationSurjective.

Set Printing Implicit.
Check @h3_normalization_surjective_abelian_action.
Print Assumptions h3_normalization_surjective_abelian_action.
