#!/usr/bin/env python3
import copy
import unittest

from gravity_quantum.cudaq_phase_v1 import (
    DEFAULT_ANGLE_MICRORAD,
    EXPECTATION_SCALE,
    build_phase_receipt,
    classical_x_expectation_scaled,
    run_phase_probe,
)


class TestCudaQPhaseV1(unittest.TestCase):
    def test_classical_oracle_zero_phase_is_plus_x(self):
        self.assertEqual(classical_x_expectation_scaled(0), EXPECTATION_SCALE)

    def test_invalid_float_angle_is_rejected(self):
        with self.assertRaises(ValueError):
            classical_x_expectation_scaled(0.5)

    def test_qpp_cpu_matches_classical_oracle(self):
        for angle in DEFAULT_ANGLE_MICRORAD:
            point = run_phase_probe(angle)
            self.assertLessEqual(point["abs_error_scaled"], point["tolerance_scaled"])

    def test_qpp_cpu_observe_is_deterministic(self):
        first = [run_phase_probe(a) for a in DEFAULT_ANGLE_MICRORAD]
        second = [run_phase_probe(a) for a in DEFAULT_ANGLE_MICRORAD]
        self.assertEqual(first, second)

    def test_receipt_has_no_floats(self):
        def contains_float(value):
            if isinstance(value, float):
                return True
            if isinstance(value, dict):
                return any(contains_float(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return any(contains_float(v) for v in value)
            return False

        self.assertFalse(contains_float(build_phase_receipt()))

    def test_receipt_is_deterministic(self):
        self.assertEqual(build_phase_receipt(), build_phase_receipt())

    def test_receipt_is_research_only(self):
        receipt = build_phase_receipt()
        self.assertEqual(receipt["scope"], "RESEARCH_ONLY_COMPUTATIONAL_CROSSCHECK")
        self.assertEqual(receipt["physics_claim_effect"], "NONE")
        self.assertEqual(receipt["authority_effect"], "NONE")
        self.assertEqual(receipt["quantum_gravity_status"], "NOT_TESTED")

    def test_tamper_changes_receipt_content(self):
        receipt = build_phase_receipt()
        forged = copy.deepcopy(receipt)
        forged["points"][0]["cudaq_x_scaled"] += 1
        self.assertNotEqual(receipt, forged)


if __name__ == "__main__":
    unittest.main(verbosity=2)
