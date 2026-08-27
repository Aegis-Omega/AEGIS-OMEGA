(*
  AEGIS Ω — preregistered O0 constructive-real quotient-stability spec.

  TDD contract: this specification is committed before QFormErrorO0.v exists.
  It requires actual theorem proofs over the production O0 carrier; it must not
  be satisfied by the exact-rational theorem alone.
*)

Require Import AnalyticDefinitions.
Require Import QFormErrorO0.
From Coq Require Import Reals.Abstract.ConstructiveAbs.

Check o0_normalized_quotient_cross_error_sound_v1.
Check o0_normalized_quotient_stability_sound_v1.

(* Concrete embedded-rational fixture on the production O0 carrier.  This is
   deliberately elementary: its role is to force the theorem to instantiate on
   O0RealsV1 rather than merely exposing a generic declaration. *)
Definition o0_q (q : Q) : O0RealV1 := CR_of_Q O0RealsV1 q.

Lemma o0_embedded_self_difference_zero_v1 :
  forall q : Q,
    O0EqV1 (O0MinusV1 (o0_q q) (o0_q q)) O0ZeroV1.
Proof.
  intros q.
  unfold O0EqV1, O0MinusV1, O0OppV1, O0ZeroV1, o0_q.
  apply CRplus_opp_r.
Qed.

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
  - apply CRltForget, CR_of_Q_pos. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - apply CR_of_Q_le. reflexivity.
  - rewrite (o0_embedded_self_difference_zero_v1 2).
    rewrite CRabs_right.
    + apply CRle_refl.
    + apply CRle_refl.
  - rewrite (o0_embedded_self_difference_zero_v1 3).
    rewrite CRabs_right.
    + apply CRle_refl.
    + apply CRle_refl.
Qed.
