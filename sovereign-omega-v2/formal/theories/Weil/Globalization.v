(*
  AEGIS Ω — O₀ globalization obligations v1

  Transparent propositions only. No density, continuity, convergence, or
  global positivity theorem is assumed here.

  This module is expressed entirely over the constructive O₀ real carrier
  defined in AnalyticDefinitions.v. It does not import the classical Coq Reals
  hierarchy.
*)

Require Import AnalyticDefinitions.

Definition FiniteLowerBoundV1
    (QR : FiniteQuadraticFamilyV1)
    (eps : nat -> O0RealV1) : Prop :=
  forall (n : nat) (f : AdmissibleTestFunctionV1),
    O0LeV1 (O0OppV1 (eps n)) (QR n f).

Definition GlobalizationReadyV1
    (QR : FiniteQuadraticFamilyV1)
    (QW : QuadraticFormV1)
    (eps : nat -> O0RealV1) : Prop :=
  pointwise_converges_v1 QR QW /\
  vanishing_nonnegative_error_v1 eps /\
  FiniteLowerBoundV1 QR eps.

Definition GlobalizationTargetV1
    (QW : QuadraticFormV1) : Prop :=
  GlobalWeilPositivityV1 QW.

Theorem finite_lower_bound_v1_specialize :
  forall (QR : FiniteQuadraticFamilyV1) (eps : nat -> O0RealV1),
    FiniteLowerBoundV1 QR eps ->
    forall (n : nat) (f : AdmissibleTestFunctionV1),
      O0LeV1 (O0OppV1 (eps n)) (QR n f).
Proof.
  intros QR eps H n f.
  exact (H n f).
Qed.
