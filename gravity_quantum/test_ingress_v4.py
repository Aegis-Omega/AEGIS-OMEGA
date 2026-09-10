#!/usr/bin/env python3
import copy
import unittest

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
