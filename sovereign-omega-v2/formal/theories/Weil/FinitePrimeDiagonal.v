From Coq Require Import QArith.
Require Import Ring.

Open Scope Q_scope.

(*
  Structural prime-diagonal bridge between the two executable routes.

  IMPORTANT AUTHORITY BOUNDARY:
  c_direct and c_complement are the cosine values used by the Arb and
  closed-form routes respectively.  Equality of those phase evaluations is
  an explicit premise here.  This file does NOT prove trigonometric
  periodicity and does NOT prove the derivative of sine.
*)

Definition arb_prime_diagonal_kernel (r c_direct : Q) : Q :=
  2 * (1 - r) * c_direct.

Definition crosscheck_prime_derivative_kernel (r c_complement : Q) : Q :=
  - (2 * (1 - r) * c_complement).

Theorem prime_diagonal_sign_periodicity_bridge :
  forall (r c_direct c_complement : Q),
    c_complement = c_direct ->
    crosscheck_prime_derivative_kernel r c_complement =
    - arb_prime_diagonal_kernel r c_direct.
Proof.
  intros r c_direct c_complement Hphase.
  subst c_complement.
  unfold crosscheck_prime_derivative_kernel, arb_prime_diagonal_kernel.
  ring.
Qed.

(*
  The Arb evaluator subtracts the positive prime diagonal kernel from the
  final matrix.  The independent closed-form route adds the derivative
  contribution, whose kernel carries the minus sign above.  Once the two
  cosine phase evaluations are identified, the weighted matrix
  contributions coincide exactly.
*)
Definition arb_prime_diagonal_matrix_contribution
    (weight r c_direct : Q) : Q :=
  - (weight * arb_prime_diagonal_kernel r c_direct).

Definition crosscheck_prime_diagonal_matrix_contribution
    (weight r c_complement : Q) : Q :=
  weight * crosscheck_prime_derivative_kernel r c_complement.

Theorem prime_diagonal_source_sign_bridge :
  forall (weight r c_direct c_complement : Q),
    c_complement = c_direct ->
    crosscheck_prime_diagonal_matrix_contribution
      weight r c_complement =
    arb_prime_diagonal_matrix_contribution
      weight r c_direct.
Proof.
  intros weight r c_direct c_complement Hphase.
  subst c_complement.
  unfold crosscheck_prime_diagonal_matrix_contribution,
         arb_prime_diagonal_matrix_contribution,
         crosscheck_prime_derivative_kernel,
         arb_prime_diagonal_kernel.
  ring.
Qed.
