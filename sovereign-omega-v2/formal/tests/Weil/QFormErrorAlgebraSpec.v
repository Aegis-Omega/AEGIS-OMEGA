(* AEGIS Ω — preregistered QForm quotient-stability algebra specification. *)

From Coq Require Import QArith.
Require Import QFormErrorAlgebra.

Check normalized_quotient_cross_error_v1.
Check normalized_quotient_stability_v1.

Goal
  normalized_quotient_cross_error_v1
    (3#1)%Q (31#10)%Q (2#1)%Q (21#10)%Q
    (1#10)%Q (1#10)%Q (2#1)%Q.
Proof.
  vm_compute.
  repeat split; reflexivity || discriminate || auto with qarith.
Qed.
