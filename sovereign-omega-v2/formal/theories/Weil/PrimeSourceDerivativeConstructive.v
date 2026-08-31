(*
  AEGIS Ω — constructive single-frequency prime-source derivative v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  This module proves only the reusable CoRN IR calculus identity

      d/dx [ a * sin(kappa * x) ]
        = a * (cos(kappa * x) * kappa).

  It does not identify CoRN IR with AEGIS O0, does not prove that sine or
  cosine commute with the O0 carrier morphism, does not formalize prime-power
  arithmetic weights, does not prove a finite prime-source sum, the
  Guinand-Weil explicit formula, global Weil positivity, or RH.
*)

Require Import CoRN.transc.Trigonometric.
Require Import CoRN.tactics.DiffTactics3.

Theorem scaled_sine_derivative_constructive_v1 :
  forall (H : proper realline) (a kappa : IR),
    Derivative realline H
      (a{**}(Sine[o](kappa{**}FId)))
      (a{**}((Cosine[o](kappa{**}FId)){*}(kappa{**}[-C-][1]))).
Proof.
  intros H a kappa.
  assert (Dsin : Derivative realline H Sine Cosine).
  { apply Derivative_Sin. }
  Derivative_Help.
  FEQ.
Qed.
