(*
  AEGIS Ω — Archimedean tail order: finite Gram core v1

  This file machine-proves only the finite algebraic positivity kernel behind
  a rank-two Cauchy–Stieltjes Gram increment.  It does NOT prove that the
  analytic Archimedean tail of the Weil form has this representation, it does
  NOT prove the continuous operator-order theorem, and it does NOT prove RH.

  The next analytic obligation is to identify the actual tail increment with a
  limit/integral of these nonnegative finite Gram increments and discharge the
  required convergence/domain conditions without target assumptions.
*)

From Coq Require Import QArith.QArith.
From Coq Require Import Psatz.
From Coq Require Import Lia.

Open Scope Q_scope.

Fixpoint qdot_prefix
    (n : nat)
    (a x : nat -> Q) : Q :=
  match n with
  | O => 0
  | S k => qdot_prefix k a x + a k * x k
  end.

Fixpoint weighted_gram_energy
    (samples dim : nat)
    (weight : nat -> Q)
    (feature : nat -> nat -> Q)
    (x : nat -> Q) : Q :=
  match samples with
  | O => 0
  | S k =>
      weighted_gram_energy k dim weight feature x
      + weight k * (qdot_prefix dim (feature k) x)^2
  end.

Theorem weighted_gram_energy_nonnegative :
  forall
    (samples dim : nat)
    (weight : nat -> Q)
    (feature : nat -> nat -> Q)
    (x : nat -> Q),
    (forall k : nat, (k < samples)%nat -> 0 <= weight k) ->
    0 <= weighted_gram_energy samples dim weight feature x.
Proof.
  induction samples as [|k IH]; intros dim weight feature x Hweight.
  - simpl. lra.
  - simpl.
    assert (Hprefix :
      0 <= weighted_gram_energy k dim weight feature x).
    {
      apply IH.
      intros j Hj.
      apply Hweight.
      lia.
    }
    assert (Hwk : 0 <= weight k).
    {
      apply Hweight.
      lia.
    }
    assert (Hsquare :
      0 <= (qdot_prefix dim (feature k) x)^2).
    {
      nra.
    }
    nra.
Qed.

Definition rank_two_weighted_gram_energy
    (samples dim : nat)
    (weight : nat -> Q)
    (feature_left feature_right : nat -> nat -> Q)
    (x : nat -> Q) : Q :=
  weighted_gram_energy samples dim weight feature_left x
  + weighted_gram_energy samples dim weight feature_right x.

Theorem rank_two_weighted_gram_energy_nonnegative :
  forall
    (samples dim : nat)
    (weight : nat -> Q)
    (feature_left feature_right : nat -> nat -> Q)
    (x : nat -> Q),
    (forall k : nat, (k < samples)%nat -> 0 <= weight k) ->
    0 <=
      rank_two_weighted_gram_energy
        samples dim weight feature_left feature_right x.
Proof.
  intros samples dim weight feature_left feature_right x Hweight.
  unfold rank_two_weighted_gram_energy.
  pose proof
    (weighted_gram_energy_nonnegative
      samples dim weight feature_left x Hweight) as Hleft.
  pose proof
    (weighted_gram_energy_nonnegative
      samples dim weight feature_right x Hweight) as Hright.
  lra.
Qed.

Definition cauchy_feature
    (nodes poles : nat -> Q)
    (sample coordinate : nat) : Q :=
  / (nodes sample + poles coordinate).

Definition CauchyDomainV1
    (samples dim : nat)
    (nodes poles : nat -> Q) : Prop :=
  forall sample coordinate : nat,
    (sample < samples)%nat ->
    (coordinate < dim)%nat ->
    ~ (nodes sample + poles coordinate == 0).

Definition cauchy_stieltjes_rank_two_energy
    (samples dim : nat)
    (weight nodes poles_left poles_right : nat -> Q)
    (x : nat -> Q) : Q :=
  rank_two_weighted_gram_energy
    samples dim weight
    (cauchy_feature nodes poles_left)
    (cauchy_feature nodes poles_right)
    x.

Theorem finite_cauchy_stieltjes_rank_two_psd :
  forall
    (samples dim : nat)
    (weight nodes poles_left poles_right : nat -> Q)
    (x : nat -> Q),
    CauchyDomainV1 samples dim nodes poles_left ->
    CauchyDomainV1 samples dim nodes poles_right ->
    (forall k : nat, (k < samples)%nat -> 0 <= weight k) ->
    0 <=
      cauchy_stieltjes_rank_two_energy
        samples dim weight nodes poles_left poles_right x.
Proof.
  intros samples dim weight nodes poles_left poles_right x
    _Hleft_domain _Hright_domain Hweight.
  unfold cauchy_stieltjes_rank_two_energy.
  apply rank_two_weighted_gram_energy_nonnegative.
  exact Hweight.
Qed.

Inductive ArchTailOrderStatusV1 : Set :=
| FINITE_RANK_TWO_GRAM_PSD_MACHINE_BOUND
| CONTINUOUS_CAUCHY_STIELTJES_REPRESENTATION_NOT_MACHINE_BOUND
| ARCHIMEDEAN_TAIL_OPERATOR_ORDER_NOT_MACHINE_BOUND.

Definition arch_tail_order_status : ArchTailOrderStatusV1 :=
  ARCHIMEDEAN_TAIL_OPERATOR_ORDER_NOT_MACHINE_BOUND.
