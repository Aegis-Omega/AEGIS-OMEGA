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

  The complex scalar support below formalizes the canonical prime-term formula
  over a supplied function [f : IR -> CC].  It deliberately does NOT identify
  that supplied function with the Lean or O0 carrier.  Cross-prover binding is
  discharged separately by exact-source normalization to the frozen canonical
  prime-term AST; this Coq constituent packages only the kernel-checked formula
  and index semantics on the CoRN carrier.
*)

From Coq Require Import Arith.PeanoNat Lia.
Require Import CoRN.reals.NRootIR.
Require Import CoRN.complex.CComplex.
Require Import VonMangoldtCanonicalBridge.
Require Import CanonicalPrimeSourceSum.

(** Canonical prime-term integer coordinate matching the Lean-side [m=n+1]
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
    apply eq_reflexive.
Qed.

(* -------------------------------------------------------------------- *)
(* Formula-level complex prime-term support.                            *)
(* -------------------------------------------------------------------- *)

(** Positive integer coordinate m=n+1 embedded in CoRN IR. *)
Definition finite_prime_positive_integer_ir_v1 (n : nat) : IR :=
  nring (S n).

Lemma finite_prime_positive_integer_ir_positive_v1 :
  forall n : nat, [0] [<] finite_prime_positive_integer_ir_v1 n.
Proof.
  intro n.
  unfold finite_prime_positive_integer_ir_v1.
  apply nring_pos.
  lia.
Qed.

(** The exact reciprocal 1/(n+1) on the same constructive-real carrier. *)
Definition finite_prime_reciprocal_ir_v1 (n : nat) : IR :=
  [1] [/] finite_prime_positive_integer_ir_v1 n
    [//] pos_ap_zero _ _ (finite_prime_positive_integer_ir_positive_v1 n).

(** Canonical complex scalar term

      Lambda(m) * (f(m) + m^-1 * f(m^-1)),  m=n+1.

    The supplied [f] is intentionally abstract.  This theorem surface binds
    the formula and index convention only; it grants no Lean/O0 carrier
    correspondence. *)
Definition finite_prime_scalar_term_cc_v1
    (f : IR -> CC) (n : nat) : CC :=
  cc_IR (von_mangoldt_v1 (finite_guinand_weil_prime_index_v1 n))
    [*]
  (f (finite_prime_positive_integer_ir_v1 n)
    [+]
   cc_IR (finite_prime_reciprocal_ir_v1 n)
    [*] f (finite_prime_reciprocal_ir_v1 n)).

(** The q=i+2 reciprocal is the same constructive term as the m=n+1 lane
    at n=S i.  Reusing that definition preserves the exact reciprocal while
    avoiding a second proof witness for the same positive denominator. *)
Definition canonical_q_reciprocal_ir_v1 (i : nat) : IR :=
  finite_prime_reciprocal_ir_v1 (S i).

(** The same scalar formula written directly in the existing q=i+2
    coordinate.  This is independent of the basis/trigonometric source
    representation used elsewhere in the proof DAG. *)
Definition canonical_q_prime_scalar_term_cc_v1
    (f : IR -> CC) (i : nat) : CC :=
  cc_IR (von_mangoldt_v1 (canonical_integer_q_v1 i))
    [*]
  (f (canonical_integer_q_ir_v1 i)
    [+]
   cc_IR (canonical_q_reciprocal_ir_v1 i)
    [*] f (canonical_q_reciprocal_ir_v1 i)).

(** The leading n=0 / m=1 scalar term vanishes for every supplied complex
    function because Lambda(1)=0. *)
Theorem finite_prime_scalar_term_leading_zero_v1 :
  forall f : IR -> CC,
    finite_prime_scalar_term_cc_v1 f 0 [=] ([0] : CC).
Proof.
  intro f.
  unfold finite_prime_scalar_term_cc_v1,
    finite_guinand_weil_prime_index_v1.
  astepl
    (cc_IR [0]
      [*]
     (f (finite_prime_positive_integer_ir_v1 0)
       [+]
      cc_IR (finite_prime_reciprocal_ir_v1 0)
       [*] f (finite_prime_reciprocal_ir_v1 0))).
  - Step_final ([0] : CC).
Qed.

(** After removing the inert m=1 term, the n=S i scalar formula is exactly
    the q=i+2 scalar formula. *)
Theorem finite_prime_scalar_term_tail_index_v1 :
  forall (f : IR -> CC) (i : nat),
    finite_prime_scalar_term_cc_v1 f (S i)
      [=] canonical_q_prime_scalar_term_cc_v1 f i.
Proof.
  intros f i.
  unfold finite_prime_scalar_term_cc_v1,
    canonical_q_prime_scalar_term_cc_v1,
    finite_guinand_weil_prime_index_v1,
    finite_prime_positive_integer_ir_v1,
    finite_prime_reciprocal_ir_v1,
    canonical_q_reciprocal_ir_v1,
    canonical_integer_q_ir_v1,
    canonical_integer_q_v1.
  apply eq_reflexive.
Qed.

(** Prime-term constituent closure on the CoRN carrier.

    This theorem packages exactly the two load-bearing facts required by the
    frozen index/prime-term semantics: the leading m=1 term is zero, and the
    remaining n=S i sequence is exactly the canonical q=i+2 tail.  It does not
    assert equality of complete Lean, CoRN, or O0 function carriers. *)
Theorem concrete_prime_term_semantics_v1 :
  (forall f : IR -> CC,
      finite_prime_scalar_term_cc_v1 f 0 [=] ([0] : CC)) /\
  (forall (f : IR -> CC) (i : nat),
      finite_prime_scalar_term_cc_v1 f (S i)
        [=] canonical_q_prime_scalar_term_cc_v1 f i).
Proof.
  split.
  - exact finite_prime_scalar_term_leading_zero_v1.
  - exact finite_prime_scalar_term_tail_index_v1.
Qed.
