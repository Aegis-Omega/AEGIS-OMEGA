(*
  AEGIS Ω — preregistered O0 constructive-real quotient-stability spec.

  TDD contract: this specification is committed before QFormErrorO0.v exists.
  It requires actual theorem proofs over the production O0 carrier; it must not
  be satisfied by the exact-rational theorem alone.
*)

Require Import AnalyticDefinitions.
Require Import QFormErrorO0.

Check o0_normalized_quotient_cross_error_sound_v1.
Check o0_normalized_quotient_stability_sound_v1.

(* Concrete embedded-rational fixture on the production O0 carrier.  This is
   deliberately elementary: its role is to force the theorem to instantiate on
   O0RealsV1 rather than merely exposing a generic declaration. *)
Definition o0_q (q : Q) : O0RealV1 := CR_of_Q O0RealsV1 q.

Example o0_quotient_fixture_v1 :
  o0_normalized_quotient_stability_v1
    (o0_q 2) (o0_q 2) (o0_q 3) (o0_q 3)
    (o0_q 0) (o0_q 0) (o0_q 1).
Proof.
  apply o0_normalized_quotient_stability_sound_v1.
  repeat split.
  - apply CR_of_Q_le. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - apply CR_of_Q_pos. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - rewrite CR_of_Q_minus, CR_of_Q_zero, CRabs_right.
    + apply CRle_refl.
    + apply CRle_refl.
  - rewrite CR_of_Q_minus, CR_of_Q_zero, CRabs_right.
    + apply CRle_refl.
    + apply CRle_refl.
Qed.
