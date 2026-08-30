(*
  AEGIS Ω — constructive prime-trigonometry phase bridge v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  This file proves only the integer-frequency complement phase identities on
  CoRN's constructive IR carrier. It does not identify CoRN IR with AEGIS O0,
  does not prove sine/cosine commute with the O0 carrier morphism, and does not
  prove the prime-source derivative, explicit formula, Weil positivity, or RH.
*)

From Coq Require Import ZArith.
Require Import CoRN.transc.Pi.
Require Import CoRN.tactics.CornTac.

Theorem prime_diagonal_constructive_cos_phase_v1 :
  forall (r : IR) (n : nat),
    Cos (Two[*]zring (Z.of_nat n)[*]Pi[*]([1][-]r))
      [=]
    Cos (Two[*]zring (Z.of_nat n)[*]Pi[*]r).
Proof.
  intros r n.
  rstepl
    (Cos
      ([--](Two[*]zring (Z.of_nat n)[*]Pi[*]r)
       [+]zring (Z.of_nat n)[*](Two[*]Pi))).
  eapply eq_transitive_unfolded.
  - apply Cos_periodic_Z.
  - apply Cos_inv.
Qed.

Theorem prime_source_constructive_sin_phase_v1 :
  forall (r : IR) (n : nat),
    Sin (Two[*]zring (Z.of_nat n)[*]Pi[*]([1][-]r))
      [=]
    [--](Sin (Two[*]zring (Z.of_nat n)[*]Pi[*]r)).
Proof.
  intros r n.
  rstepl
    (Sin
      ([--](Two[*]zring (Z.of_nat n)[*]Pi[*]r)
       [+]zring (Z.of_nat n)[*](Two[*]Pi))).
  eapply eq_transitive_unfolded.
  - apply Sin_periodic_Z.
  - apply Sin_inv.
Qed.
