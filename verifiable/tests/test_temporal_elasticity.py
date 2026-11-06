import base64
import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from verifiable.temporal_elasticity import (
    duration_to_femtoseconds,
    femtoseconds_to_seconds,
    sum_femtoseconds,
    signed_payload_bytes,
    signed_payload_sha256,
    verify_blp_declared_pair,
    verify_coherence_revival,
    verify_receipt,
    verify_spectral_concentration,
    verify_tau_adaptation,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "temporal-elasticity-receipt.v1.schema.json").read_text())
VECTORS = json.loads((ROOT / "verifiable" / "fixtures" / "temporal_elasticity" / "reference_vectors.v1.json").read_text())


def deterministic_test_pq_verifier(signature, payload):
    """TEST-ONLY deterministic adapter. It is deliberately not a PQ algorithm."""
    expected = base64.b64encode(hashlib.sha256(payload).digest()).decode("ascii")
    return signature["key_id"] == "TEST-ONLY-NONCRYPTOGRAPHIC-ADAPTER" and signature["signature_b64"] == expected


def build_receipt(vector, source_class="SYNTHETIC"):
    receipt = {
        "receipt_type": "TEMPORAL_ELASTICITY_RECEIPT_V1",
        "receipt_version": "1.0.0",
        "specification": "AEGIS_OMEGA_TEMPORAL_ELASTICITY_V1",
        "epistemic_class": "MATHEMATICALLY_BOUNDED_SPECIFICATION",
        "physical_time_deformation": "NOT_CLAIMED",
        "retrocausality": "NOT_ESTABLISHED",
        "macroscopic_time_reversal": "NOT_ESTABLISHED",
        "authority_effect": "NONE",
        "claim_promotion": "FAIL_CLOSED_OUTSIDE_DECLARED_COMPONENT_BOUNDARIES",
        "primary_witness": "VECTOR_VALUED",
        "scalar_score_authority": "ANALYTICS_ONLY",
        "receipt_id": "tew-test-001",
        "created_at": "2026-09-11T20:00:00Z",
        "source": {
            "class": source_class,
            "dataset_digest_sha256": hashlib.sha256(vector["id"].encode()).hexdigest(),
        },
        "uncertainty": {"confidence_level": "0.95", "method": "DECLARED_SYMMETRIC_INTERVAL_TEST_MODEL"},
        "blp": copy.deepcopy(vector["blp"]),
        "spectral": copy.deepcopy(vector["spectral"]),
        "coherence": copy.deepcopy(vector["coherence"]),
        "tau_adaptation": copy.deepcopy(vector["tau_adaptation"]),
        "scalar_score": {"value": "999999999", "status": "ANALYTICS_ONLY"},
        "integrity": {
            "canonicalization": "AEGIS_JSON_CANONICAL_V1",
            "digest_algorithm": "SHA-256",
            "payload_sha256": "0" * 64,
            "signature": {
                "standard": "FIPS_204",
                "algorithm": "ML-DSA",
                "parameter_set": "ML-DSA-65",
                "key_id": "TEST-ONLY-NONCRYPTOGRAPHIC-ADAPTER",
                "signature_b64": "AA==",
            },
        },
    }
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")
    return receipt


def vector(index=0):
    return copy.deepcopy(VECTORS["vectors"][index])


def test_schema_is_valid_and_good_receipt_conforms():
    Draft202012Validator.check_schema(SCHEMA)
    receipt = build_receipt(vector(0))
    errors = list(Draft202012Validator(SCHEMA).iter_errors(receipt))
    assert errors == []


def test_reference_vectors_match_declared_statuses():
    for v in VECTORS["vectors"]:
        assert verify_blp_declared_pair(v["blp"])["status"] == v["expected"]["blp_status"]
        assert verify_spectral_concentration(v["spectral"])["status"] == v["expected"]["spectral_status"]
        assert verify_coherence_revival(v["coherence"])["status"] == v["expected"]["coherence_status"]
        assert verify_tau_adaptation(v["tau_adaptation"])["status"] == v["expected"]["tau_status"]


