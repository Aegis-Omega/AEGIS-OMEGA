(*
  AEGIS Ω — contract for CoRN -> O₀ derivative remainder image bridge v1.

  This contract checks only the image-level transport of the CoRN
  Derivative_I remainder inequality.  It does not assert a native O₀
  derivative relation or any Guinand--Weil/global/RH result.
*)

Require Import CoRN.ftc.Derivative.
Require Import CoRN.ftc.MoreIntervals.
Require Import CornO0MorphismBridge.
Require Import CanonicalPrimeSourceSum.
Require Import CornO0DerivativeImageBridge.

Definition corn_o0_derivative_I_remainder_image_contract_v1 :
  forall (a b : IR)
         (Hab : a [<] b)
         (F F' : PartIR),
    Derivative_I Hab F F' ->
    forall e : IR,
      [0] [<] e ->
      { d : IR |
        [0] [<] d |
        forall x y : IR,
          Compact (less_leEq _ a b Hab) x ->
          Compact (less_leEq _ a b Hab) y ->
          forall
            (Hx : Dom F x)
            (Hy : Dom F y)
            (Hx' : Dom F' x),
            AbsIR (x[-]y) [<=] d ->
            O0LeV1
              (corn_ir_to_o0_carrier_v1
                (AbsIR
                  (F y Hy
                    [-] F x Hx
                    [-] F' x Hx' [*] (y[-]x))))
              (corn_ir_to_o0_carrier_v1
                (e [*] AbsIR (y[-]x))) } :=
  corn_o0_derivative_I_remainder_image_v1.


Definition corn_o0_derivative_realline_remainder_image_contract_v1 :
  forall (H : proper realline)
         (F F' : PartIR),
    Derivative realline H F F' ->
    forall (a b : IR)
           (Hab : a [<] b)
           (e : IR),
      [0] [<] e ->
      { d : IR |
        [0] [<] d |
        forall x y : IR,
          Compact (less_leEq _ a b Hab) x ->
          Compact (less_leEq _ a b Hab) y ->
          forall
            (Hx : Dom F x)
            (Hy : Dom F y)
            (Hx' : Dom F' x),
            AbsIR (x[-]y) [<=] d ->
            O0LeV1
              (corn_ir_to_o0_carrier_v1
                (AbsIR
                  (F y Hy
                    [-] F x Hx
                    [-] F' x Hx' [*] (y[-]x))))
              (corn_ir_to_o0_carrier_v1
                (e [*] AbsIR (y[-]x))) } :=
  corn_o0_derivative_realline_remainder_image_v1.


Definition canonical_von_mangoldt_o0_remainder_image_contract_v1 :
  forall (H : proper realline)
         (count : nat)
         (L : IR)
         (H_L_pos : [0] [<] L)
         (a b : IR)
         (Hab : a [<] b)
         (e : IR),
    [0] [<] e ->
    { d : IR |
      [0] [<] d |
      forall x y : IR,
        Compact (less_leEq _ a b Hab) x ->
        Compact (less_leEq _ a b Hab) y ->
        forall
          (Hx : Dom
            (canonical_von_mangoldt_source_sum_o0_bridge_v1
              count L H_L_pos) x)
          (Hy : Dom
            (canonical_von_mangoldt_source_sum_o0_bridge_v1
              count L H_L_pos) y)
          (Hx' : Dom
            (canonical_von_mangoldt_derivative_sum_o0_bridge_v1
              count L H_L_pos) x),
          AbsIR (x[-]y) [<=] d ->
          O0LeV1
            (corn_ir_to_o0_carrier_v1
              (AbsIR
                ((canonical_von_mangoldt_source_sum_o0_bridge_v1
                    count L H_L_pos) y Hy
                  [-]
                 (canonical_von_mangoldt_source_sum_o0_bridge_v1
                    count L H_L_pos) x Hx
                  [-]
                 (canonical_von_mangoldt_derivative_sum_o0_bridge_v1
                    count L H_L_pos) x Hx'
                    [*] (y[-]x))))
            (corn_ir_to_o0_carrier_v1
              (e [*] AbsIR (y[-]x))) } :=
  canonical_von_mangoldt_o0_remainder_image_v1.
