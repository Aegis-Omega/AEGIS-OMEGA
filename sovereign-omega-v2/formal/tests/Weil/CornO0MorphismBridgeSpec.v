(*
  AEGIS Ω — CoRN IR -> O₀ A1c morphism + completion contract

  The reference carrier and the independent G/CR_complete presentation must
  both be kernel-checked. The completion identity is admissible only after
  both are shown to be limits of the same O₀ rational sequence and
  CR_cv_unique closes their equality.
*)

From Coq Require Import QArith.
From Coq Require Import Reals.Abstract.ConstructiveReals.
From Coq Require Import Reals.Abstract.ConstructiveLimits.
From Coq Require Import Reals.Abstract.ConstructiveRealsMorphisms.
Require Import CoRN.reals.R_morphism.
Require Import CoRN.reals.Q_dense.
Require Import CoRN.reals.fast.CRIR.
Require Import CoRN.reals.fast.CRArith.
Require Import CoRN.reals.fast.CRabs.
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

Check corn_fast_cauchy_lim_prop2_to_cv_a1c_v1.
Check corn_ir_G_fast_cauchy_lim_prop2_v1.
Check corn_ir_G_fast_cv_v1.
Check corn_ir_to_o0_reference_cv_v1.
Check corn_o0_G_seq_is_cauchy_v1.
Check corn_ir_to_o0_complete_sigma_v1.
Check corn_ir_to_o0_complete_v1.
Check corn_ir_to_o0_complete_cv_v1.
Check corn_ir_to_o0_completion_equivalence_v1.
Check corn_ir_to_o0_complete_preserves_rat_v1.
Check corn_ir_to_o0_complete_strict_v1.

(* Scope remains narrow: this contract proves no trig transport, explicit
   formula, global Weil positivity, or RH result. *)
