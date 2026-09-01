(*
  AEGIS Ω — primality activation contract v1

  This contract binds three claims that must not be flattened:
  - the bespoke [prime_nat_v1] predicate implies the standard-library
    [Znumtheory.prime] of its integer image;
  - Euclid's lemma and prime-power base uniqueness hold on [nat]; and
  - the uniqueness conclusion is FALSE for merely-greater-than-one bases,
    so primality is load-bearing rather than inert.

  The contract does not establish total factorisation, a total von Mangoldt
  function, canonical prime-power enumeration, CoRN-to-O0 transport, the
  Guinand-Weil explicit formula, global Weil positivity, or RH.
*)

From Coq Require Import Arith.PeanoNat ZArith Znumtheory.

Require Import PrimePowerArithmeticBridge.
Require Import PrimalityStdlibBridge.

Check prime_nat_v1_to_Znumtheory
  : forall p : nat, prime_nat_v1 p -> prime (Z.of_nat p).

Check prime_nat_v1_euclid
  : forall p a b : nat,
      prime_nat_v1 p ->
      divides_nat_v1 p (a * b) ->
      divides_nat_v1 p a \/ divides_nat_v1 p b.

Check prime_nat_v1_divides_pow
  : forall p q k : nat,
      prime_nat_v1 p -> divides_nat_v1 p (Nat.pow q k) -> divides_nat_v1 p q.

Check prime_power_base_uniqueness_v1
  : forall p k p' k' : nat,
      prime_nat_v1 p -> prime_nat_v1 p' ->
      (0 < k)%nat -> (0 < k')%nat ->
      Nat.pow p k = Nat.pow p' k' ->
      p = p' /\ k = k'.

(* The falsifier: without primality the conclusion fails at 4^3 = 2^6. *)
Check base_uniqueness_fails_without_primality
  : Nat.pow 4 3 = Nat.pow 2 6 /\ (4 <> 2)%nat /\ (3 <> 6)%nat.

Check four_is_not_prime_nat_v1 : ~ prime_nat_v1 4.

Print Assumptions prime_nat_v1_to_Znumtheory.
Print Assumptions prime_nat_v1_euclid.
Print Assumptions prime_nat_v1_divides_pow.
Print Assumptions prime_power_base_uniqueness_v1.
Print Assumptions base_uniqueness_fails_without_primality.
Print Assumptions four_is_not_prime_nat_v1.
