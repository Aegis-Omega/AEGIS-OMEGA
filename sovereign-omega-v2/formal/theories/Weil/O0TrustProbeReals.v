(*
  Diagnostic only: isolate the assumption surface of classical Coq Reals.
  Nothing in this file is production proof authority.
*)
From Coq Require Import Reals.
From Coq Require Import Rtrigo1.
From Coq Require Import Rtrigo_reg.
From Coq Require Import Ring.

Open Scope R_scope.

Theorem o0_trust_probe_reals_reflexive :
  forall x : R, x = x.
Proof.
  intros x.
  reflexivity.
Qed.

(* For integer frequency n, the cosine phase used by the closed-form route
   at (1-r) agrees with the direct Arb phase at r. *)
Theorem prime_diagonal_classical_cos_phase_probe :
  forall (r : R) (n : nat),
    cos (2 * INR n * PI * (1 - r)) =
    cos (2 * INR n * PI * r).
Proof.
  intros r n.
  replace (2 * INR n * PI * (1 - r))
    with (-(2 * INR n * PI * r) + 2 * INR n * PI) by ring.
  rewrite cos_period.
  rewrite cos_neg.
  reflexivity.
Qed.

(* The corresponding sine phase changes sign. *)
Theorem prime_source_classical_sin_phase_probe :
  forall (r : R) (n : nat),
    sin (2 * INR n * PI * (1 - r)) =
    - sin (2 * INR n * PI * r).
Proof.
  intros r n.
  replace (2 * INR n * PI * (1 - r))
    with (-(2 * INR n * PI * r) + 2 * INR n * PI) by ring.
  rewrite sin_period.
  rewrite sin_neg.
  reflexivity.
Qed.

(* Primitive derivative needed by the diagonal closed-form route. *)
Theorem prime_source_classical_sine_derivative_probe :
  forall x : R,
    derive_pt sin x (derivable_pt_sin x) = cos x.
Proof.
  intro x.
  apply derive_pt_sin.
Qed.
