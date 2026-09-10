#!/usr/bin/env python3
import unittest

from gravity_quantum.external_adapter_v5 import (
    CONTRACT_CSV_BYTES,
    EXPECTED_COLUMNS,
    build_dataset_candidate,
    parse_point_csv,
)


class TestExternalDatasetAdapterV5(unittest.TestCase):
    def test_contract_csv_parses_exact_integer_scaled_points(self):
        points = parse_point_csv(CONTRACT_CSV_BYTES)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["point_id"], "fixture-p0")
        self.assertEqual(points[0]["time_us"], 500)
        self.assertEqual(points[0]["phase_microrad"], -250000)
        self.assertEqual(points[0]["phase_sigma_microrad"], 10000)
        self.assertEqual(points[0]["control_ratio_ppm"], 500000)

    def test_decimal_numeric_input_is_rejected(self):
        bad = CONTRACT_CSV_BYTES.replace(b"500,-250000", b"500.0,-250000")
        with self.assertRaises(ValueError):
            parse_point_csv(bad)

    def test_missing_column_is_rejected(self):
        header = b",".join(c.encode() for c in EXPECTED_COLUMNS[:-1]) + b"\n"
        row = b"p0,500,-250000,10000,500000\n"
        with self.assertRaises(ValueError):
            parse_point_csv(header + row)

    def test_extra_column_is_rejected(self):
        bad = CONTRACT_CSV_BYTES.replace(
            b"calibration_epoch_id\n", b"calibration_epoch_id,extra\n"
        ).replace(b"CAL-V5-TEST\n", b"CAL-V5-TEST,x\n")
        with self.assertRaises(ValueError):
            parse_point_csv(bad)

    def test_candidate_binds_exact_source_bytes(self):
        a = build_dataset_candidate(CONTRACT_CSV_BYTES, evidence_origin="TEST_FIXTURE")
        modified = CONTRACT_CSV_BYTES.replace(b"-250000", b"-250001", 1)
        b = build_dataset_candidate(modified, evidence_origin="TEST_FIXTURE")
        self.assertNotEqual(
            a["batch"]["source_binding"]["source_sha256"],
            b["batch"]["source_binding"]["source_sha256"],
        )
        self.assertNotEqual(a["batch"]["batch_sha256"], b["batch"]["batch_sha256"])

    def test_test_fixture_candidate_cannot_release_empirical_analysis(self):
        candidate = build_dataset_candidate(
            CONTRACT_CSV_BYTES,
            evidence_origin="TEST_FIXTURE",
        )
        self.assertEqual(candidate["adapter_status"], "CANDIDATE_ONLY")
        self.assertEqual(candidate["release_gate"]["decision"], "BLOCKED")
        self.assertEqual(candidate["release_gate"]["empirical_fit_release"], "BLOCKED")
        self.assertEqual(candidate["authority_effect"], "NONE")

    def test_external_origin_without_enrolled_receipts_still_cannot_release(self):
        candidate = build_dataset_candidate(
            CONTRACT_CSV_BYTES,
            evidence_origin="EXTERNAL_EXPERIMENTAL_SOURCE",
        )
        self.assertEqual(candidate["release_gate"]["decision"], "BLOCKED")
        self.assertIn(
            "NO_TRUSTED_VERIFICATION_RECEIPT_ENROLLED",
            candidate["release_gate"]["reason_codes"],
        )
        self.assertEqual(candidate["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
