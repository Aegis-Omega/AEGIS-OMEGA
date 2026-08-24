(*
  AEGIS Ω — O₀ analytic vocabulary v1

  This file defines only the real-analysis carrier needed to state the
  finite-to-limit obligations. It does NOT identify this v1 carrier with every
  classical formulation of Weil's admissible test-function class, and it does
  NOT define the Riemann zeta function or RH.

  Trust-boundary note:
  - the load-bearing vocabulary uses only Coq's Reals interface here;
  - Coquelicot is probed separately and is not imported into this core module,
    because the first dependency probe exposed additional global assumptions.
*)

From Coq Require Import Reals.
From Coq Require Import Lra.

Open Scope R_scope.

Record AdmissibleTestFunctionV1 := {
  test_function_v1 :> R -> R;
  support_radius_v1 : R;
  support_radius_nonnegative_v1 : 0 <= support_radius_v1;
  compact_support_v1 :
    forall x : R,
      Rabs x > support_radius_v1 ->
      test_function_v1 x = 0;
  continuous_test_function_v1 : continuity test_function_v1
}.

Definition QuadraticFormV1 := AdmissibleTestFunctionV1 -> R.
Definition FiniteQuadraticFamilyV1 := nat -> QuadraticFormV1.

Definition pointwise_converges_v1
    (QR : FiniteQuadraticFamilyV1)
    (QW : QuadraticFormV1) : Prop :=
  forall (f : AdmissibleTestFunctionV1) (eta : R),
    0 < eta ->
    exists N : nat,
      forall n : nat,
        (N <= n)%nat ->
        Rabs (QR n f - QW f) < eta.

Definition vanishing_nonnegative_error_v1
    (eps : nat -> R) : Prop :=
  (forall n : nat, 0 <= eps n) /\
  (forall eta : R,
      0 < eta ->
      exists N : nat,
        forall n : nat,
          (N <= n)%nat ->
          eps n < eta).

Definition GlobalWeilPositivityV1
    (QW : QuadraticFormV1) : Prop :=
  forall f : AdmissibleTestFunctionV1, 0 <= QW f.

Theorem global_weil_positivity_v1_pointwise :
  forall (QW : QuadraticFormV1),
    GlobalWeilPositivityV1 QW ->
    forall f : AdmissibleTestFunctionV1, 0 <= QW f.
Proof.
  intros QW H f.
  exact (H f).
Qed.
