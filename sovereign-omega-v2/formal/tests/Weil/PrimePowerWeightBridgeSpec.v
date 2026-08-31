(*
  AEGIS Ω — prime-power weight / pi-normalization bridge contract v1

  RED-first FORMAL_MATH_EVIDENCE_ONLY contract.

  This contract binds the arithmetic parameterization used by the Guinand-Weil
  single-frequency prime source to the constructive CoRN IR derivative theorem.
  It does not formalize prime enumeration, a finite prime-source sum, O0 trig
  transport, the explicit formula, global Weil positivity, or RH.
*)

Require Import CoRN.transc.Pi.
Require Import PrimePowerWeightBridge.

Definition prime_power_weight_derivative_contract_v1 :
  forall (H : proper realline)
         (L lambda_q sqrt_q log_q : IR)
         (H_L_pos : [0] [<] L)
         (H_sqrt_q_pos : [0] [<] sqrt_q),
    Derivative realline H
      (prime_source_term_v1 L H_L_pos lambda_q sqrt_q H_sqrt_q_pos log_q)
      (prime_source_derivative_term_raw_v1
        L H_L_pos lambda_q sqrt_q H_sqrt_q_pos log_q) :=
  prime_power_weight_derivative_constructive_v1.

Definition prime_power_scalar_normalization_contract_v1 :
  forall (L lambda_q sqrt_q log_q : IR)
         (H_L_pos : [0] [<] L)
         (H_sqrt_q_pos : [0] [<] sqrt_q),
    (amplitude_param_v1 lambda_q sqrt_q H_sqrt_q_pos
      [*] frequency_param_v1 L H_L_pos log_q)
    [=]
    normalized_prime_coefficient_v1
      L H_L_pos lambda_q sqrt_q H_sqrt_q_pos log_q :=
  prime_power_scalar_normalization_v1.

Check omega_param_v1.
Check amplitude_param_v1.
Check frequency_param_v1.
Check normalized_prime_coefficient_v1.
Check prime_source_term_v1.
Check prime_source_derivative_term_raw_v1.
Check prime_power_weight_derivative_constructive_v1.
Check prime_power_scalar_normalization_v1.
