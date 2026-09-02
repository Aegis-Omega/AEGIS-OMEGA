from __future__ import annotations


def build_signature_contract() -> str:
    """Return verifier-owned exact type assignments for the A1c public API.

    `Check theorem_name` is insufficient because a candidate can retain a name
    while weakening its proposition. These definitions force Coq conversion
    against the preregistered load-bearing statements.
    """
    return r'''Set Coqtop Exit On Error.
From Coq Require Import QArith.
Require Import CornO0MorphismBridge.

Definition avd_sig_rat_v1 :
  forall q : Q,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (inj_Q IR q))
      (CR_of_Q O0RealsV1 q)
  := corn_ir_to_o0_preserves_rat_v1.

Definition avd_sig_strict_v1 :
  forall x y : IR,
    x [<] y ->
    O0LtV1
      (corn_ir_to_o0_carrier_v1 x)
      (corn_ir_to_o0_carrier_v1 y)
  := corn_ir_to_o0_strict_v1.

Definition avd_sig_zero_v1 :
  O0EqV1
    (corn_ir_to_o0_carrier_v1 [0])
    O0ZeroV1
  := corn_ir_to_o0_preserves_zero_v1.

Definition avd_sig_one_v1 :
  O0EqV1
    (corn_ir_to_o0_carrier_v1 [1])
    (CR_of_Q O0RealsV1 1%Q)
  := corn_ir_to_o0_preserves_one_v1.

Definition avd_sig_plus_v1 :
  forall x y : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (x [+] y))
      (CRplus O0RealsV1
        (corn_ir_to_o0_carrier_v1 x)
        (corn_ir_to_o0_carrier_v1 y))
  := corn_ir_to_o0_preserves_plus_v1.

Definition avd_sig_mult_v1 :
  forall x y : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (x [*] y))
      (CRmult O0RealsV1
        (corn_ir_to_o0_carrier_v1 x)
        (corn_ir_to_o0_carrier_v1 y))
  := corn_ir_to_o0_preserves_mult_v1.

Definition avd_sig_le_v1 :
  forall x y : IR,
    x [<=] y ->
    O0LeV1
      (corn_ir_to_o0_carrier_v1 x)
      (corn_ir_to_o0_carrier_v1 y)
  := corn_ir_to_o0_preserves_le_v1.

Fail Check corn_ir_to_o0_completion_equivalence_v1.
'''
