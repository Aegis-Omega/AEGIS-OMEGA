Require Import CStarV09H3ClassEquivalence.

(**
  CSTAR v0.10: gauge-relation equivalence laws.

  Scope:
  - prove reflexivity, symmetry, and transitivity for the full degree-3
    gauge relation introduced in v0.9;
  - prove the same three laws for the normalized-witness gauge relation;
  - no quotient type is constructed here;
  - no arbitrary-degree chain-complex quasi-isomorphism is claimed;
  - authority_effect = NONE.
*)

Section H3GaugeEquivalenceRelations.

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

Definition zero2_relation_local : @C2_A_action G A :=
  fun _g _h => zero.

Definition opp2_relation_local
  (b : @C2_A_action G A) : @C2_A_action G A :=
  fun g h => opp (b g h).

Definition add2_relation_local
  (b c : @C2_A_action G A) : @C2_A_action G A :=
  fun g h => add (b g h) (c g h).

Definition r4_relation_local (a b c d : A) : A :=
  add a (add b (add c d)).

Lemma r4_relation_pointwise_add :
  forall a1 a2 a3 a4 c1 c2 c3 c4 : A,
    r4_relation_local
      (add a1 c1) (add a2 c2) (add a3 c3) (add a4 c4) =
    add (r4_relation_local a1 a2 a3 a4)
        (r4_relation_local c1 c2 c3 c4).
Proof.
  intros a1 a2 a3 a4 c1 c2 c3 c4.
  unfold r4_relation_local.
  rewrite (@medial A add add_assoc add_comm a3 c3 a4 c4).
  rewrite (@medial A add add_assoc add_comm
    a2 c2 (add a3 a4) (add c3 c4)).
  rewrite (@medial A add add_assoc add_comm
    a1 c1 (add a2 (add a3 a4)) (add c2 (add c3 c4))).
  reflexivity.
Qed.

Lemma delta2_zero_relation_local :
  forall g h k : G,
    @delta2_A_action G A mul add opp act
      zero2_relation_local g h k = zero.
Proof.
  intros g h k.
  unfold delta2_A_action, zero2_relation_local.
  rewrite act_zero.
  repeat rewrite (@opp_zero A zero add opp
    add_assoc add_comm add_zero_l add_opp_l).
  repeat rewrite add_zero_l.
  reflexivity.
Qed.

Lemma delta2_opp_relation_local :
  forall (b : @C2_A_action G A) (g h k : G),
    @delta2_A_action G A mul add opp act
      (opp2_relation_local b) g h k =
    opp (@delta2_A_action G A mul add opp act b g h k).
Proof.
  intros b g h k.
  unfold delta2_A_action, opp2_relation_local.
  rewrite act_opp.
  repeat rewrite (@opp_involutive A zero add opp
    add_assoc add_comm add_zero_l add_opp_l).
  repeat rewrite (@opp_add A zero add opp
    add_assoc add_comm add_zero_l add_opp_l).
  repeat rewrite (@opp_involutive A zero add opp
    add_assoc add_comm add_zero_l add_opp_l).
  reflexivity.
Qed.

Lemma delta2_add_relation_local :
  forall (b c : @C2_A_action G A) (g h k : G),
    @delta2_A_action G A mul add opp act
      (add2_relation_local b c) g h k =
    add
      (@delta2_A_action G A mul add opp act b g h k)
      (@delta2_A_action G A mul add opp act c g h k).
Proof.
  intros b c g h k.
  unfold delta2_A_action, add2_relation_local.
  rewrite act_add.
  repeat rewrite (@opp_add A zero add opp
    add_assoc add_comm add_zero_l add_opp_l).
  change
    (r4_relation_local
      (add (act g (b h k)) (act g (c h k)))
      (add (opp (b (mul g h) k)) (opp (c (mul g h) k)))
      (add (b g (mul h k)) (c g (mul h k)))
      (add (opp (b g h)) (opp (c g h))) =
     add
      (r4_relation_local
        (act g (b h k))
        (opp (b (mul g h) k))
        (b g (mul h k))
        (opp (b g h)))
      (r4_relation_local
        (act g (c h k))
        (opp (c (mul g h) k))
        (c g (mul h k))
        (opp (c g h)))).
  apply r4_relation_pointwise_add.
