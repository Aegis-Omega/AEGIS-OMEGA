(**
  AEGIS Ω — concrete finite Guinand–Weil semantics v1

  Production PR #1 semantic boundary.

  This module is intentionally semantics-only.  It does not import the finite
  matrix/PSD bridge, does not construct a matrix representation, and does not
  state finite lower-bound, convergence, globalization, or RH claims.

  Stage 1 closes the first real cross-system convention mismatch:

  - the Lean explicit-right-side prime sequence uses the positive integer
    m = n + 1, so n = 0 denotes m = 1;
  - the existing Coq canonical finite source uses q = i + 2, omitting m = 1;
  - the omitted leading term is semantically inert because Lambda(1) = 0.

  Later constituent theorems in this same module must bind the remaining
  canonical specification surfaces before the aggregate finite-semantics
  theorem may be declared closed.
*)

From Coq Require Import Arith.PeanoNat Lia.
Require Import CanonicalPrimeSourceSum.

(** Canonical prime-term integer coordinate matching the Lean-side `m=n+1`
    convention.  This is a semantic coordinate only, not a matrix index. *)
Definition finite_guinand_weil_prime_index_v1 (n : nat) : nat := S n.

(** The Coq q-native finite index is exactly the tail of the canonical
    positive-integer coordinate after the leading m=1 term. *)
Theorem concrete_index_semantics_v1 :
  finite_guinand_weil_prime_index_v1 0 = 1 /\
  forall i : nat,
    finite_guinand_weil_prime_index_v1 (S i) = canonical_integer_q_v1 i.
Proof.
  split.
  - reflexivity.
  - intro i. reflexivity.
Qed.

(** The leading positive integer m=1 is not a positive power of a prime, so
    the already verified total Coq von-Mangoldt function evaluates to zero. *)
Lemma concrete_von_mangoldt_one_zero_v1 :
  von_mangoldt_v1 1 [=] [0].
Proof.
  apply von_mangoldt_v1_zero_off_prime_powers.
  intros p k Hp Hk Hpow.
  destruct Hp as [Hp_gt1 _].
  pose proof (pow_exponent_bound p k ltac:(lia)) as Hexp.
  rewrite Hpow in Hexp.
  lia.
Qed.

(** Von-Mangoldt semantics are therefore preserved by dropping the inert
    leading m=1 term and shifting the remaining positive-integer coordinate
    onto the existing Coq q=i+2 coordinate. *)
Theorem concrete_von_mangoldt_semantics_v1 :
  von_mangoldt_v1 (finite_guinand_weil_prime_index_v1 0) [=] [0] /\
  forall i : nat,
    von_mangoldt_v1 (finite_guinand_weil_prime_index_v1 (S i))
      [=] von_mangoldt_v1 (canonical_integer_q_v1 i).
Proof.
  split.
  - exact concrete_von_mangoldt_one_zero_v1.
  - intro i.
    change von_mangoldt_v1 (S (S i)) [=] von_mangoldt_v1 (S (S i)).
    apply eq_reflexive.
Qed.
