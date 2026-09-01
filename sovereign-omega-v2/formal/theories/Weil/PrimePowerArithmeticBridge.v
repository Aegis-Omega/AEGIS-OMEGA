(**
  AEGIS Ω — proof-carrying prime-power arithmetic bridge v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  This module binds an explicitly supplied certificate to a base [p] that
  satisfies the local [prime_nat_v1] predicate, a positive exponent [k], and
  [q = p^k].  It then constructs canonical CoRN-IR values for log(p), log(q),
  and sqrt(q), proves their power/log/root identities, and derives the finite
  source family.

  It does not implement total factorization, total von Mangoldt evaluation,
  canonical prime-power enumeration, a bridge to the standard-library prime
  predicate, CoRN-to-O0 transport, the Guinand-Weil explicit formula, global
  Weil positivity, or RH.
*)

From Coq Require Import Arith.PeanoNat.

Require Import CoRN.reals.NRootIR.
Require Import CoRN.transc.Exponential.
Require Import CoRN.ftc.MoreFunctions.
Require Import PrimePowerWeightBridge.

Definition divides_nat_v1 (d n : nat) : Prop :=
  exists witness : nat, n = d * witness.

Definition prime_nat_v1 (p : nat) : Prop :=
  1 < p /\
  forall d : nat, divides_nat_v1 d p -> d = 1 \/ d = p.

Record prime_power_certificate_v1 : Type := {
  certified_prime_base_v1 : nat;
  certified_prime_exponent_v1 : nat;
  certified_prime_power_value_v1 : nat;
  certified_prime_base_is_prime_v1 :
    prime_nat_v1 certified_prime_base_v1;
  certified_prime_exponent_positive_v1 :
    0 < certified_prime_exponent_v1;
  certified_prime_power_nat_identity_v1 :
    certified_prime_power_value_v1 =
      Nat.pow certified_prime_base_v1 certified_prime_exponent_v1;
  certified_prime_power_value_positive_nat_v1 :
    0 < certified_prime_power_value_v1
}.

Lemma certified_prime_base_positive_nat_v1 :
  forall certificate : prime_power_certificate_v1,
    0 < certified_prime_base_v1 certificate.
Proof.
  intros certificate.
  destruct (certified_prime_base_is_prime_v1 certificate)
    as [H_base_gt_one _].
  eapply Nat.lt_trans.
  - exact (Nat.lt_0_succ 0).
  - exact H_base_gt_one.
Qed.

Definition certified_prime_base_ir_v1
    (certificate : prime_power_certificate_v1) : IR :=
  nring (certified_prime_base_v1 certificate).

Definition certified_prime_power_value_ir_v1
    (certificate : prime_power_certificate_v1) : IR :=
  nring (certified_prime_power_value_v1 certificate).

Lemma certified_prime_base_ir_positive_v1 :
  forall certificate : prime_power_certificate_v1,
    [0] [<] certified_prime_base_ir_v1 certificate.
Proof.
  intros certificate.
  unfold certified_prime_base_ir_v1.
  apply nring_pos.
  apply certified_prime_base_positive_nat_v1.
Qed.

Lemma certified_prime_power_value_ir_positive_v1 :
  forall certificate : prime_power_certificate_v1,
    [0] [<] certified_prime_power_value_ir_v1 certificate.
Proof.
  intros certificate.
  unfold certified_prime_power_value_ir_v1.
  apply nring_pos.
  apply certified_prime_power_value_positive_nat_v1.
Qed.

Lemma nring_nat_power_identity_v1 :
  forall p k : nat,
    (nring (Nat.pow p k) : IR) [=] (nring p : IR)[^]k.
Proof.
  intros p k.
  induction k as [| k IH].
  - simpl. algebra.
  - simpl.
    astepl
      ((nring (Nat.pow p k) : IR) [*] (nring p : IR)).
    apply mult_wdl.
    exact IH.
Qed.

Theorem certified_prime_power_ir_power_identity_v1 :
  forall certificate : prime_power_certificate_v1,
    certified_prime_power_value_ir_v1 certificate
    [=]
    (certified_prime_base_ir_v1 certificate)
      [^](certified_prime_exponent_v1 certificate).
Proof.
  intros certificate.
  unfold certified_prime_power_value_ir_v1,
    certified_prime_base_ir_v1.
  rewrite (certified_prime_power_nat_identity_v1 certificate).
  apply nring_nat_power_identity_v1.
