(**
  AEGIS Ω — q-native canonical prime-source sum v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  [VonMangoldtCanonicalBridge] defines the prime base and von Mangoldt
  weight as total functions of a supplied integer [q].  This module removes
  prime-power certificate families from the finite analytic interface:

  - [None] means precisely that [q] has no representation as a positive
    power of a prime;
  - that negative branch forces both [Lambda(q)] and the analytic amplitude
    to zero;
  - the positive branch binds [Lambda(q)], [sqrt(q)], and [log(q)] to the
    earlier proof-carrying certificate semantics;
  - [q = 2, ..., count + 1] therefore supplies a canonical all-integer index
    for the finite source and its constructive derivative.  No separate
    prime-power enumeration or total factorisation is needed for this slice.

  It does not establish the Guinand--Weil explicit formula, CoRN-to-O0
  transport, global Weil positivity, the Weil criterion, or RH.
*)

From Coq Require Import Arith.PeanoNat Lia.

Require Import CoRN.reals.NRootIR.
Require Import CoRN.transc.Exponential.
Require Import CoRN.transc.Pi.
Require Import CoRN.ftc.MoreFunctions.
Require Import PrimePowerWeightBridge.
Require Import PrimePowerArithmeticBridge.
Require Import VonMangoldtCanonicalBridge.

Theorem prime_power_base_v1_none_iff :
  forall q : nat,
    prime_power_base_v1 q = None <->
    forall p k : nat,
      prime_nat_v1 p -> (0 < k)%nat -> Nat.pow p k <> q.
Proof.
  intros q. split.
  - intros Hnone p k Hp Hk Heq. subst q.
    rewrite (prime_power_base_v1_complete p k Hp Hk) in Hnone.
    discriminate Hnone.
  - intros Hnot.
    destruct (prime_power_base_v1 q) as [p|] eqn:Hbase; [|reflexivity].
    exfalso.
    destruct (prime_power_base_v1_sound q p Hbase)
      as [Hp [k [Hk Hpow]]].
    exact (Hnot p k Hp Hk Hpow).
Qed.

Theorem von_mangoldt_v1_zero_off_prime_powers :
  forall q : nat,
    (forall p k : nat,
      prime_nat_v1 p -> (0 < k)%nat -> Nat.pow p k <> q) ->
    von_mangoldt_v1 q [=] [0].
Proof.
  intros q Hnot.
  assert (Hnone : prime_power_base_v1 q = None).
  { apply (proj2 (prime_power_base_v1_none_iff q)). exact Hnot. }
  unfold prime_power_base_v1 in Hnone.
  unfold von_mangoldt_v1.
  destruct (prime_power_base_sig_v1 q) as [[p Hp]|] eqn:Hbase.
  - discriminate Hnone.
  - algebra.
Qed.

(* The first [count] canonical integer indices are q = 2, ..., count + 1.
   Summing over these indices needs no prime-power enumerator: Lambda is the
   filter and the theorem above proves its zero branch. *)
Definition canonical_integer_q_v1 (i : nat) : nat := S (S i).

Lemma canonical_integer_q_positive_v1 :
  forall i : nat, (0 < canonical_integer_q_v1 i)%nat.
Proof. intros i. unfold canonical_integer_q_v1. lia. Qed.

Definition canonical_integer_q_ir_v1 (i : nat) : IR :=
  nring (canonical_integer_q_v1 i).

Lemma canonical_integer_q_ir_positive_v1 :
  forall i : nat, [0] [<] canonical_integer_q_ir_v1 i.
Proof.
  intros i. unfold canonical_integer_q_ir_v1.
  apply nring_pos. apply canonical_integer_q_positive_v1.
Qed.

Definition canonical_integer_sqrt_v1 (i : nat) : IR :=
  sqrt
    (canonical_integer_q_ir_v1 i)
    (less_leEq _ _ _ (canonical_integer_q_ir_positive_v1 i)).

Lemma canonical_integer_sqrt_positive_v1 :
  forall i : nat, [0] [<] canonical_integer_sqrt_v1 i.
Proof.
  intros i. unfold canonical_integer_sqrt_v1, sqrt.
  apply NRoot_pos. apply canonical_integer_q_ir_positive_v1.
Qed.

Definition canonical_integer_log_v1 (i : nat) : IR :=
  Log
    (canonical_integer_q_ir_v1 i)
    (canonical_integer_q_ir_positive_v1 i).

