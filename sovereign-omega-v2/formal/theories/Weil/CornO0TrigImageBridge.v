(*
  AEGIS Ω — CoRN -> O₀ trig image bridge v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  This module transports the already machine-bound CoRN IR complement-phase
  equalities through the proper CoRN -> O₀ carrier map. It proves only equality
  of images under [corn_ir_to_o0_carrier_v1].

  It does NOT define native O₀ sine/cosine/pi, prove native O₀ trigonometric
  commutation, derivative transport, the Guinand-Weil explicit formula,
  concrete GlobalizationReadyV1, global Weil positivity, the Weil criterion,
  or the Riemann Hypothesis.
*)

From Coq Require Import ZArith.
Require Import CoRN.transc.Pi.
Require Import AnalyticDefinitions CornO0MorphismBridge PrimeTrigConstructive.

Theorem corn_o0_cos_phase_image_Z_v1 :
  forall (r : IR) (k : Z),
    O0EqV1
      (corn_ir_to_o0_carrier_v1
        (Cos (Two[*]zring k[*]Pi[*]([1][-]r))))
      (corn_ir_to_o0_carrier_v1
        (Cos (Two[*]zring k[*]Pi[*]r))).
Proof.
  intros r k.
  apply corn_ir_to_o0_proper_v1.
  exact (prime_diagonal_constructive_cos_phase_Z_v1 r k).
Qed.

Theorem corn_o0_sin_phase_image_Z_v1 :
  forall (r : IR) (k : Z),
    O0EqV1
      (corn_ir_to_o0_carrier_v1
        (Sin (Two[*]zring k[*]Pi[*]([1][-]r))))
      (corn_ir_to_o0_carrier_v1
        ([--](Sin (Two[*]zring k[*]Pi[*]r)))).
Proof.
  intros r k.
  apply corn_ir_to_o0_proper_v1.
  exact (prime_source_constructive_sin_phase_Z_v1 r k).
Qed.