Qed.

Definition certified_prime_log_v1
    (certificate : prime_power_certificate_v1) : IR :=
  Log
    (certified_prime_base_ir_v1 certificate)
    (certified_prime_base_ir_positive_v1 certificate).

Definition certified_prime_power_log_v1
    (certificate : prime_power_certificate_v1) : IR :=
  Log
    (certified_prime_power_value_ir_v1 certificate)
    (certified_prime_power_value_ir_positive_v1 certificate).

Theorem certified_prime_power_log_identity_v1 :
  forall certificate : prime_power_certificate_v1,
    certified_prime_power_log_v1 certificate
    [=]
    (nring (certified_prime_exponent_v1 certificate) : IR)
      [*] certified_prime_log_v1 certificate.
Proof.
  intros certificate.
  assert (H_power_pos :
    [0] [<]
      (certified_prime_base_ir_v1 certificate)
        [^](certified_prime_exponent_v1 certificate)).
  {
    apply nexp_resp_pos.
    apply certified_prime_base_ir_positive_v1.
  }
  unfold certified_prime_power_log_v1, certified_prime_log_v1.
  apply eq_transitive_unfolded with
    (Log
      ((certified_prime_base_ir_v1 certificate)
        [^](certified_prime_exponent_v1 certificate))
      H_power_pos).
  - apply Log_wd.
    apply certified_prime_power_ir_power_identity_v1.
  - apply Log_nexp.
Qed.

Definition certified_prime_power_sqrt_v1
    (certificate : prime_power_certificate_v1) : IR :=
  sqrt
    (certified_prime_power_value_ir_v1 certificate)
    (less_leEq _ _ _
      (certified_prime_power_value_ir_positive_v1 certificate)).

Lemma certified_prime_power_sqrt_positive_v1 :
  forall certificate : prime_power_certificate_v1,
    [0] [<] certified_prime_power_sqrt_v1 certificate.
Proof.
  intros certificate.
  unfold certified_prime_power_sqrt_v1, sqrt.
  apply NRoot_pos.
  apply certified_prime_power_value_ir_positive_v1.
Qed.

Theorem certified_prime_power_sqrt_square_identity_v1 :
  forall certificate : prime_power_certificate_v1,
    (certified_prime_power_sqrt_v1 certificate)[^]2
    [=]
    certified_prime_power_value_ir_v1 certificate.
Proof.
  intros certificate.
  unfold certified_prime_power_sqrt_v1.
  apply sqrt_sqr.
Qed.

Definition certified_prime_power_source_term_v1
    (L : IR) (H_L_pos : [0] [<] L)
    (certificate : prime_power_certificate_v1) : PartIR :=
  prime_source_term_v1
    L H_L_pos
    (certified_prime_log_v1 certificate)
    (certified_prime_power_sqrt_v1 certificate)
    (certified_prime_power_sqrt_positive_v1 certificate)
    (certified_prime_power_log_v1 certificate).

Definition certified_prime_power_derivative_term_raw_v1
    (L : IR) (H_L_pos : [0] [<] L)
    (certificate : prime_power_certificate_v1) : PartIR :=
  prime_source_derivative_term_raw_v1
    L H_L_pos
    (certified_prime_log_v1 certificate)
    (certified_prime_power_sqrt_v1 certificate)
    (certified_prime_power_sqrt_positive_v1 certificate)
    (certified_prime_power_log_v1 certificate).

Theorem certified_prime_power_finite_sum_derivative_constructive_v1 :
  forall (H : proper realline)
         (n : nat)
         (certificates : nat -> prime_power_certificate_v1)
         (L : nat -> IR)
         (H_L_pos : forall i : nat, [0] [<] L i),
    Derivative realline H
      (FSumx n
        (fun i _ =>
          certified_prime_power_source_term_v1
            (L i) (H_L_pos i) (certificates i)))
      (FSumx n
        (fun i _ =>
          certified_prime_power_derivative_term_raw_v1
            (L i) (H_L_pos i) (certificates i))).
Proof.
  intros H n certificates L H_L_pos.
  apply Derivative_Sumx.
  intros i Hi Hi'.
  unfold certified_prime_power_source_term_v1,
    certified_prime_power_derivative_term_raw_v1.
  apply prime_power_weight_derivative_constructive_v1.
Qed.
