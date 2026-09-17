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

Definition finite_guinand_weil_prime_index_v1 (n : nat) : nat := S n.

Theorem concrete_index_semantics_v1 :
  finite_guinand_weil_prime_index_v1 0 = 1 /\
  forall i : nat,
    finite_guinand_weil_prime_index_v1 (S i) = canonical_integer_q_v1 i.
Proof.
  split.
  - reflexivity.
  - intro i. reflexivity.
Qed.

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

Definition finite_prime_reciprocal_ir_v1 (n : nat) : IR :=
  [1] [/] finite_prime_positive_integer_ir_v1 n
    [//] pos_ap_zero _ _ (finite_prime_positive_integer_ir_positive_v1 n).

Definition finite_prime_scalar_term_cc_v1
    (f : IR -> CC) (n : nat) : CC :=
  cc_IR (von_mangoldt_v1 (finite_guinand_weil_prime_index_v1 n))
    [*]
  (f (finite_prime_positive_integer_ir_v1 n)
    [+]
   cc_IR (finite_prime_reciprocal_ir_v1 n)
    [*] f (finite_prime_reciprocal_ir_v1 n)).

Definition canonical_q_reciprocal_ir_v1 (i : nat) : IR :=
  finite_prime_reciprocal_ir_v1 (S i).

Definition canonical_q_prime_scalar_term_cc_v1
    (f : IR -> CC) (i : nat) : CC :=
  cc_IR (von_mangoldt_v1 (canonical_integer_q_v1 i))
    [*]
  (f (canonical_integer_q_ir_v1 i)
    [+]
   cc_IR (canonical_q_reciprocal_ir_v1 i)
    [*] f (canonical_q_reciprocal_ir_v1 i)).

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

Definition finite_pole_term_cc_v1 (mellin_zero mellin_one : CC) : CC :=
  mellin_zero [+] mellin_one.

Theorem concrete_pole_term_semantics_v1 :
  forall mellin_zero mellin_one : CC,
    finite_pole_term_cc_v1 mellin_zero mellin_one
      [=] mellin_zero [+] mellin_one.
Proof.
  intros mellin_zero mellin_one.
  unfold finite_pole_term_cc_v1.
  apply eq_reflexive.
Qed.

Definition finite_archimedean_normalization_cc_v1
    (constant_at_one integral_value : CC) : CC :=
  constant_at_one [+] integral_value.

Theorem concrete_archimedean_normalization_v1 :
  forall constant_at_one integral_value : CC,
    finite_archimedean_normalization_cc_v1 constant_at_one integral_value
      [=] constant_at_one [+] integral_value.
Proof.
  intros constant_at_one integral_value.
  unfold finite_archimedean_normalization_cc_v1.
  apply eq_reflexive.
Qed.

Definition finite_positive_prefix_member_v1
    (count m : nat) : Prop :=
  (1 <= m <= S count)%nat.

Definition finite_coq_tail_member_v1
    (count i : nat) : Prop :=
  (i < count)%nat.

Theorem concrete_cutoff_semantics_v1 :
  von_mangoldt_v1 (finite_guinand_weil_prime_index_v1 0) [=] [0] /\
  (forall count i : nat,
      finite_coq_tail_member_v1 count i ->
      finite_positive_prefix_member_v1 count
        (finite_guinand_weil_prime_index_v1 (S i)) /\
      finite_guinand_weil_prime_index_v1 (S i) =
        canonical_integer_q_v1 i) /\
  (forall count m : nat,
      (2 <= m <= S count)%nat ->
      exists i : nat,
        finite_coq_tail_member_v1 count i /\
        m = canonical_integer_q_v1 i).
Proof.
  split.
  - exact concrete_von_mangoldt_one_zero_v1.
  - split.
    + intros count i Hi.
      split.
      * unfold finite_coq_tail_member_v1 in Hi.
        unfold finite_positive_prefix_member_v1,
          finite_guinand_weil_prime_index_v1.
        lia.
      * reflexivity.
    + intros count m Hm.
      exists (m - 2)%nat.
      split.
      * unfold finite_coq_tail_member_v1.
        lia.
      * unfold canonical_integer_q_v1.
        lia.
Qed.

(* -------------------------------------------------------------------- *)
(* Measure convention semantics.                                      *)
(* -------------------------------------------------------------------- *)

Inductive FiniteWeilMeasureConventionV1 : Type :=
| OrdinaryLebesgueV1
| MultiplicativeHaarV1.

Definition finite_explicit_integral_measure_v1 : FiniteWeilMeasureConventionV1 :=
  OrdinaryLebesgueV1.

Definition finite_autocorrelation_inner_measure_v1 : FiniteWeilMeasureConventionV1 :=
  OrdinaryLebesgueV1.

(** Both frozen integrals use ordinary Lebesgue measure.  The final conjunct
    makes the forbidden dx/x (multiplicative-Haar) drift discriminable in the
    kernel rather than leaving it as prose. *)
Theorem concrete_measure_semantics_v1 :
  finite_explicit_integral_measure_v1 = OrdinaryLebesgueV1 /\
  finite_autocorrelation_inner_measure_v1 = OrdinaryLebesgueV1 /\
  OrdinaryLebesgueV1 <> MultiplicativeHaarV1.
Proof.
  split.
  - reflexivity.
  - split.
    + reflexivity.
    + discriminate.
Qed.
