(**
  AEGIS Ω — constructive finite prime-source sum derivative v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  This module proves finite linearity only for a supplied family of analytic
  descriptors already matched, via [Feq realline], to the constructive source
  and derivative terms of [PrimePowerWeightBridge].  It deliberately does not
  identify indices with actual prime powers, bind von Mangoldt values, or
  establish CoRN-IR to O0 transport, an explicit formula, global Weil
  positivity, or RH.

  The supplied [source_terms] and [derivative_terms] do not depend on the
  bound proof [Hi : i < n].  This keeps the finite-family interface independent
  of proof-object identity while reusing CoRN 9.0.0 [Derivative_Sumx].
*)

Require Import CoRN.ftc.MoreFunctions.
Require Import PrimePowerWeightBridge.

Section FinitePrimeSourceSum.

Variable H_proper : proper realline.
Variable n : nat.
Variable source_terms derivative_terms : nat -> PartIR.
Variable L lambda_q sqrt_q log_q : nat -> IR.

Variable H_L_pos : forall i : nat, i < n -> [0] [<] L i.
Variable H_sqrt_q_pos : forall i : nat, i < n -> [0] [<] sqrt_q i.

Hypothesis H_source_match :
  forall (i : nat) (Hi : i < n),
    Feq realline
      (prime_source_term_v1
        (L i) (H_L_pos i Hi)
        (lambda_q i) (sqrt_q i)
        (H_sqrt_q_pos i Hi)
        (log_q i))
      (source_terms i).

Hypothesis H_derivative_match :
  forall (i : nat) (Hi : i < n),
    Feq realline
      (prime_source_derivative_term_raw_v1
        (L i) (H_L_pos i Hi)
        (lambda_q i) (sqrt_q i)
        (H_sqrt_q_pos i Hi)
        (log_q i))
      (derivative_terms i).

Theorem finite_prime_source_sum_derivative_constructive_v1 :
  Derivative realline H_proper
    (FSumx n (fun i _ => source_terms i))
    (FSumx n (fun i _ => derivative_terms i)).
Proof.
  apply Derivative_Sumx.
  intros i Hi Hi'.
  eapply Derivative_wdl.
  - exact (H_source_match i Hi).
  - eapply Derivative_wdr.
    + exact (H_derivative_match i Hi).
    + apply prime_power_weight_derivative_constructive_v1.
Qed.

End FinitePrimeSourceSum.
