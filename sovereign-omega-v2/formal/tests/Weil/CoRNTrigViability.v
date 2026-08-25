(*
  AEGIS Ω — CoRN constructive-trigonometry T0 viability probe

  DIAGNOSTIC_ONLY.

  This file measures whether pinned CoRN can load next to the exact AEGIS O0
  production carrier, whether direct carrier reuse is definitionally available,
  and whether the stdlib ConstructiveReals morphism layer can construct an
  explicit proof-only bridge.  It grants no production authority and proves no
  Weil/RH claim.
*)

Require Import AnalyticDefinitions.
From Coq Require Import Reals.Abstract.ConstructiveRealsMorphisms.
Require Import CoRN.reals.fast.CRsin.
Require Import CoRN.reals.fast.CRcos.
Require Import CoRN.reals.fast.CRpi.
Require Import CoRN.transc.SinCos.
Require Import CoRN.reals.stdlib.ConstructiveFastReals.
Require Import CoRN.reals.stdlib.ConstructiveCauchyIntegral.

(* Concrete CoRN transcendental surface. *)
Check CR.
Check sin.
Check cos.
Check CRpi.
Check sin_correct.
Check cos_correct.
Check Derivative_Sin.
Check Derivative_Cos.

(* AEGIS production carrier remains the stdlib constructive Cauchy real.
   [AnalyticDefinitions] already binds [O0RealsV1 := CRealConstructive]; the
   probe deliberately uses that public nominal binding rather than depending
   on the upstream constructor name being re-exported into this namespace. *)
Check O0RealsV1.
Check O0RealV1.
Check O0ZeroV1.

(* CoRN's fast CR is a separate concrete carrier. Silent definitional reuse on
   O0RealV1 must fail. *)
Fail Check (sin O0ZeroV1).
Fail Check (cos O0ZeroV1).

(* CoRN proves that its fast CR implements Coq's ConstructiveReals interface. *)
Check FastRealsConstructive.
Check IntervalPartition.

(* The stdlib morphism layer constructs a canonical proof-oriented map between
   arbitrary ConstructiveReals structures. Bind both directions explicitly. *)
Definition corn_fast_to_o0_morphism_v1
  : @ConstructiveRealsMorphism FastRealsConstructive O0RealsV1 :=
  @SlowConstructiveRealsMorphism FastRealsConstructive O0RealsV1.

Definition o0_to_corn_fast_morphism_v1
  : @ConstructiveRealsMorphism O0RealsV1 FastRealsConstructive :=
  @SlowConstructiveRealsMorphism O0RealsV1 FastRealsConstructive.

Definition corn_fast_to_o0_v1 (x : CR) : O0RealV1 :=
  CRmorph corn_fast_to_o0_morphism_v1 x.

Definition o0_to_corn_fast_v1 (x : O0RealV1) : CR :=
  CRmorph o0_to_corn_fast_morphism_v1 x.

Theorem corn_o0_corn_roundtrip_v1 :
  forall x : CR,
    CReq FastRealsConstructive
      (o0_to_corn_fast_v1 (corn_fast_to_o0_v1 x)) x.
Proof.
  intros x.
  exact (@Endomorph_id FastRealsConstructive
    (CRmorph_compose corn_fast_to_o0_morphism_v1
                     o0_to_corn_fast_morphism_v1) x).
Qed.

Theorem o0_corn_o0_roundtrip_v1 :
  forall x : O0RealV1,
    CReq O0RealsV1
      (corn_fast_to_o0_v1 (o0_to_corn_fast_v1 x)) x.
Proof.
  intros x.
  exact (@Endomorph_id O0RealsV1
    (CRmorph_compose o0_to_corn_fast_morphism_v1
                     corn_fast_to_o0_morphism_v1) x).
Qed.

(* This bridge is only carrier/order/ring interoperability. Nothing here says
   that CoRN's concrete [sin]/[cos] commute with the bridge; that is a separate
   theorem obligation and remains unbound. *)
