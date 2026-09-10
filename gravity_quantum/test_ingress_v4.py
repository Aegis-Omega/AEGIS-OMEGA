#!/usr/bin/env python3
import copy
import unittest

from verifiable.chain import canon, sha256_hex
from gravity_quantum import ingress_v4
from gravity_quantum.ingress_v4 import (
    CONTRACT_FIXTURE_BYTES,
    build_calibration_binding,
    build_contract_fixture,
    build_point,
    build_point_batch,
    build_source_binding,
    fit_release_gate,
    validate_ingress,
)


def rehash_batch(batch):
    payload = {k: copy.deepcopy(v) for k, v in batch.items() if k != "batch_sha256"}
    batch["batch_sha256"] = sha256_hex(canon(payload))
    return batch


def self_consistent_receipt(subject_kind, subject_sha256):
    receipt = {
        "schema": ingress_v4.VERIFICATION_RECEIPT_SCHEMA,
        "verifier_id": "CALLER_AUTHORED_FAKE",
        "subject_kind": subject_kind,
        "subject_sha256": subject_sha256,
        "result": "VERIFIED",
        "method": "CALLER_ASSERTION_ONLY",
        "authority_effect": "NONE",
    }
    receipt["receipt_sha256"] = sha256_hex(canon(receipt))
    return receipt


class TestPointLevelIngressV4(unittest.TestCase):
    def test_source_bytes_are_bound_by_sha256(self):
        source = build_source_binding(
            CONTRACT_FIXTURE_BYTES,
            source_uri="fixture://qgi-v4",
            media_type="text/csv",
            evidence_origin="TEST_FIXTURE",
        )
        self.assertEqual(len(source["source_sha256"]), 64)
        changed = build_source_binding(
            CONTRACT_FIXTURE_BYTES + b"x",
            source_uri="fixture://qgi-v4",
            media_type="text/csv",
            evidence_origin="TEST_FIXTURE",
        )
        self.assertNotEqual(source["source_sha256"], changed["source_sha256"])

    def test_float_point_value_is_rejected(self):
        with self.assertRaises(ValueError):
            build_point(
                point_id="p0",
                time_us=1000.0,
                phase_microrad=100,
                phase_sigma_microrad=10,
                control_ratio_ppm=1000000,
                calibration_epoch_id="CAL-V4-TEST",
            )

    def test_nonpositive_uncertainty_is_rejected(self):
        with self.assertRaises(ValueError):
            build_point(
                point_id="p0",
                time_us=1000,
                phase_microrad=100,
                phase_sigma_microrad=0,
                control_ratio_ppm=1000000,
                calibration_epoch_id="CAL-V4-TEST",
            )

    def test_calibration_epoch_mismatch_is_rejected(self):
        fixture = build_contract_fixture()
        wrong = copy.deepcopy(fixture["points"][0])
        wrong["calibration_epoch_id"] = "OTHER-EPOCH"
        with self.assertRaises(ValueError):
            build_point_batch(
                fixture["source_binding"],
                fixture["calibration_binding"],
                [wrong],
            )

    def test_duplicate_point_ids_are_rejected(self):
        fixture = build_contract_fixture()
        point = fixture["points"][0]
        with self.assertRaises(ValueError):
            build_point_batch(
                fixture["source_binding"],
                fixture["calibration_binding"],
                [point, copy.deepcopy(point)],
            )

    def test_tampered_batch_digest_is_rejected(self):
        fixture = build_contract_fixture()
        batch = fixture["batch"]
        forged = copy.deepcopy(batch)
        forged["points"][0]["phase_microrad"] += 1
        result = validate_ingress(forged, CONTRACT_FIXTURE_BYTES)
        self.assertEqual(result["decision"], "DENY")
        self.assertIn("BATCH_DIGEST_MISMATCH", result["reason_codes"])

    def test_source_digest_mismatch_is_rejected(self):
        fixture = build_contract_fixture()
        result = validate_ingress(fixture["batch"], CONTRACT_FIXTURE_BYTES + b"tamper")
        self.assertEqual(result["decision"], "DENY")
        self.assertIn("SOURCE_DIGEST_MISMATCH", result["reason_codes"])

    def test_test_fixture_cannot_release_empirical_fit(self):
        fixture = build_contract_fixture()
        gate = fit_release_gate(fixture["batch"], CONTRACT_FIXTURE_BYTES)
        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertEqual(gate["empirical_fit_release"], "BLOCKED")
        self.assertIn("TEST_FIXTURE_NOT_EMPIRICAL_SOURCE", gate["reason_codes"])
        self.assertEqual(gate["authority_effect"], "NONE")

    def test_contract_fixture_is_structurally_valid_but_non_empirical(self):
        fixture = build_contract_fixture()
        validation = validate_ingress(fixture["batch"], CONTRACT_FIXTURE_BYTES)
        self.assertEqual(validation["decision"], "CONTRACT_VALID")
        self.assertEqual(validation["evidence_origin"], "TEST_FIXTURE")
        self.assertEqual(validation["authority_effect"], "NONE")

    def test_caller_asserted_verified_flags_cannot_unlock_fit(self):
        fixture = build_contract_fixture()
        forged = copy.deepcopy(fixture["batch"])
        forged["source_binding"]["evidence_origin"] = "EXTERNAL_EXPERIMENTAL_SOURCE"
        forged["source_binding"]["independent_source_verification"] = "VERIFIED"
        forged["calibration_binding"]["independent_calibration_verification"] = "VERIFIED"
        rehash_batch(forged)

        gate = fit_release_gate(forged, CONTRACT_FIXTURE_BYTES)
        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertEqual(gate["empirical_fit_release"], "BLOCKED")
        self.assertIn("TRUSTED_VERIFICATION_RECEIPT_MISSING", gate["reason_codes"])
        self.assertEqual(gate["authority_effect"], "NONE")

    def test_repository_enrolled_receipt_digest_registry_is_immutable_and_empty(self):
        registry = ingress_v4.TRUSTED_VERIFICATION_RECEIPT_DIGESTS
        self.assertIsInstance(registry, frozenset)
        self.assertEqual(registry, frozenset())

    def test_self_consistent_unenrolled_receipts_cannot_unlock_fit(self):
        fixture = build_contract_fixture()
        forged = copy.deepcopy(fixture["batch"])
        forged["source_binding"]["evidence_origin"] = "EXTERNAL_EXPERIMENTAL_SOURCE"
        rehash_batch(forged)
        receipts = [
            self_consistent_receipt(
                "SOURCE_BYTES", forged["source_binding"]["source_sha256"]
            ),
            self_consistent_receipt(
                "CALIBRATION_CONFIG", forged["calibration_binding"]["config_sha256"]
            ),
        ]

        gate = fit_release_gate(forged, CONTRACT_FIXTURE_BYTES, receipts)
        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertEqual(gate["empirical_fit_release"], "BLOCKED")
        self.assertIn("UNTRUSTED_VERIFICATION_RECEIPT", gate["reason_codes"])
        self.assertEqual(gate["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
