from __future__ import annotations

import unittest

from gravity_quantum_measurement import (
    REQUIRED_NUISANCE_CHANNELS,
    evaluate_witness,
    validate_nuisance,
    validate_replication,
)

HEX = "a" * 64


def nuisance_fixture(status="PASS"):
    return {
        "schema": "AEGIS_GQ_NUISANCE_RECEIPT_V1",
        "controls": {
            name: {"status": status, "evidence_sha256": HEX}
            for name in REQUIRED_NUISANCE_CHANNELS
        },
        "authority_effect": "NONE",
    }


class GravityQuantumMeasurementTests(unittest.TestCase):
    def test_missing_nuisance_channel_denies(self):
        receipt = nuisance_fixture()
        del receipt["controls"]["electrostatic_patch"]
        result = validate_nuisance(receipt)
        self.assertEqual(result["status"], "DENY")
        self.assertIn("electrostatic_patch", result["missing"])

    def test_failed_nuisance_channel_denies(self):
        receipt = nuisance_fixture()
        receipt["controls"]["magnetic"]["status"] = "FAIL"
        result = validate_nuisance(receipt)
        self.assertEqual(result["status"], "DENY")
        self.assertTrue(result["failures"])

    def test_point_estimate_without_uncertainty_clearance_denies(self):
        receipt = {
            "schema": "AEGIS_GQ_ENTANGLEMENT_WITNESS_RECEIPT_V1",
            "measurement_receipt_sha256": HEX,
            "estimate": "-0.01",
            "total_uncertainty": "0.02",
            "threshold": "0",
            "decision_rule": "ESTIMATE_PLUS_UNCERTAINTY_LT_THRESHOLD",
            "authority_effect": "NONE",
        }
        result = evaluate_witness(receipt)
        self.assertEqual(result["status"], "DENY")
        self.assertEqual(result["upper_bound"], "0.01")

    def test_one_sided_witness_upper_bound_can_pass_synthetic_control(self):
        receipt = {
            "schema": "AEGIS_GQ_ENTANGLEMENT_WITNESS_RECEIPT_V1",
            "measurement_receipt_sha256": HEX,
            "estimate": "-0.03",
            "total_uncertainty": "0.01",
            "threshold": "0",
            "decision_rule": "ESTIMATE_PLUS_UNCERTAINTY_LT_THRESHOLD",
            "authority_effect": "NONE",
        }
        result = evaluate_witness(receipt)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["upper_bound"], "-0.02")
        self.assertEqual(result["authority_effect"], "NONE")

    def test_same_apparatus_or_same_analysis_is_not_independent_replication(self):
        primary = {
            "schema": "AEGIS_GQ_REPLICATION_RECEIPT_V1",
            "status": "PASS",
            "apparatus_id": "A",
            "analysis_implementation_sha256": "1" * 64,
            "same_preregistered_claim": True,
            "authority_effect": "NONE",
        }
        same = dict(primary)
        result = validate_replication(primary, same)
        self.assertEqual(result["status"], "DENY")
        self.assertFalse(result["independent"])

    def test_distinct_apparatus_and_analysis_can_pass_synthetic_replication(self):
        primary = {
            "schema": "AEGIS_GQ_REPLICATION_RECEIPT_V1",
            "status": "PASS",
            "apparatus_id": "A",
            "analysis_implementation_sha256": "1" * 64,
            "same_preregistered_claim": True,
            "authority_effect": "NONE",
        }
        replication = {
            "schema": "AEGIS_GQ_REPLICATION_RECEIPT_V1",
            "status": "PASS",
            "apparatus_id": "B",
            "analysis_implementation_sha256": "2" * 64,
            "same_preregistered_claim": True,
            "authority_effect": "NONE",
        }
        result = validate_replication(primary, replication)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["independent"])
        self.assertEqual(result["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