Theorem canonical_integer_parameters_certified_binding_v1 :
  forall (i : nat) (certificate : prime_power_certificate_v1),
    canonical_integer_q_v1 i =
      certified_prime_power_value_v1 certificate ->
    von_mangoldt_v1 (canonical_integer_q_v1 i)
      [=] certified_prime_log_v1 certificate /\
    canonical_integer_sqrt_v1 i
      [=] certified_prime_power_sqrt_v1 certificate /\
    canonical_integer_log_v1 i
      [=] certified_prime_power_log_v1 certificate.
Proof.
  intros i certificate Hq. split.
  - rewrite Hq. apply von_mangoldt_v1_certified_binding.
  - split.
    + unfold canonical_integer_sqrt_v1,
        certified_prime_power_sqrt_v1.
      apply sqrt_wd.
      unfold canonical_integer_q_ir_v1,
        certified_prime_power_value_ir_v1.
      rewrite Hq. algebra.
    + unfold canonical_integer_log_v1,
        certified_prime_power_log_v1.
      apply Log_wd.
      unfold canonical_integer_q_ir_v1,
        certified_prime_power_value_ir_v1.
      rewrite Hq. algebra.
Qed.

Theorem canonical_von_mangoldt_amplitude_zero_off_prime_powers_v1 :
  forall i : nat,
    (forall p k : nat,
      prime_nat_v1 p -> (0 < k)%nat ->
      Nat.pow p k <> canonical_integer_q_v1 i) ->
    amplitude_param_v1
      (von_mangoldt_v1 (canonical_integer_q_v1 i))
      (canonical_integer_sqrt_v1 i)
      (canonical_integer_sqrt_positive_v1 i)
    [=] [0].
Proof.
  intros i Hnot.
  pose proof
    (von_mangoldt_v1_zero_off_prime_powers
      (canonical_integer_q_v1 i) Hnot) as Hzero.
  unfold amplitude_param_v1.
  apply eq_transitive_unfolded with
    ((([--] [0]) [/] Pi [//] pos_ap_zero _ _ pos_Pi)
      [/] canonical_integer_sqrt_v1 i
      [//] pos_ap_zero _ _ (canonical_integer_sqrt_positive_v1 i)).
  - apply div_wd.
    + apply div_wd.
      * apply un_op_wd_unfolded. exact Hzero.
      * apply eq_reflexive.
    + apply eq_reflexive.
  - unfold cf_div.
    rewrite cg_zero_inv.
    rewrite cring_mult_zero_op.
    apply cring_mult_zero_op.
Qed.

Definition canonical_von_mangoldt_source_term_v1
    (L : IR) (H_L_pos : [0] [<] L) (i : nat) : PartIR :=
  prime_source_term_v1
    L H_L_pos
    (von_mangoldt_v1 (canonical_integer_q_v1 i))
    (canonical_integer_sqrt_v1 i)
    (canonical_integer_sqrt_positive_v1 i)
    (canonical_integer_log_v1 i).

Definition canonical_von_mangoldt_derivative_term_raw_v1
    (L : IR) (H_L_pos : [0] [<] L) (i : nat) : PartIR :=
  prime_source_derivative_term_raw_v1
    L H_L_pos
    (von_mangoldt_v1 (canonical_integer_q_v1 i))
    (canonical_integer_sqrt_v1 i)
    (canonical_integer_sqrt_positive_v1 i)
    (canonical_integer_log_v1 i).

Theorem
  canonical_von_mangoldt_finite_sum_shared_scale_derivative_constructive_v1 :
  forall (H : proper realline)
         (count : nat)
         (L : IR)
         (H_L_pos : [0] [<] L),
    Derivative realline H
      (FSumx count
        (fun i _ =>
          canonical_von_mangoldt_source_term_v1 L H_L_pos i))
      (FSumx count
        (fun i _ =>
          canonical_von_mangoldt_derivative_term_raw_v1 L H_L_pos i)).
Proof.
  intros H count L H_L_pos.
  apply Derivative_Sumx.
  intros i Hi Hi'.
  unfold canonical_von_mangoldt_source_term_v1,
    canonical_von_mangoldt_derivative_term_raw_v1.
  apply prime_power_weight_derivative_constructive_v1.
Qed.
