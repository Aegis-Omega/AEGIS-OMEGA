(*
  AEGIS Ω — prime-power arithmetic semantics theorem contract v2

  This contract separates three claims that must not be flattened:
  - a supplied certificate exposes the full local primality predicate;
  - q = p^k induces constructive CoRN-IR power/log/root identities; and
  - the finite derivative family admits one shared scale L, as a corollary
    of the general per-index statement.

  The contract does not establish a standard-library primality bridge, total
  factorization, a total von Mangoldt function, canonical prime-power
  enumeration, CoRN-to-O0 transport, the Guinand-Weil explicit formula,
  global Weil positivity, or RH.
*)

Require Import PrimePowerArithmeticBridge.

Check prime_power_certificate_v1.

Check certified_prime_base_divisor_classification_v1
  : forall (certificate : prime_power_certificate_v1) (d : nat),
      divides_nat_v1 d (certified_prime_base_v1 certificate) ->
      d = 1 \/ d = certified_prime_base_v1 certificate.

Check certified_prime_power_ir_power_identity_v1.
Check certified_prime_power_log_identity_v1.
Check certified_prime_power_sqrt_square_identity_v1.

Check certified_prime_power_finite_sum_derivative_constructive_v1.

Check certified_prime_power_finite_sum_shared_scale_derivative_constructive_v1
  : forall (H : proper realline)
           (n : nat)
           (certificates : nat -> prime_power_certificate_v1)
           (L : IR)
           (H_L_pos : [0] [<] L),
      Derivative realline H
        (FSumx n
          (fun i _ =>
            certified_prime_power_source_term_v1
              L H_L_pos (certificates i)))
        (FSumx n
          (fun i _ =>
            certified_prime_power_derivative_term_raw_v1
              L H_L_pos (certificates i))).

Print Assumptions certified_prime_base_divisor_classification_v1.
Print Assumptions certified_prime_power_ir_power_identity_v1.
Print Assumptions certified_prime_power_log_identity_v1.
Print Assumptions certified_prime_power_sqrt_square_identity_v1.
Print Assumptions certified_prime_power_finite_sum_derivative_constructive_v1.
Print Assumptions
  certified_prime_power_finite_sum_shared_scale_derivative_constructive_v1.
