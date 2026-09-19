Require Import CStarAbelianGroupCohomology.

(**
  CSTAR v0.8: injective H3-normalization witness boundary.

  Scope:
  - if the coboundary of an arbitrary degree-2 cochain is normalized as a
    degree-3 cochain, then the same coboundary has a normalized degree-2
    witness;
  - this is the witness-normalization lemma needed for injectivity on H3
    gauge classes;
  - no full complex quasi-isomorphism claim;
  - authority_effect = NONE.
*)

Section H3NormalizationInjective.

Context {G A : Type}.

Variable e : G.
Variable mul : G -> G -> G.

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
Hypothesis act_add : forall (g : G) (x y : A),
  act g (add x y) = add (act g x) (act g y).
Hypothesis act_opp : forall (g : G) (x : A),
  act g (opp x) = opp (act g x).
Hypothesis act_comp : forall (g h : G) (x : A),
  act (mul g h) x = act g (act h x).
Hypothesis act_id : forall x : A, act e x = x.

Definition add2_A_action_local
  (b c : @C2_A_action G A) : @C2_A_action G A :=
  fun g h => add (b g h) (c g h).

Definition r4_local (a b c d : A) : A :=
  add a (add b (add c d)).

Lemma r4_pointwise_add_local :
  forall a1 a2 a3 a4 c1 c2 c3 c4 : A,
    r4_local
      (add a1 c1) (add a2 c2) (add a3 c3) (add a4 c4) =
    add (r4_local a1 a2 a3 a4)
        (r4_local c1 c2 c3 c4).
Proof.
  intros a1 a2 a3 a4 c1 c2 c3 c4.
  unfold r4_local.
  rewrite (@medial A add add_assoc add_comm a3 c3 a4 c4).
  rewrite (@medial A add add_assoc add_comm
    a2 c2 (add a3 a4) (add c3 c4)).
  rewrite (@medial A add add_assoc add_comm
    a1 c1 (add a2 (add a3 a4)) (add c2 (add c3 c4))).
  reflexivity.
Qed.

Lemma delta2_additive_local :
  forall (b c : @C2_A_action G A) (g h k : G),
    @delta2_A_action G A mul add opp act
      (add2_A_action_local b c) g h k =
    add
      (@delta2_A_action G A mul add opp act b g h k)
      (@delta2_A_action G A mul add opp act c g h k).
Proof.
  intros b c g h k.
  unfold delta2_A_action, add2_A_action_local.
  rewrite act_add.
  repeat rewrite (@opp_add A zero add opp
    add_assoc add_comm add_zero_l add_opp_l).
  change
    (r4_local
      (add (act g (b h k)) (act g (c h k)))
      (add (opp (b (mul g h) k)) (opp (c (mul g h) k)))
      (add (b g (mul h k)) (c g (mul h k)))
      (add (opp (b g h)) (opp (c g h))) =
     add
      (r4_local
        (act g (b h k))
        (opp (b (mul g h) k))
        (b g (mul h k))
        (opp (b g h)))
      (r4_local
        (act g (c h k))
        (opp (c (mul g h) k))
        (c g (mul h k))
        (opp (c g h)))).
  apply r4_pointwise_add_local.
Qed.

Theorem normalized_delta2_has_normalized_witness_abelian_action :
  forall b : @C2_A_action G A,
    @normalized3_A_action G A e zero
      (@delta2_A_action G A mul add opp act b) ->
    exists bn : @C2_A_action G A,
      @normalized2_A_action G A e zero bn /\
      forall g h k : G,
        @delta2_A_action G A mul add opp act bn g h k =
        @delta2_A_action G A mul add opp act b g h k.
