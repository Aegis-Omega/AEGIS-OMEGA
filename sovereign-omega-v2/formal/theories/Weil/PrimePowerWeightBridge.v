(*
  AEGIS Ω — constructive prime-power weight / pi-normalization bridge v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  This module binds only the analytic parameterization used by a supplied
  Guinand-Weil prime-source descriptor:

      omega = 1 - log(q)/L,
      amplitude = -Lambda(q)/(Pi*sqrt(q)),
      frequency = 2*Pi*omega.

  Together with [scaled_sine_derivative_constructive_v1], this yields a
  constructive CoRN-IR derivative relation and the scalar normalization

      amplitude * frequency = -2*Lambda(q)*omega/sqrt(q).

  The module deliberately does NOT prove that the supplied fields encode an
  actual prime power q=p^k, that Lambda(q) is the von Mangoldt value, or that
  sqrt_q is the constructive square root of q. It also does not prove a finite
  prime-source sum, CoRN-to-O0 trig transport, the Guinand-Weil explicit
  formula, the Weil-operator identity, global Weil positivity, or RH.
*)

Require Import CoRN.transc.Pi.
Require Import PrimeSourceDerivativeConstructive.

Definition omega_param_v1
  (L : IR) (H_L_pos : [0] [<] L) (log_q : IR) : IR :=
  [1] [-] (log_q [/] L [//] pos_ap_zero _ _ H_L_pos).

Definition amplitude_param_v1
  (lambda_q sqrt_q : IR)
  (H_sqrt_q_pos : [0] [<] sqrt_q) : IR :=
  (([--] lambda_q) [/] Pi [//] pos_ap_zero _ _ pos_Pi)
    [/] sqrt_q [//] pos_ap_zero _ _ H_sqrt_q_pos.

Definition frequency_param_v1
  (L : IR) (H_L_pos : [0] [<] L) (log_q : IR) : IR :=
  Two [*] Pi [*] omega_param_v1 L H_L_pos log_q.

Definition normalized_prime_coefficient_v1
  (L : IR) (H_L_pos : [0] [<] L)
  (lambda_q sqrt_q : IR)
  (H_sqrt_q_pos : [0] [<] sqrt_q)
  (log_q : IR) : IR :=
  ([--] (Two [*] lambda_q [*] omega_param_v1 L H_L_pos log_q))
    [/] sqrt_q [//] pos_ap_zero _ _ H_sqrt_q_pos.

Definition prime_source_term_v1
  (L : IR) (H_L_pos : [0] [<] L)
  (lambda_q sqrt_q : IR)
  (H_sqrt_q_pos : [0] [<] sqrt_q)
  (log_q : IR) : PartIR :=
  amplitude_param_v1 lambda_q sqrt_q H_sqrt_q_pos
    {**}(Sine[o](frequency_param_v1 L H_L_pos log_q{**}FId)).

Definition prime_source_derivative_term_raw_v1
  (L : IR) (H_L_pos : [0] [<] L)
  (lambda_q sqrt_q : IR)
  (H_sqrt_q_pos : [0] [<] sqrt_q)
  (log_q : IR) : PartIR :=
  amplitude_param_v1 lambda_q sqrt_q H_sqrt_q_pos
    {**}((Cosine[o](frequency_param_v1 L H_L_pos log_q{**}FId))
      {*} (frequency_param_v1 L H_L_pos log_q{**}[-C-][1])).

Theorem prime_power_weight_derivative_constructive_v1 :
  forall (H : proper realline)
         (L lambda_q sqrt_q log_q : IR)
         (H_L_pos : [0] [<] L)
         (H_sqrt_q_pos : [0] [<] sqrt_q),
    Derivative realline H
      (prime_source_term_v1 L H_L_pos lambda_q sqrt_q H_sqrt_q_pos log_q)
      (prime_source_derivative_term_raw_v1
        L H_L_pos lambda_q sqrt_q H_sqrt_q_pos log_q).
Proof.
  intros H L lambda_q sqrt_q log_q H_L_pos H_sqrt_q_pos.
  unfold prime_source_term_v1, prime_source_derivative_term_raw_v1.
  apply scaled_sine_derivative_constructive_v1.
Qed.

Theorem prime_power_scalar_normalization_v1 :
  forall (L lambda_q sqrt_q log_q : IR)
         (H_L_pos : [0] [<] L)
         (H_sqrt_q_pos : [0] [<] sqrt_q),
    (amplitude_param_v1 lambda_q sqrt_q H_sqrt_q_pos
      [*] frequency_param_v1 L H_L_pos log_q)
    [=]
    normalized_prime_coefficient_v1
      L H_L_pos lambda_q sqrt_q H_sqrt_q_pos log_q.
Proof.
  intros L lambda_q sqrt_q log_q H_L_pos H_sqrt_q_pos.
  unfold amplitude_param_v1, frequency_param_v1,
    normalized_prime_coefficient_v1.
  rational.
Qed.
