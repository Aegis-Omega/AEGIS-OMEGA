(*
  AEGIS Ω — CoRN -> O₀ derivative remainder image bridge v1

  LOCAL CANDIDATE / FORMAL_MATH_EVIDENCE_ONLY / NOT_YET_KERNEL_REPLAYED.

  This module transports only the load-bearing Derivative_I remainder
  inequality through the already proved CoRN IR -> O₀ order-preserving map.

  It does NOT:
  - define an independent/native O₀ derivative;
  - prove agreement with an independent O₀ sine/cosine implementation;
  - establish the Guinand--Weil explicit formula;
  - prove global Weil positivity, the Weil criterion, or RH.
*)

Require Import CoRN.ftc.Derivative.
Require Import CoRN.ftc.MoreIntervals.
Require Import CornO0MorphismBridge.
Require Import CanonicalPrimeSourceSum.

Theorem corn_o0_derivative_I_remainder_image_v1 :
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
                (e [*] AbsIR (y[-]x))) }.
Proof.
  intros a b Hab F F' Hder e He.
  destruct Hder as [_ [_ Hremainder]].
  destruct (Hremainder e He) as [d Hd Hbound].
  exists d.
  - exact Hd.
  - intros x y HxI HyI Hx Hy Hx' Hxy.
    apply corn_ir_to_o0_preserves_le_v1.
    exact (Hbound x y HxI HyI Hx Hy Hx' Hxy).
Qed.


(* Specialization to CoRN's global derivative on the whole real line.
   This is the adapter needed by the existing #351/#361 theorem shape. *)
Theorem corn_o0_derivative_realline_remainder_image_v1 :
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
                (e [*] AbsIR (y[-]x))) }.
Proof.
  intros H F F' Hder a b Hab e He.
  destruct Hder as [_ [_ Hlocal]].
  assert (HI :
    included (Compact (less_leEq _ a b Hab)) realline).
  {
    intros z Hz.
    constructor.
  }
  exact
    (corn_o0_derivative_I_remainder_image_v1
      a b Hab F F'
      (Hlocal a b Hab HI)
      e He).
Qed.


(* Concrete binding to the already machine-checked canonical von Mangoldt
   finite source.  This prevents the generic adapter from being mistaken for
   a connection to the arithmetic proofline unless that actual theorem fits. *)
Definition canonical_von_mangoldt_source_sum_o0_bridge_v1
    (count : nat)
    (L : IR)
    (H_L_pos : [0] [<] L) : PartIR :=
  FSumx count
    (fun i _ =>
      canonical_von_mangoldt_source_term_v1 L H_L_pos i).

Definition canonical_von_mangoldt_derivative_sum_o0_bridge_v1
    (count : nat)
    (L : IR)
    (H_L_pos : [0] [<] L) : PartIR :=
  FSumx count
    (fun i _ =>
      canonical_von_mangoldt_derivative_term_raw_v1 L H_L_pos i).

Theorem canonical_von_mangoldt_o0_remainder_image_v1 :
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
              (e [*] AbsIR (y[-]x))) }.
Proof.
  intros H count L H_L_pos a b Hab e He.
  unfold canonical_von_mangoldt_source_sum_o0_bridge_v1.
  unfold canonical_von_mangoldt_derivative_sum_o0_bridge_v1.
  exact
    (corn_o0_derivative_realline_remainder_image_v1
      H
      (FSumx count
        (fun i _ =>
          canonical_von_mangoldt_source_term_v1 L H_L_pos i))
      (FSumx count
        (fun i _ =>
          canonical_von_mangoldt_derivative_term_raw_v1 L H_L_pos i))
      (canonical_von_mangoldt_finite_sum_shared_scale_derivative_constructive_v1
        H count L H_L_pos)
      a b Hab e He).
Qed.
