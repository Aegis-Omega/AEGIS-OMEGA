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


def test_state_space_surrogate_refutation_is_machine_readable_without_closing_w6():
    with open("research/rh/proof-obligations-v1.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    entry = next(
        item
        for item in payload["refutations"]
        if item["id"] == "FINITE-CUTOFF-STATE-SPACE-BOUNDARY-V1"
    )
    assert entry["target_obligation"] == "W6_GuinandWeilOperatorIdentity"
    assert entry["classification"] == "REFUTED_ROUTE_UNDER_STATED_SURROGATE_SEMANTICS"
    assert entry["verified_source_sha"] == "e7d9009233ea69631263853bbf9ecffa2454e34a"
    assert entry["refutes"] == "FINITE_PRIME_CUTOFF_MULTIPLIER_POSITIVITY_ON_COMPACT_SPECTRAL_CCINFINITY_ZERO_MOMENT_SURROGATE"
    assert "CLASSICAL_PALEY_WIENER_WEIL_ADMISSIBLE_SPACE" in entry["does_not_refute"]
    assert entry["does_not_close_obligation"] is True

    w6 = next(item for item in payload["proof_obligations"] if item["id"] == "W6_GuinandWeilOperatorIdentity")
    assert w6["status"] == "OPEN"


def test_formal_status_without_exact_proof_kernel_receipt_is_rejected(tmp_path):
    source = "research/rh/proof-obligations-v1.json"
    with open(source, "r", encoding="utf-8") as f:
        payload = json.load(f)
    payload["proof_obligations"][0]["status"] = "FORMALLY_VERIFIED"
    payload["proof_obligations"][0]["proof_receipt"] = None

    tampered = tmp_path / "tampered-ledger.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="requires proof_receipt"):
        RHObligationLedger.from_json_file(tampered)


def test_top_level_declared_verdict_cannot_promote_gate(tmp_path):
    source = "research/rh/proof-obligations-v1.json"
    with open(source, "r", encoding="utf-8") as f:
        payload = json.load(f)
    payload["declared_verdict"] = "RH_PROVEN_FORMALLY"

    tampered = tmp_path / "prose-promoted-ledger.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    result = RHObligationLedger.from_json_file(tampered).verify_final_closure()
    assert result["verdict"] == "RH_NOT_PROVEN"
    assert result["gate_status"] == "FAIL_CLOSED"
