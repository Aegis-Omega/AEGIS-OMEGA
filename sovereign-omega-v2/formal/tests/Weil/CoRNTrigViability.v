(*
  AEGIS Ω — CoRN constructive-trigonometry T0 viability probe

  DIAGNOSTIC_ONLY.

  This file measures only whether the pinned CoRN surface can be loaded next to
  the exact AEGIS O0 production carrier and whether the obvious direct carrier
  reuse route is definitionally available.  It grants no production authority
  and proves no Weil/RH claim.
*)

Require Import AnalyticDefinitions.
Require Import CoRN.reals.fast.CRsin.
Require Import CoRN.reals.fast.CRcos.
Require Import CoRN.reals.fast.CRpi.
Require Import CoRN.transc.SinCos.
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

(* AEGIS production carrier remains the stdlib constructive Cauchy real. *)
Check O0RealsV1.
Check O0RealV1.
Check O0ZeroV1.
Check CRealConstructive.

(* CoRN's fast CR and AEGIS O0RealV1 are not a definitionally identical
   carrier at this surface.  Any interoperability path must therefore be an
   explicit, separately verified map/isomorphism rather than silent reuse. *)
Fail Check (sin O0ZeroV1).
Fail Check (cos O0ZeroV1).

(* CoRN also contains modules parameterized over Coq's ConstructiveReals
   interface.  This confirms shared interface vocabulary only; it is not a
   CR <-> O0RealV1 bridge. *)
Check IntervalPartition.
