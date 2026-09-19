Require Import CStarAbelianGroupCohomology.
Require Import CStarV07H3Normalization.
Require Import CStarV08H3NormalizationInjective.

(**
  CSTAR v0.9: degree-3 normalization class-equivalence boundary.

  Scope:
  - every declared full degree-3 cocycle has a normalized cocycle
    representative in its full gauge class;
  - for normalized degree-3 representatives, full gauge equivalence is
    equivalent to gauge equivalence witnessed by a normalized degree-2
    cochain;
  - this is a degree-3 class-level normalization result only;
  - no chain-complex quasi-isomorphism theorem is claimed;
  - authority_effect = NONE.
*)

Section H3NormalizationClassEquivalence.

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

Definition normalized_three_cocycle_candidate
  (a : @C3_A_action G A) : Prop :=
  @normalized3_A_action G A e zero a /\
  @three_cocycle_A_action G A mul zero add opp act a.

Definition full_gauge_equivalent3
  (a a' : @C3_A_action G A) : Prop :=
  exists b : @C2_A_action G A,
    forall g h k : G,
      a' g h k =
      @gauge_transform_A_action G A mul add opp act a b g h k.

Definition normalized_gauge_equivalent3
  (a a' : @C3_A_action G A) : Prop :=
  exists b : @C2_A_action G A,
    @normalized2_A_action G A e zero b /\
    forall g h k : G,
      a' g h k =
      @gauge_transform_A_action G A mul add opp act a b g h k.

Theorem h3_normalization_surjective_on_class_candidates :
  forall a : @C3_A_action G A,
    @three_cocycle_A_action G A mul zero add opp act a ->
    exists an : @C3_A_action G A,
      normalized_three_cocycle_candidate an /\
      full_gauge_equivalent3 a an.
Proof.
  intros a Ha.

  assert (Hex :
    exists b : @C2_A_action G A,
      @normalized3_A_action G A e zero
        (@gauge_transform_A_action G A mul add opp act a b)).
  {
    eapply h3_normalization_surjective_abelian_action.
    exact Ha.
  }

  destruct Hex as [b Hnorm].
  exists (@gauge_transform_A_action G A mul add opp act a b).
  split.

  - split.
    + exact Hnorm.
    + eapply gauge_preserves_three_cocycle_abelian_action.
      exact Ha.

  - exists b.
    intros g h k.
    reflexivity.
Qed.

Theorem full_iff_normalized_gauge_on_normalized3 :
  forall (a a' : @C3_A_action G A),
    @normalized3_A_action G A e zero a ->
    @normalized3_A_action G A e zero a' ->
    (full_gauge_equivalent3 a a' <->
     normalized_gauge_equivalent3 a a').
Proof.
  intros a a' Ha Ha'.
  split.

  - intros [b Hb].

    destruct Ha' as [Ha'L [Ha'M Ha'R]].

    assert (Hg :
      @normalized3_A_action G A e zero
        (@gauge_transform_A_action G A mul add opp act a b)).
    {
      unfold normalized3_A_action.
      split.
      - intros g h.
        rewrite <- (Hb e g h).
        exact (Ha'L g h).
      - split.
        + intros g h.
          rewrite <- (Hb g e h).
          exact (Ha'M g h).
        + intros g h.
          rewrite <- (Hb g h e).
          exact (Ha'R g h).
    }

    assert (Hex :
      exists bn : @C2_A_action G A,
        @normalized2_A_action G A e zero bn /\
        forall g h k : G,
          @gauge_transform_A_action G A mul add opp act a bn g h k =
          @gauge_transform_A_action G A mul add opp act a b g h k).
    {
      eapply normalized_gauge_equivalence_has_normalized_witness_abelian_action.
      - exact Ha.
      - exact Hg.
    }

    destruct Hex as [bn [Hbn Hsame]].
    exists bn.
    split.
    + exact Hbn.
    + intros g h k.
      rewrite (Hb g h k).
      symmetry.
      apply Hsame.

  - intros [b [Hbn Hb]].
    exists b.
    exact Hb.
Qed.

Theorem h3_normalization_class_equivalence_boundary :
  (forall a : @C3_A_action G A,
    @three_cocycle_A_action G A mul zero add opp act a ->
    exists an : @C3_A_action G A,
      normalized_three_cocycle_candidate an /\
      full_gauge_equivalent3 a an)
  /\
  (forall (a a' : @C3_A_action G A),
    normalized_three_cocycle_candidate a ->
    normalized_three_cocycle_candidate a' ->
    (full_gauge_equivalent3 a a' <->
     normalized_gauge_equivalent3 a a')).
Proof.
  split.

  - exact h3_normalization_surjective_on_class_candidates.

  - intros a a' [Ha_norm Ha_coc] [Ha'_norm Ha'_coc].
    apply full_iff_normalized_gauge_on_normalized3.
    + exact Ha_norm.
    + exact Ha'_norm.
Qed.

End H3NormalizationClassEquivalence.

Set Printing Implicit.
Check @h3_normalization_surjective_on_class_candidates.
Print Assumptions h3_normalization_surjective_on_class_candidates.
Check @full_iff_normalized_gauge_on_normalized3.
Print Assumptions full_iff_normalized_gauge_on_normalized3.
Check @h3_normalization_class_equivalence_boundary.
Print Assumptions h3_normalization_class_equivalence_boundary.
