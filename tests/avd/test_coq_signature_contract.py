from __future__ import annotations

from scripts.avd.coq_signature_contract import build_signature_contract


def test_signature_contract_locks_load_bearing_theorem_types() -> None:
    text = build_signature_contract()
    assert "Require Import CornO0MorphismBridge." in text
    assert "Definition avd_sig_rat_v1 :" in text
    assert "forall q : Q," in text
    assert "corn_ir_to_o0_carrier_v1 (inj_Q IR q)" in text
    assert "CR_of_Q O0RealsV1 q" in text
    assert ":= corn_ir_to_o0_preserves_rat_v1." in text

    assert "Definition avd_sig_strict_v1 :" in text
    assert "x [<] y ->" in text
    assert "O0LtV1" in text
    assert ":= corn_ir_to_o0_strict_v1." in text

    assert "Definition avd_sig_zero_v1 :" in text
    assert "Definition avd_sig_one_v1 :" in text
    assert "Definition avd_sig_plus_v1 :" in text
    assert "Definition avd_sig_mult_v1 :" in text
    assert "Definition avd_sig_le_v1 :" in text
    assert "Fail Check corn_ir_to_o0_completion_equivalence_v1." in text


def test_signature_contract_covers_all_seven_production_theorems() -> None:
    text = build_signature_contract()
    for theorem in (
        "corn_ir_to_o0_preserves_rat_v1",
        "corn_ir_to_o0_strict_v1",
        "corn_ir_to_o0_preserves_zero_v1",
        "corn_ir_to_o0_preserves_one_v1",
        "corn_ir_to_o0_preserves_plus_v1",
        "corn_ir_to_o0_preserves_mult_v1",
        "corn_ir_to_o0_preserves_le_v1",
    ):
        assert f":= {theorem}." in text
