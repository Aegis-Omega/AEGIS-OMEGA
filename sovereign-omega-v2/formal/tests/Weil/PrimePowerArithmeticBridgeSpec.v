(*
  AEGIS Ω — prime-power arithmetic semantics theorem contract v1

  This theorem-level contract is installed before the production module.
  While [PrimePowerArithmeticBridge] is absent, the dedicated RED workflow
  must still fail exactly at this import and nowhere else.

  A later GREEN transition must provide:
  - a proof-carrying natural prime-power certificate;
  - the CoRN-IR identity induced by q = p^k;
  - the corresponding constructive logarithm identity;
  - the square identity for the canonical constructive square root; and
  - finite derivative linearity for the certified prime-power family.

  The contract does not request a total factorization algorithm, a total
  von Mangoldt implementation, CoRN-to-O0 transport, the Guinand-Weil
  explicit formula, global Weil positivity, or RH.
*)

Require Import PrimePowerArithmeticBridge.

Check prime_power_certificate_v1.
Check certified_prime_power_ir_power_identity_v1.
Check certified_prime_power_log_identity_v1.
Check certified_prime_power_sqrt_square_identity_v1.
Check certified_prime_power_finite_sum_derivative_constructive_v1.

Print Assumptions certified_prime_power_ir_power_identity_v1.
Print Assumptions certified_prime_power_log_identity_v1.
Print Assumptions certified_prime_power_sqrt_square_identity_v1.
Print Assumptions certified_prime_power_finite_sum_derivative_constructive_v1.
