(*
  AEGIS Ω — RED/GREEN contract for the CoRN -> O₀ trig image bridge.

  This contract intentionally targets only image-of-CoRN phase identities.
  It does NOT assert native O₀ sine/cosine commutation, derivative transport,
  the Guinand–Weil explicit formula, global Weil positivity, or RH.
*)
From Coq Require Import ZArith.
Require Import CoRN.transc.Pi.
Require Import AnalyticDefinitions CornO0MorphismBridge PrimeTrigConstructive.
Require Import CornO0TrigImageBridge.

Definition corn_o0_cos_phase_image_Z_contract_v1 :
  forall (r : IR) (k : Z),
    O0EqV1
      (corn_ir_to_o0_carrier_v1
        (Cos (Two[*]zring k[*]Pi[*]([1][-]r))))
      (corn_ir_to_o0_carrier_v1
        (Cos (Two[*]zring k[*]Pi[*]r))) :=
  corn_o0_cos_phase_image_Z_v1.

Definition corn_o0_sin_phase_image_Z_contract_v1 :
  forall (r : IR) (k : Z),
    O0EqV1
      (corn_ir_to_o0_carrier_v1
        (Sin (Two[*]zring k[*]Pi[*]([1][-]r))))
      (corn_ir_to_o0_carrier_v1
        ([--](Sin (Two[*]zring k[*]Pi[*]r)))) :=
  corn_o0_sin_phase_image_Z_v1.
