import json

import pytest

from harness.sdk.rh_obligation_gate import RHObligationLedger


def test_machine_readable_rh_ledger_matches_fail_closed_default():
    ledger = RHObligationLedger.from_json_file("research/rh/proof-obligations-v1.json")
    result = ledger.verify_final_closure()

    assert result["verdict"] == "RH_NOT_PROVEN"
    assert result["gate_status"] == "FAIL_CLOSED"
    assert "W8_DensityContinuityCoverage" in result["open_obligations"]
    assert "W10_FinalRiemannHypothesis" in result["open_obligations"]


def test_formal_status_without_exact_proof_kernel_receipt_is_rejected(tmp_path):
    source = "research/rh/proof-obligations-v1.json"
    payload = json.load(open(source, "r", encoding="utf-8"))
    payload["proof_obligations"][0]["status"] = "FORMALLY_VERIFIED"
    payload["proof_obligations"][0]["proof_receipt"] = None

    tampered = tmp_path / "tampered-ledger.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="requires proof_receipt"):
        RHObligationLedger.from_json_file(tampered)


def test_top_level_declared_verdict_cannot_promote_gate(tmp_path):
    source = "research/rh/proof-obligations-v1.json"
    payload = json.load(open(source, "r", encoding="utf-8"))
    payload["declared_verdict"] = "RH_PROVEN_FORMALLY"

    tampered = tmp_path / "prose-promoted-ledger.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    result = RHObligationLedger.from_json_file(tampered).verify_final_closure()
    assert result["verdict"] == "RH_NOT_PROVEN"
    assert result["gate_status"] == "FAIL_CLOSED"