def test_valid_synthetic_receipt_passes_evidence_but_never_releases_execution():
    result = verify_receipt(build_receipt(vector(0)), pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "PASS"
    assert result["temporal_elasticity_witness_valid"] is True
    assert result["execution_release"] == "BLOCKED"
    assert result["authority_effect"] == "NONE"
    assert result["physical_time_deformation"] == "NOT_CLAIMED"
    assert result["retrocausality"] == "NOT_ESTABLISHED"
    assert result["scalar_score_authority"] == "ANALYTICS_ONLY"


def test_missing_pq_backend_denies_by_default():
    result = verify_receipt(build_receipt(vector(0)))
    assert result["verification"] == "DENY"
    assert "PQ_SIGNATURE_VERIFIER_UNAVAILABLE" in result["reason_codes"]
    assert result["authority_effect"] == "NONE"


def test_digest_tamper_denies():
    receipt = build_receipt(vector(0))
    receipt["blp"]["trace_distances"][2] = "0.99"
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert "PAYLOAD_DIGEST_MISMATCH" in result["reason_codes"]


def test_spectral_anomaly_is_not_tampering_claim_and_denies_tew():
    receipt = build_receipt(vector(0))
    receipt["spectral"]["observed"] = "1.20"
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    gate = result["component_gates"]["spectral"]
    assert result["verification"] == "DENY"
    assert gate["status"] == "SPECTRAL_CONSISTENCY_FAIL"
    assert "TAMPERING" not in json.dumps(result)


def test_declared_pair_backflow_is_not_full_blp_measure_claim():
    result = verify_blp_declared_pair(vector(0)["blp"])
    assert result["status"] == "BLP_BACKFLOW_FOR_DECLARED_PAIR"
    assert "N_BLP" not in result["status"]


def test_nonmonotonic_blp_time_fails_closed():
    receipt = build_receipt(vector(0))
    receipt["blp"]["times_s"] = ["0", "2", "1", "3"]
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert "BLP_TIME_NOT_STRICTLY_INCREASING" in result["reason_codes"]


def test_tau_nonpositive_fails_closed():
    receipt = build_receipt(vector(0))
    receipt["tau_adaptation"]["tau_values_s"][1] = "0"
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert "TAU_VALUE_NONPOSITIVE" in result["reason_codes"]


def test_missing_coherence_basis_fails_closed():
    receipt = build_receipt(vector(0))
    receipt["coherence"]["basis"] = ""
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert "COHERENCE_BASIS_REQUIRED" in result["reason_codes"]


def test_scalar_score_cannot_compensate_for_failed_gate():
    receipt = build_receipt(vector(0))
    receipt["scalar_score"]["value"] = "1e999"
    receipt["spectral"]["s_c"] = "0"
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert result["scalar_score_authority"] == "ANALYTICS_ONLY"
    assert result["authority_effect"] == "NONE"


def test_fips204_profile_mismatch_denies():
    receipt = build_receipt(vector(0))
    receipt["integrity"]["signature"]["algorithm"] = "SLH-DSA"
    receipt["integrity"]["signature"]["parameter_set"] = "SLH-DSA-SHA2-128s"
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert "FIPS_204_SIGNATURE_PROFILE_INVALID" in result["reason_codes"]


def test_float_in_hashed_receipt_is_rejected():
    receipt = build_receipt(vector(0))
    receipt["scalar_score"]["value"] = 1.25
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert result["component_gates"]["integrity"]["gate_passed"] is False


def test_empirical_source_without_trusted_provenance_verifier_denies():
    receipt = build_receipt(vector(0), source_class="EMPIRICAL")
    receipt["source"]["provenance_uri"] = "urn:aegis:test:empirical-placeholder"
    receipt["source"]["external_admission_receipt_sha256"] = "1" * 64
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert "EMPIRICAL_PROVENANCE_VERIFIER_UNAVAILABLE" in result["reason_codes"]


def test_schema_rejects_json_float_numeric_evidence():
    receipt = build_receipt(vector(0))
    receipt["blp"]["trace_distances"][0] = 0.8
    errors = list(Draft202012Validator(SCHEMA).iter_errors(receipt))
    assert errors


def test_undeclared_nested_field_denies_runtime_even_without_schema_call():
    receipt = build_receipt(vector(0))
    receipt["blp"]["undeclared"] = "must-deny"
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "DENY"
    assert any(code.startswith("BLP_UNDECLARED_FIELDS:") for code in result["reason_codes"])


def test_fips205_profile_is_structurally_supported_with_external_adapter():
    receipt = build_receipt(vector(0))
    receipt["integrity"]["signature"]["standard"] = "FIPS_205"
    receipt["integrity"]["signature"]["algorithm"] = "SLH-DSA"
    receipt["integrity"]["signature"]["parameter_set"] = "SLH-DSA-SHAKE-128s"
    result = verify_receipt(receipt, pq_verifier=deterministic_test_pq_verifier)
    assert result["verification"] == "PASS"
    assert result["component_gates"]["integrity"]["status"] == "PQ_SIGNATURE_VERIFIED"


def test_empirical_source_can_only_pass_with_explicit_trusted_provenance_adapter():
    receipt = build_receipt(vector(0), source_class="EMPIRICAL")
    receipt["source"]["provenance_uri"] = "urn:aegis:test:empirical-admitted"
    receipt["source"]["external_admission_receipt_sha256"] = "1" * 64
    receipt["integrity"]["payload_sha256"] = signed_payload_sha256(receipt)
    receipt["integrity"]["signature"]["signature_b64"] = base64.b64encode(
        hashlib.sha256(signed_payload_bytes(receipt)).digest()
    ).decode("ascii")

    result = verify_receipt(
        receipt,
        pq_verifier=deterministic_test_pq_verifier,
        provenance_verifier=lambda source: source["external_admission_receipt_sha256"] == "1" * 64,
    )
    assert result["verification"] == "PASS"
    assert result["authority_effect"] == "NONE"
    assert result["execution_release"] == "BLOCKED"



def test_exact_femtosecond_roundtrip_and_millisecond_sum():
    assert duration_to_femtoseconds("1", "fs") == 1
    assert duration_to_femtoseconds("0.001", "s") == 10**12
    assert duration_to_femtoseconds("1", "ms") == 10**12
    assert duration_to_femtoseconds("-1e-15", "s") == -1
    total = sum_femtoseconds([
        duration_to_femtoseconds("500", "ms"),
        duration_to_femtoseconds("500", "ms"),
        duration_to_femtoseconds("1", "fs"),
    ])
    assert total == 10**15 + 1
    assert femtoseconds_to_seconds(total) == "1.000000000000001"


def test_exact_femtosecond_large_integer_roundtrip():
    # Epoch-sized counts are beyond IEEE-754's safe-integer range.
    ticks = 2**80 + 17
    assert duration_to_femtoseconds(femtoseconds_to_seconds(ticks)) == ticks
    assert duration_to_femtoseconds(femtoseconds_to_seconds(-ticks)) == -ticks


@pytest.mark.parametrize("value,unit", [
    ("0.1", "fs"),
    ("0.0000000000000001", "s"),
    ("0.0000000000001", "ms"),
])
def test_sub_femtosecond_precision_fails_closed(value, unit):
    with pytest.raises(ValueError, match="SUB_FEMTOSECOND_PRECISION"):
        duration_to_femtoseconds(value, unit)


@pytest.mark.parametrize("value,unit", [
    (1.0, "s"),
    (True, "fs"),
    ("NaN", "s"),
    ("Infinity", "s"),
    ("1", "fortnight"),
])
def test_invalid_exact_duration_fails_closed(value, unit):
    with pytest.raises(ValueError, match="INVALID_EXACT_DURATION"):
        duration_to_femtoseconds(value, unit)


@pytest.mark.parametrize("ticks", [True, 1.0, "1"])
def test_invalid_femtosecond_integer_fails_closed(ticks):
    with pytest.raises(ValueError, match="INVALID_FEMTOSECOND_TICKS"):
        femtoseconds_to_seconds(ticks)
    with pytest.raises(ValueError, match="INVALID_FEMTOSECOND_TICKS"):
        sum_femtoseconds([1, ticks])


def test_temporal_verifier_distinguishes_adjacent_femtosecond_timestamps():
    times = [femtoseconds_to_seconds(i) for i in (0, 1, 2)]
    assert times == ["0", "0.000000000000001", "0.000000000000002"]
    evidence = {"times_s": times, "tau_values_s": ["1", "1", "1"], "epsilon": "0"}
    valid = verify_tau_adaptation(evidence)
    assert valid["gate_passed"] is True
    assert valid["status"] == "NO_NUMERICAL_ADAPTATION_OBSERVED"
    evidence["times_s"] = [times[0], times[2], times[1]]
    invalid = verify_tau_adaptation(evidence)
    assert invalid["gate_passed"] is False
    assert "TAU_TIME_NOT_STRICTLY_INCREASING" in invalid["reason_codes"]