Qed.

Definition relation_reflexive_local
  (R : @C3_A_action G A -> @C3_A_action G A -> Prop) : Prop :=
  forall a, R a a.

Definition relation_symmetric_local
  (R : @C3_A_action G A -> @C3_A_action G A -> Prop) : Prop :=
  forall a a', R a a' -> R a' a.

Definition relation_transitive_local
  (R : @C3_A_action G A -> @C3_A_action G A -> Prop) : Prop :=
  forall a a' a'', R a a' -> R a' a'' -> R a a''.

Definition relation_equivalence_laws_local
  (R : @C3_A_action G A -> @C3_A_action G A -> Prop) : Prop :=
  relation_reflexive_local R /\
  relation_symmetric_local R /\
  relation_transitive_local R.

Theorem full_gauge_equivalent3_reflexive :
  relation_reflexive_local
    (fun a a' =>
      @full_gauge_equivalent3 G A mul add opp act a a').
Proof.
  intro a.
  exists zero2_relation_local.
  intros g h k.
  unfold gauge_transform_A_action, add3_A_action.
  rewrite delta2_zero_relation_local.
  rewrite (@add_zero_r A zero add add_comm add_zero_l).
  reflexivity.
Qed.

Theorem full_gauge_equivalent3_symmetric :
  relation_symmetric_local
    (fun a a' =>
      @full_gauge_equivalent3 G A mul add opp act a a').
Proof.
  intros a a' [b Hb].
  exists (opp2_relation_local b).
  intros g h k.

  pose proof (Hb g h k) as Hpoint.
  unfold gauge_transform_A_action, add3_A_action in Hpoint.

  unfold gauge_transform_A_action, add3_A_action.
  rewrite delta2_opp_relation_local.
  rewrite Hpoint.
  rewrite add_assoc.
  rewrite (@add_opp_r A zero add opp add_comm add_opp_l).
  rewrite (@add_zero_r A zero add add_comm add_zero_l).
  reflexivity.
Qed.

Theorem full_gauge_equivalent3_transitive :
  relation_transitive_local
    (fun a a' =>
      @full_gauge_equivalent3 G A mul add opp act a a').
Proof.
  intros a a' a'' [b Hab] [c Hbc].
  exists (add2_relation_local b c).
  intros g h k.

  pose proof (Hab g h k) as Hab_point.
  pose proof (Hbc g h k) as Hbc_point.
  unfold gauge_transform_A_action, add3_A_action in Hab_point, Hbc_point.

  unfold gauge_transform_A_action, add3_A_action.
  rewrite delta2_add_relation_local.
  rewrite Hbc_point.
  rewrite Hab_point.
  apply add_assoc.
Qed.

Theorem normalized_gauge_equivalent3_reflexive :
  relation_reflexive_local
    (fun a a' =>
      @normalized_gauge_equivalent3
        G A e mul zero add opp act a a').
Proof.
  intro a.
  exists zero2_relation_local.
  split.

  - unfold normalized2_A_action, zero2_relation_local.
    split; intros g; reflexivity.

  - intros g h k.
    unfold gauge_transform_A_action, add3_A_action.
    rewrite delta2_zero_relation_local.
    rewrite (@add_zero_r A zero add add_comm add_zero_l).
    reflexivity.
Qed.

Theorem normalized_gauge_equivalent3_symmetric :
  relation_symmetric_local
    (fun a a' =>
      @normalized_gauge_equivalent3
        G A e mul zero add opp act a a').
Proof.
  intros a a' [b [Hbn Hb]].
  exists (opp2_relation_local b).
  split.

  - destruct Hbn as [Hleft Hright].
    unfold normalized2_A_action, opp2_relation_local.
    split.
    + intro g.
      rewrite Hleft.
      apply (@opp_zero A zero add opp
        add_assoc add_comm add_zero_l add_opp_l).
    + intro g.
      rewrite Hright.
      apply (@opp_zero A zero add opp
        add_assoc add_comm add_zero_l add_opp_l).

  - intros g h k.
    pose proof (Hb g h k) as Hpoint.
    unfold gauge_transform_A_action, add3_A_action in Hpoint.

    unfold gauge_transform_A_action, add3_A_action.
    rewrite delta2_opp_relation_local.
    rewrite Hpoint.
    rewrite add_assoc.
    rewrite (@add_opp_r A zero add opp add_comm add_opp_l).
    rewrite (@add_zero_r A zero add add_comm add_zero_l).
    reflexivity.
Qed.

Theorem normalized_gauge_equivalent3_transitive :
  relation_transitive_local
    (fun a a' =>
      @normalized_gauge_equivalent3
        G A e mul zero add opp act a a').
Proof.
  intros a a' a'' [b [Hbn Hab]] [c [Hcn Hbc]].
  exists (add2_relation_local b c).
  split.

  - destruct Hbn as [Hb_left Hb_right].
    destruct Hcn as [Hc_left Hc_right].
    unfold normalized2_A_action, add2_relation_local.
    split.
    + intro g.
      rewrite Hb_left.
      rewrite Hc_left.
      apply add_zero_l.
    + intro g.
      rewrite Hb_right.
      rewrite Hc_right.
      apply add_zero_l.

  - intros g h k.
    pose proof (Hab g h k) as Hab_point.
    pose proof (Hbc g h k) as Hbc_point.
    unfold gauge_transform_A_action, add3_A_action in Hab_point, Hbc_point.

    unfold gauge_transform_A_action, add3_A_action.
    rewrite delta2_add_relation_local.
    rewrite Hbc_point.
    rewrite Hab_point.
    apply add_assoc.
Qed.

Theorem h3_gauge_relations_equivalence_boundary :
  relation_equivalence_laws_local
    (fun a a' =>
      @full_gauge_equivalent3 G A mul add opp act a a')
  /\
  relation_equivalence_laws_local
    (fun a a' =>
      @normalized_gauge_equivalent3
        G A e mul zero add opp act a a').
Proof.
  split.

  - unfold relation_equivalence_laws_local.
    split.
    + exact full_gauge_equivalent3_reflexive.
    + split.
      * exact full_gauge_equivalent3_symmetric.
      * exact full_gauge_equivalent3_transitive.

  - unfold relation_equivalence_laws_local.
    split.
    + exact normalized_gauge_equivalent3_reflexive.
    + split.
      * exact normalized_gauge_equivalent3_symmetric.
      * exact normalized_gauge_equivalent3_transitive.
Qed.

End H3GaugeEquivalenceRelations.

Set Printing Implicit.
Check @full_gauge_equivalent3_reflexive.
Print Assumptions full_gauge_equivalent3_reflexive.
Check @full_gauge_equivalent3_symmetric.
Print Assumptions full_gauge_equivalent3_symmetric.
Check @full_gauge_equivalent3_transitive.
Print Assumptions full_gauge_equivalent3_transitive.
Check @normalized_gauge_equivalent3_reflexive.
Print Assumptions normalized_gauge_equivalent3_reflexive.
Check @normalized_gauge_equivalent3_symmetric.
Print Assumptions normalized_gauge_equivalent3_symmetric.
Check @normalized_gauge_equivalent3_transitive.
Print Assumptions normalized_gauge_equivalent3_transitive.
Check @h3_gauge_relations_equivalence_boundary.
Print Assumptions h3_gauge_relations_equivalence_boundary.
