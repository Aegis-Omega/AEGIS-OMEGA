(*
  AEGIS Ω — transport-defined O₀ trigonometry v1

  FORMAL_MATH_EVIDENCE_ONLY.

  This module constructs a reverse O₀ -> CoRN IR carrier map through the
  canonical constructive-real morphism O₀ -> CoRN fast CR followed by CoRN's
  CR -> IR isomorphism. It proves both carrier round trips up to the relevant
  setoid equalities, then defines O₀ sine/cosine by transport through that
  proved equivalence.

  Scope boundary:
  - this DOES prove commutation for the transport-defined O₀ trig functions;
  - this does NOT prove agreement with an independently chosen native O₀ trig
    implementation;
  - it does NOT transport derivatives, establish the Guinand-Weil explicit
    formula, prove global Weil positivity, machine-bind the Weil criterion,
    or prove RH.

  No Axiom, Parameter, or Admitted is introduced.
*)

From Coq Require Import Reals.Abstract.ConstructiveReals.
From Coq Require Import Reals.Abstract.ConstructiveRealsMorphisms.
Require Import CoRN.reals.fast.CRIR.
Require Import CoRN.reals.stdlib.ConstructiveFastReals.
Require Import CoRN.transc.Pi.
Require Import AnalyticDefinitions CornO0MorphismBridge.

Definition o0_to_corn_fast_morphism_v1
  : @ConstructiveRealsMorphism O0RealsV1 FastRealsConstructive :=
  @SlowConstructiveRealsMorphism O0RealsV1 FastRealsConstructive.

Definition o0_to_corn_ir_carrier_v1 (y : O0RealV1) : IR :=
  CRasIR (CRmorph o0_to_corn_fast_morphism_v1 y).

Theorem o0_to_corn_ir_proper_v1 :
  forall y z : O0RealV1,
    O0EqV1 y z ->
    o0_to_corn_ir_carrier_v1 y [=] o0_to_corn_ir_carrier_v1 z.
Proof.
  intros y z Hyz.
  unfold o0_to_corn_ir_carrier_v1.
  apply CRasIR_wd.
  apply (proj2 (CReq_nlt _ _)).
  apply CRmorph_proper.
  exact Hyz.
Qed.

Theorem corn_o0_roundtrip_ir_v1 :
  forall x : IR,
    o0_to_corn_ir_carrier_v1 (corn_ir_to_o0_carrier_v1 x) [=] x.
Proof.
  intro x.
  unfold o0_to_corn_ir_carrier_v1, corn_ir_to_o0_carrier_v1.
  eapply eq_transitive_unfolded.
  - apply CRasIR_wd.
    apply (proj2 (CReq_nlt _ _)).
    exact
      (Endomorph_id
         (CRmorph_compose
            corn_fast_to_o0_morphism_a1c_v1
            o0_to_corn_fast_morphism_v1)
         (IRasCR x)).
  - apply IRasCRasIR_id.
Qed.

Theorem corn_o0_roundtrip_o0_v1 :
  forall y : O0RealV1,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (o0_to_corn_ir_carrier_v1 y))
      y.
Proof.
  intro y.
  unfold o0_to_corn_ir_carrier_v1, corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    apply CRasIRasCR_id.
  - exact
      (Endomorph_id
         (CRmorph_compose
            o0_to_corn_fast_morphism_v1
            corn_fast_to_o0_morphism_a1c_v1)
         y).
Qed.

Definition O0SinTransportV1 (y : O0RealV1) : O0RealV1 :=
  corn_ir_to_o0_carrier_v1 (Sin (o0_to_corn_ir_carrier_v1 y)).

Definition O0CosTransportV1 (y : O0RealV1) : O0RealV1 :=
  corn_ir_to_o0_carrier_v1 (Cos (o0_to_corn_ir_carrier_v1 y)).

Theorem o0_sin_transport_proper_v1 :
  forall y z : O0RealV1,
    O0EqV1 y z ->
    O0EqV1 (O0SinTransportV1 y) (O0SinTransportV1 z).
Proof.
  intros y z Hyz.
  unfold O0SinTransportV1.
  apply corn_ir_to_o0_proper_v1.
  apply Sin_wd.
  apply o0_to_corn_ir_proper_v1.
  exact Hyz.
Qed.

Theorem o0_cos_transport_proper_v1 :
  forall y z : O0RealV1,
    O0EqV1 y z ->
    O0EqV1 (O0CosTransportV1 y) (O0CosTransportV1 z).
Proof.
  intros y z Hyz.
  unfold O0CosTransportV1.
  apply corn_ir_to_o0_proper_v1.
  apply Cos_wd.
  apply o0_to_corn_ir_proper_v1.
  exact Hyz.
Qed.

Theorem corn_o0_sin_transport_commutes_v1 :
  forall x : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (Sin x))
      (O0SinTransportV1 (corn_ir_to_o0_carrier_v1 x)).
Proof.
  intro x.
  unfold O0SinTransportV1.
  apply corn_ir_to_o0_proper_v1.
  apply Sin_wd.
  apply eq_symmetric_unfolded.
  apply corn_o0_roundtrip_ir_v1.
Qed.

Theorem corn_o0_cos_transport_commutes_v1 :
  forall x : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (Cos x))
      (O0CosTransportV1 (corn_ir_to_o0_carrier_v1 x)).
Proof.
  intro x.
  unfold O0CosTransportV1.
  apply corn_ir_to_o0_proper_v1.
  apply Cos_wd.
  apply eq_symmetric_unfolded.
  apply corn_o0_roundtrip_ir_v1.
Qed.
