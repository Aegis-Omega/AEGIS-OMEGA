(*
  AEGIS Ω — canonical von Mangoldt contract v1

  This contract binds four claims that must not be flattened:
  - the bespoke primality predicate is decidable, through the reverse
    standard-library bridge;
  - the prime base of q is a FUNCTION of q alone, sound and complete;
  - the certificate-free weight Lambda agrees with every certificate's log p;
  - the canonical base of 64 is 2 and is not 4, so primality selects the
    base rather than any base > 1 that happens to fit.

  The contract does not establish total factorisation of arbitrary n,
  canonical prime-power enumeration, CoRN-to-O0 transport, the Guinand-Weil
  explicit formula, global Weil positivity, or RH.
*)

From Coq Require Import Arith.PeanoNat ZArith Znumtheory.

Require Import CoRN.reals.NRootIR.
Require Import CoRN.transc.Exponential.
Require Import CoRN.ftc.MoreFunctions.
Require Import PrimePowerWeightBridge.
Require Import PrimePowerArithmeticBridge.
Require Import PrimalityStdlibBridge.
Require Import VonMangoldtCanonicalBridge.

Check Znumtheory_to_prime_nat_v1
  : forall p : nat, prime (Z.of_nat p) -> prime_nat_v1 p.

Check prime_nat_v1_dec
  : forall p : nat, {prime_nat_v1 p} + {~ prime_nat_v1 p}.

Check prime_power_base_v1 : nat -> option nat.

Check prime_power_base_v1_sound
  : forall q p : nat, prime_power_base_v1 q = Some p ->
      prime_nat_v1 p /\ exists k : nat, (0 < k)%nat /\ Nat.pow p k = q.

Check prime_power_base_v1_complete
  : forall p k : nat, prime_nat_v1 p -> (0 < k)%nat ->
      prime_power_base_v1 (Nat.pow p k) = Some p.

Check von_mangoldt_v1 : nat -> IR.

Check von_mangoldt_v1_certified_binding
  : forall certificate : prime_power_certificate_v1,
      von_mangoldt_v1 (certified_prime_power_value_v1 certificate)
      [=] certified_prime_log_v1 certificate.

(* The falsifiers: 4^3 = 64 = 2^6, and the canonical base is 2. *)
Check canonical_base_of_64_is_2 : prime_power_base_v1 64 = Some 2%nat.
Check canonical_base_of_64_is_not_4 : prime_power_base_v1 64 <> Some 4%nat.

Print Assumptions Znumtheory_to_prime_nat_v1.
Print Assumptions prime_power_base_v1_sound.
Print Assumptions prime_power_base_v1_complete.
Print Assumptions von_mangoldt_v1_certified_binding.
Print Assumptions canonical_base_of_64_is_2.
Print Assumptions canonical_base_of_64_is_not_4.
