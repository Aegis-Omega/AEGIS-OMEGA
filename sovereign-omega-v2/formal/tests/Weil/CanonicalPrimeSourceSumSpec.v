(*
  AEGIS Ω — q-native canonical prime-source contract v1

  RED-first contract.  It locks the two branches of the all-integer index:
  non-prime-powers have zero Lambda and zero analytic amplitude; prime powers
  agree with the earlier certificate semantics.  The finite derivative then
  ranges canonically over q = 2, ..., count + 1 without accepting a supplied
  certificate family or a separate prime-power enumerator.

  This contract does not bind CoRN-to-O0 transport, the Guinand--Weil
  explicit formula, formula-to-operator identity, global Weil positivity,
  the Weil criterion, or RH.
*)

From Coq Require Import Arith.PeanoNat.

Require Import CoRN.reals.NRootIR.
Require Import CoRN.ftc.MoreFunctions.
Require Import PrimePowerWeightBridge.
Require Import PrimePowerArithmeticBridge.
Require Import VonMangoldtCanonicalBridge.
Require Import CanonicalPrimeSourceSum.

Check prime_power_base_v1_none_iff
  : forall q : nat,
      prime_power_base_v1 q = None <->
      forall p k : nat,
        prime_nat_v1 p -> (0 < k)%nat -> Nat.pow p k <> q.

Check von_mangoldt_v1_zero_off_prime_powers
  : forall q : nat,
      (forall p k : nat,
        prime_nat_v1 p -> (0 < k)%nat -> Nat.pow p k <> q) ->
      von_mangoldt_v1 q [=] [0].

Check canonical_integer_q_v1 : nat -> nat.

Check canonical_integer_q_v1_scope
  : forall i : nat, canonical_integer_q_v1 i = S (S i).

Check canonical_integer_q_v1_injective
  : forall i j : nat, canonical_integer_q_v1 i = canonical_integer_q_v1 j -> i = j.

Check canonical_integer_q_v1_ge_2
  : forall i : nat, (2 <= canonical_integer_q_v1 i)%nat.

Check canonical_integer_parameters_certified_binding_v1
  : forall (i : nat) (certificate : prime_power_certificate_v1),
      canonical_integer_q_v1 i =
        certified_prime_power_value_v1 certificate ->
      von_mangoldt_v1 (canonical_integer_q_v1 i)
        [=] certified_prime_log_v1 certificate /\
      canonical_integer_sqrt_v1 i
        [=] certified_prime_power_sqrt_v1 certificate /\
      canonical_integer_log_v1 i
        [=] certified_prime_power_log_v1 certificate.

Check canonical_von_mangoldt_amplitude_zero_off_prime_powers_v1
  : forall i : nat,
      (forall p k : nat,
        prime_nat_v1 p -> (0 < k)%nat ->
        Nat.pow p k <> canonical_integer_q_v1 i) ->
      amplitude_param_v1
        (von_mangoldt_v1 (canonical_integer_q_v1 i))
        (canonical_integer_sqrt_v1 i)
        (canonical_integer_sqrt_positive_v1 i)
      [=] [0].

Check canonical_von_mangoldt_finite_sum_shared_scale_derivative_constructive_v1
  : forall (H : proper realline)
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

Print Assumptions prime_power_base_v1_none_iff.
Print Assumptions canonical_integer_q_v1_scope.
Print Assumptions canonical_integer_q_v1_injective.
Print Assumptions canonical_integer_q_v1_ge_2.
Print Assumptions von_mangoldt_v1_zero_off_prime_powers.
Print Assumptions canonical_integer_parameters_certified_binding_v1.
Print Assumptions
  canonical_von_mangoldt_amplitude_zero_off_prime_powers_v1.
Print Assumptions
  canonical_von_mangoldt_finite_sum_shared_scale_derivative_constructive_v1.
