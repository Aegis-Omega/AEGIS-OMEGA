(*
  Constructive prime-trigonometry production contract.

  The production module must expose both the full Z-frequency identities and
  the backward-compatible nat-frequency corollaries.  This remains a phase-only
  contract on CoRN IR; it does not establish O0 transport, derivatives, the
  explicit formula, global Weil positivity, or RH.
*)
Require Import PrimeTrigConstructive.

Check prime_diagonal_constructive_cos_phase_Z_v1.
Check prime_source_constructive_sin_phase_Z_v1.
Check prime_diagonal_constructive_cos_phase_v1.
Check prime_source_constructive_sin_phase_v1.
