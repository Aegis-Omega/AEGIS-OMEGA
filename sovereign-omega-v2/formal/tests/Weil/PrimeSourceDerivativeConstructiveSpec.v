(*
  AEGIS Ω — constructive single-frequency prime-source derivative contract.

  RED-first production contract. The implementation module is intentionally
  absent at the first checkpoint. This contract proves only the reusable CoRN
  IR calculus identity for a scaled sine source; it does not prove O0 trig
  transport, prime-power arithmetic semantics, the explicit formula, global
  Weil positivity, or RH.
*)
Require Import PrimeSourceDerivativeConstructive.

Definition scaled_sine_derivative_constructive_contract_v1 :
  forall (H : proper realline) (a kappa : IR),
    Derivative realline H
      (a{**}(Sine[o](kappa{**}FId)))
      (a{**}((Cosine[o](kappa{**}FId)){*}(kappa{**}[-C-][1]))) :=
  scaled_sine_derivative_constructive_v1.

Check scaled_sine_derivative_constructive_v1.
