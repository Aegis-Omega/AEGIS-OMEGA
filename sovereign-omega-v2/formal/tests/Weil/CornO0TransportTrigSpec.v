(*
  AEGIS Ω — RED/GREEN contract for transport-defined O₀ trigonometry.

  This contract requires a genuine two-way carrier bridge before defining
  transport trigonometry, and requires the transported functions to respect
  O₀ setoid equality. It does NOT assert agreement with an independently
  chosen native O₀ sine/cosine implementation, derivative transport, the
  Guinand–Weil explicit formula, global Weil positivity, the Weil criterion,
  or RH.
*)

From Coq Require Import Reals.Abstract.ConstructiveReals.
Require Import CoRN.transc.Pi.
Require Import AnalyticDefinitions CornO0MorphismBridge PrimeTrigConstructive.
Require Import CornO0TransportTrig.

Definition o0_to_corn_ir_proper_contract_v1 :
  forall y z : O0RealV1,
    O0EqV1 y z ->
    o0_to_corn_ir_carrier_v1 y [=] o0_to_corn_ir_carrier_v1 z :=
  o0_to_corn_ir_proper_v1.

Definition corn_o0_roundtrip_ir_contract_v1 :
  forall x : IR,
    o0_to_corn_ir_carrier_v1 (corn_ir_to_o0_carrier_v1 x) [=] x :=
  corn_o0_roundtrip_ir_v1.

Definition corn_o0_roundtrip_o0_contract_v1 :
  forall y : O0RealV1,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (o0_to_corn_ir_carrier_v1 y))
      y :=
  corn_o0_roundtrip_o0_v1.

Definition o0_sin_transport_proper_contract_v1 :
  forall y z : O0RealV1,
    O0EqV1 y z ->
    O0EqV1 (O0SinTransportV1 y) (O0SinTransportV1 z) :=
  o0_sin_transport_proper_v1.

Definition o0_cos_transport_proper_contract_v1 :
  forall y z : O0RealV1,
    O0EqV1 y z ->
    O0EqV1 (O0CosTransportV1 y) (O0CosTransportV1 z) :=
  o0_cos_transport_proper_v1.

Definition corn_o0_sin_transport_commutes_contract_v1 :
  forall x : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (Sin x))
      (O0SinTransportV1 (corn_ir_to_o0_carrier_v1 x)) :=
  corn_o0_sin_transport_commutes_v1.

Definition corn_o0_cos_transport_commutes_contract_v1 :
  forall x : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (Cos x))
      (O0CosTransportV1 (corn_ir_to_o0_carrier_v1 x)) :=
  corn_o0_cos_transport_commutes_v1.