Proof.
  intros b Hnorm.
  destruct Hnorm as [Hleft [Hmid Hright]].

  pose proof (@add_zero_r A zero add add_comm add_zero_l) as Hadd_zero_r.
  pose proof (@add_opp_r A zero add opp add_comm add_opp_l) as Hadd_opp_r.
  pose proof (@opp_involutive A zero add opp
    add_assoc add_comm add_zero_l add_opp_l) as Hopp_involutive.

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

  set (c := b e e).

  assert (Hbe : forall h : G, b e h = c).
  {
    intro h.
    pose proof (Hleft e h) as H.
    unfold delta2_A_action in H.
    rewrite act_id in H.
    repeat rewrite mul_left_id in H.
    rewrite Hcancel_pos in H.
    change (add (b e h) (opp c) = zero) in H.
    pose proof (@inverse_unique_l A zero add opp
      add_assoc add_comm add_zero_l add_opp_l
      (opp c) (b e h) H) as Hu.
    rewrite Hopp_involutive in Hu.
    exact Hu.
  }

  assert (Hbge : forall g : G, b g e = act g c).
  {
    intro g.
    pose proof (Hright g e) as H.
    unfold delta2_A_action in H.
    repeat rewrite mul_right_id in H.
    rewrite Hcancel_neg in H.
    change (add (act g c) (opp (b g e)) = zero) in H.
    pose proof (@inverse_unique_l A zero add opp
      add_assoc add_comm add_zero_l add_opp_l
      (opp (b g e)) (act g c) H) as Hu.
    rewrite Hopp_involutive in Hu.
    symmetry.
    exact Hu.
  }

  set (q :=
    (fun g _h => opp (act g c)) :
      @C2_A_action G A).

  assert (Hqzero :
    forall g h k : G,
      @delta2_A_action G A mul add opp act q g h k = zero).
  {
    intros g h k.
    unfold delta2_A_action, q.
    rewrite act_opp.
    rewrite <- act_comp.
    repeat rewrite Hopp_involutive.
    rewrite Hcancel_neg.
    apply add_opp_l.
  }

  set (bn := add2_A_action_local b q).
  exists bn.
  split.

  - unfold normalized2_A_action.
    split.
    + intro h.
      unfold bn, add2_A_action_local, q.
      rewrite Hbe.
      rewrite act_id.
      apply Hadd_opp_r.
    + intro g.
      unfold bn, add2_A_action_local, q.
      rewrite Hbge.
      apply Hadd_opp_r.

  - intros g h k.
    unfold bn.
    rewrite delta2_additive_local.
    rewrite Hqzero.
    apply Hadd_zero_r.
Qed.


Theorem normalized_gauge_equivalence_has_normalized_witness_abelian_action :
  forall (a : @C3_A_action G A) (b : @C2_A_action G A),
    @normalized3_A_action G A e zero a ->
    @normalized3_A_action G A e zero
      (@gauge_transform_A_action G A mul add opp act a b) ->
    exists bn : @C2_A_action G A,
      @normalized2_A_action G A e zero bn /\
      forall g h k : G,
        @gauge_transform_A_action G A mul add opp act a bn g h k =
        @gauge_transform_A_action G A mul add opp act a b g h k.
Proof.
  intros a b Ha Hg.
  destruct Ha as [HaL [HaM HaR]].
  destruct Hg as [HgL [HgM HgR]].

  assert (Hdbnorm :
    @normalized3_A_action G A e zero
      (@delta2_A_action G A mul add opp act b)).
  {
    unfold normalized3_A_action.
    split.
    - intros g h.
      pose proof (HgL g h) as H.
      unfold gauge_transform_A_action, add3_A_action in H.
      rewrite (HaL g h) in H.
      rewrite add_zero_l in H.
      exact H.
    - split.
      + intros g h.
        pose proof (HgM g h) as H.
        unfold gauge_transform_A_action, add3_A_action in H.
        rewrite (HaM g h) in H.
        rewrite add_zero_l in H.
        exact H.
      + intros g h.
        pose proof (HgR g h) as H.
        unfold gauge_transform_A_action, add3_A_action in H.
        rewrite (HaR g h) in H.
        rewrite add_zero_l in H.
        exact H.
  }

  destruct
    (normalized_delta2_has_normalized_witness_abelian_action b Hdbnorm)
    as [bn [Hbn Hdelta]].
  exists bn.
  split.
  - exact Hbn.
  - intros g h k.
    unfold gauge_transform_A_action, add3_A_action.
    rewrite (Hdelta g h k).
    reflexivity.
Qed.

End H3NormalizationInjective.

Set Printing Implicit.
Check @normalized_delta2_has_normalized_witness_abelian_action.
Print Assumptions normalized_delta2_has_normalized_witness_abelian_action.
Check @normalized_gauge_equivalence_has_normalized_witness_abelian_action.
Print Assumptions normalized_gauge_equivalence_has_normalized_witness_abelian_action.
