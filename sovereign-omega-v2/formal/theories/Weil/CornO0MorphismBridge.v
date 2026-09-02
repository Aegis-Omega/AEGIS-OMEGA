(*
  AEGIS Ω — CoRN IR -> O₀ morphism barriers (A1c)

  This production slice proves the two transport barriers against the actual
  CoRN 9.0.0 and Rocq ConstructiveReals interfaces:

    A1-RAT    : rational preservation
    A1-STRICT : strict-order preservation

  CoRN's IR is a CReals carrier, not itself a Rocq ConstructiveReals record.
  Therefore the proof route is the existing CoRN isomorphism IR -> fast CR,
  followed by Rocq's proof-oriented SlowConstructiveRealsMorphism from
  FastRealsConstructive to the AEGIS O₀ carrier.

  The separate theorem identifying a G-based CR_complete presentation with
  this reference carrier is deliberately NOT claimed here.
*)

Require Import AnalyticDefinitions.
From Coq Require Import QArith.
From Coq Require Import Reals.Abstract.ConstructiveReals.
From Coq Require Import Reals.Abstract.ConstructiveRealsMorphisms.
Require Import CoRN.reals.R_morphism.
Require Import CoRN.reals.Q_in_CReals.
Require Import CoRN.reals.fast.CRIR.
Require Import CoRN.reals.fast.CRArith.
Require Import CoRN.reals.stdlib.ConstructiveFastReals.

Local Open Scope CR_scope.

Definition corn_fast_to_o0_morphism_a1c_v1
  : @ConstructiveRealsMorphism FastRealsConstructive O0RealsV1 :=
  @SlowConstructiveRealsMorphism FastRealsConstructive O0RealsV1.

Definition corn_ir_to_o0_carrier_v1 (x : IR) : O0RealV1 :=
  CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x).

(* CoRN fast-real setoid equality is extensionally the equality induced by
   FastRealsConstructive's Set-valued strict order. Keep that conversion
   explicit so no definitional-equality accident becomes part of A1c. *)
Lemma corn_fast_eq_to_stdlib_eq_a1c_v1 :
  forall x y : CR,
    (x == y)%CR ->
    CReq FastRealsConstructive x y.
Proof.
  intros x y Hxy.
  exact (proj1 (CReq_nlt x y) Hxy).
Qed.

(* [CRle] is also a CoRN identifier after the fast-real imports.  State the
   stdlib order at FastRealsConstructive in its definitionally equal normal
   form instead of relying on an ambiguous unqualified projection name. *)
Lemma corn_fast_le_to_stdlib_le_a1c_v1 :
  forall x y : CR,
    (x <= y)%CR ->
    (CRltT y x -> False).
Proof.
  intros x y Hxy.
  exact (proj1 (CRle_not_lt x y) Hxy).
Qed.

Theorem corn_ir_to_o0_proper_v1 :
  forall x y : IR,
    x [=] y ->
    O0EqV1
      (corn_ir_to_o0_carrier_v1 x)
      (corn_ir_to_o0_carrier_v1 y).
Proof.
  intros x y Hxy.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  apply CRmorph_proper.
  apply corn_fast_eq_to_stdlib_eq_a1c_v1.
  exact (IRasCR_wd x y Hxy).
Qed.

(* A1-RAT. *)
Theorem corn_ir_to_o0_preserves_rat_v1 :
  forall q : Q,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (inj_Q IR q))
      (CR_of_Q O0RealsV1 q).
Proof.
  intros q.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact (IR_inj_Q_as_CR q).
  - change
      (CReq O0RealsV1
        (CRmorph corn_fast_to_o0_morphism_a1c_v1
          (CR_of_Q FastRealsConstructive q))
        (CR_of_Q O0RealsV1 q)).
    exact (CRmorph_rat corn_fast_to_o0_morphism_a1c_v1 q).
Qed.

(* A1-STRICT. The source strict-order fact is already part of CoRN's
   canonical IR <-> fast-CR isomorphism. *)
Theorem corn_ir_to_o0_strict_v1 :
  forall x y : IR,
    x [<] y ->
    O0LtV1
      (corn_ir_to_o0_carrier_v1 x)
      (corn_ir_to_o0_carrier_v1 y).
Proof.
  intros x y Hxy.
  unfold corn_ir_to_o0_carrier_v1, O0LtV1.
  apply CRmorph_increasing.
  exact
    (map_pres_less_unfolded
       IR CRasCReals
       (iso_map_rht CRasCReals IR CRIR_iso)
       x y Hxy).
Qed.

(* The remaining ring/order laws are corollaries of the two already-proved
   morphism layers; they are not additional assumptions. *)
Theorem corn_ir_to_o0_preserves_zero_v1 :
  O0EqV1
    (corn_ir_to_o0_carrier_v1 [0])
    O0ZeroV1.
Proof.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1, O0ZeroV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact IR_Zero_as_CR.
  - change
      (CReq O0RealsV1
        (CRmorph corn_fast_to_o0_morphism_a1c_v1
          (CR_of_Q FastRealsConstructive 0%Q))
        (CR_of_Q O0RealsV1 0%Q)).
    exact (CRmorph_zero corn_fast_to_o0_morphism_a1c_v1).
Qed.

Theorem corn_ir_to_o0_preserves_one_v1 :
  O0EqV1
    (corn_ir_to_o0_carrier_v1 [1])
    (CR_of_Q O0RealsV1 1%Q).
Proof.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact IR_One_as_CR.
  - change
      (CReq O0RealsV1
        (CRmorph corn_fast_to_o0_morphism_a1c_v1
          (CR_of_Q FastRealsConstructive 1%Q))
        (CR_of_Q O0RealsV1 1%Q)).
    exact (CRmorph_one corn_fast_to_o0_morphism_a1c_v1).
Qed.

Theorem corn_ir_to_o0_preserves_plus_v1 :
  forall x y : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (x [+] y))
      ((corn_ir_to_o0_carrier_v1 x + corn_ir_to_o0_carrier_v1 y)%ConstructiveReals).
Proof.
  intros x y.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact (IR_plus_as_CR x y).
  - exact
      (CRmorph_plus corn_fast_to_o0_morphism_a1c_v1
         (IRasCR x) (IRasCR y)).
Qed.

Theorem corn_ir_to_o0_preserves_mult_v1 :
  forall x y : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (x [*] y))
      ((corn_ir_to_o0_carrier_v1 x * corn_ir_to_o0_carrier_v1 y)%ConstructiveReals).
Proof.
  intros x y.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact (IR_mult_as_CR x y).
  - exact
      (CRmorph_mult corn_fast_to_o0_morphism_a1c_v1
         (IRasCR x) (IRasCR y)).
Qed.

Theorem corn_ir_to_o0_preserves_le_v1 :
  forall x y : IR,
    x [<=] y ->
    O0LeV1
      (corn_ir_to_o0_carrier_v1 x)
      (corn_ir_to_o0_carrier_v1 y).
Proof.
  intros x y Hxy.
  unfold corn_ir_to_o0_carrier_v1, O0LeV1.
  apply CRmorph_le.
  change (CRltT (IRasCR y) (IRasCR x) -> False).
  exact
    (corn_fast_le_to_stdlib_le_a1c_v1
       (IRasCR x) (IRasCR y)
       (proj1 (IR_leEq_as_CR x y) Hxy)).
Qed.
