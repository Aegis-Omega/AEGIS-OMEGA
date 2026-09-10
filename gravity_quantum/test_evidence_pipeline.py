#!/usr/bin/env python3
from __future__ import annotations

from gravity_quantum.evidence_pipeline import (
    PRIMARY_DATE,
    PRIMARY_DOI,
    build_chain,
    classify_claim,
    receipt,
)


def test_chain_certifies_and_is_deterministic():
    a = build_chain()
    b = build_chain()
    assert a.certify()["is_valid"] is True
    assert b.certify()["is_valid"] is True
    assert a.terminal_hash() == b.terminal_hash()


def test_primary_source_identity_is_locked():
    r = receipt()
    source = r["stages"][0]["output"]
    assert source["doi"] == PRIMARY_DOI == "10.1126/sciadv.aec8045"
    assert source["published_date"] == PRIMARY_DATE == "2026-09-02"
    assert source["source_kind"] == "PRIMARY_PEER_REVIEWED"


def test_observation_and_interpretation_are_separate_stages():
    r = receipt()
    names = [s["stage"] for s in r["stages"]]
    assert names.index("OBSERVATION") < names.index("MODEL_CONSISTENCY")
    assert names.index("MODEL_CONSISTENCY") < names.index("INTERPRETATION_DEBATE")


def test_quantum_gravity_promotion_is_fail_closed():
    d = classify_claim("quantum_gravity_proven", ["OBSERVED", "SUPPORTED"])
    assert d["decision"] == "DENY"
    assert d["admitted_status"] == "NOT_TESTED"
    assert d["authority_effect"] == "NONE"
    assert "NO_DIRECT_QUANTUM_GRAVITY_EVIDENCE" in d["reason_codes"]


def test_allowed_low_energy_consistency_claim_is_bounded():
    d = classify_claim(
        "equivalence_principle_consistent_in_reported_low_energy_quantum_regime",
        ["OBSERVED", "SUPPORTED"],
    )
    assert d["decision"] == "ADMIT_BOUNDED_CLAIM"
    assert d["admitted_status"] == "SUPPORTED"
    assert d["authority_effect"] == "EPISTEMIC_ONLY"


def test_unknown_claim_cannot_self_register():
    d = classify_claim("general_relativity_proven_at_all_quantum_scales", ["OBSERVED"])
    assert d["decision"] == "DENY"
    assert d["admitted_status"] == "OPEN"
    assert d["authority_effect"] == "NONE"


def test_unknown_evidence_status_is_rejected():
    d = classify_claim("predicted_free_fall_quantum_phase_observed", ["MAGIC"])
    assert d["decision"] == "DENY"
    assert d["authority_effect"] == "NONE"
    assert d["reason_codes"] == ["UNKNOWN_EVIDENCE_STATUS"]


def test_interpretation_tamper_is_localized():
    chain = build_chain()
    target = next(r for r in chain.records if r.stage == "INTERPRETATION_DEBATE")
    target.output["authority_effect"] = "GRANT"
    cert = chain.certify()
    assert cert["is_valid"] is False
    assert cert["broken_at"] == "INTERPRETATION_DEBATE"


def test_receipt_contains_no_floats():
    def walk(v):
        if isinstance(v, float):
            raise AssertionError("float leaked into hashed/receipt state")
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(receipt())


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)}/{len(tests)}")
