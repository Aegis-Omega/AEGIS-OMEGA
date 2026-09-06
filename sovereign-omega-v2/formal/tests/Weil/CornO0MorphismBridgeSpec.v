(*
  AEGIS Ω — CoRN IR -> O₀ A1c morphism contract

  RED-first specification. The production module is intentionally absent at
  preregistration. A GREEN implementation must establish the two load-bearing
  barriers without Axiom/Parameter/Admitted:

    A1-RAT    rational preservation
    A1-STRICT strict-order preservation

  Algebraic/order corollaries are checked only after those barriers are bound.
  The separate G/CR_complete extensional-identification obligation is not
  silently promoted by this contract.
*)

From Coq Require Import QArith.
From Coq Require Import Reals.Abstract.ConstructiveReals.
From Coq Require Import Reals.Abstract.ConstructiveRealsMorphisms.
Require Import CoRN.reals.fast.CRIR.
Require Import CoRN.reals.stdlib.ConstructiveFastReals.
Require Import CornO0MorphismBridge.

Check corn_fast_to_o0_morphism_a1c_v1.
Check corn_ir_to_o0_carrier_v1.

Check corn_ir_to_o0_preserves_rat_v1.
Check corn_ir_to_o0_strict_v1.

Check corn_ir_to_o0_preserves_zero_v1.
Check corn_ir_to_o0_preserves_one_v1.
Check corn_ir_to_o0_preserves_plus_v1.
Check corn_ir_to_o0_preserves_mult_v1.
Check corn_ir_to_o0_preserves_le_v1.

(* The completion-defined carrier is deliberately a distinct proof obligation.
   A1c must not claim it until the CoRN G-sequence is proved to converge to the
   same O₀ value and CR_cv_unique closes the identity. *)
Fail Check corn_ir_to_o0_completion_equivalence_v1.
