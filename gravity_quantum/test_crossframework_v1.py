#!/usr/bin/env python3
import copy
import math
import unittest

from gravity_quantum.crossframework_v1 import (
    DEFAULT_TIME_SCALED,
    PARENT_TWOQUBIT_HEAD,
    PARENT_TWOQUBIT_RECEIPT_SHA256,
    VALUE_SCALE,
    build_crossframework_receipt,
    pennylane_dynamics_point,
    pennylane_spectrum_scaled,
)
from gravity_quantum.cudaq_twoqubit_v1 import (
    FIELD0_SCALED,
    FIELD1_SCALED,
    INTERACTION_J_SCALED,
    TIME_SCALE,
    analytic_spectrum_scaled,
    cudaq_spectrum_scaled,
    run_dynamics_point,
)

EXPECTED_PARENT_HEAD = "35d7aa884d17670a9bc2f8e1fdfb2b5d988f8958"
EXPECTED_PARENT_RECEIPT_SHA256 = "264b285e2447482d70d41da8284569ebe23897b14afe88d594b3528a49bfce8d"


def independent_closed_form(time_scaled: int) -> tuple[int, int]:
    t = time_scaled / TIME_SCALE
    j = INTERACTION_J_SCALED / 1_000_000
    h0 = FIELD0_SCALED / 1_000_000
    h1 = FIELD1_SCALED / 1_000_000
    x0 = int(round(math.cos(2 * h0 * t) * math.cos(2 * j * t) * VALUE_SCALE))
    x1 = int(round(math.cos(2 * h1 * t) * math.cos(2 * j * t) * VALUE_SCALE))
    return x0, x1


class TestCrossFrameworkV1(unittest.TestCase):
    def test_parent_twoqubit_evidence_is_exactly_bound(self):
        self.assertEqual(PARENT_TWOQUBIT_HEAD, EXPECTED_PARENT_HEAD)
        self.assertEqual(PARENT_TWOQUBIT_RECEIPT_SHA256, EXPECTED_PARENT_RECEIPT_SHA256)

    def test_pennylane_spectrum_matches_independent_analytic_spectrum(self):
        analytic = analytic_spectrum_scaled()["by_basis"]
        pennylane = pennylane_spectrum_scaled()
        self.assertEqual(set(analytic), set(pennylane))
        for basis in analytic:
            self.assertLessEqual(abs(pennylane[basis] - analytic[basis]), 1_000)

    def test_cudaq_and_pennylane_spectra_match_each_other(self):
        cudaq_values = cudaq_spectrum_scaled()
        pennylane_values = pennylane_spectrum_scaled()
        for basis in cudaq_values:
            self.assertLessEqual(abs(cudaq_values[basis] - pennylane_values[basis]), 1_000)

    def test_both_frameworks_match_independent_closed_form_dynamics(self):
        for time_scaled in DEFAULT_TIME_SCALED:
            expected_x0, expected_x1 = independent_closed_form(time_scaled)
            cudaq_point = run_dynamics_point(time_scaled)
            pennylane_point = pennylane_dynamics_point(time_scaled)
            self.assertLessEqual(abs(cudaq_point["cudaq_x0_scaled"] - expected_x0), 1_000)
            self.assertLessEqual(abs(cudaq_point["cudaq_x1_scaled"] - expected_x1), 1_000)
            self.assertLessEqual(abs(pennylane_point["pennylane_x0_scaled"] - expected_x0), 1_000)
            self.assertLessEqual(abs(pennylane_point["pennylane_x1_scaled"] - expected_x1), 1_000)

    def test_cudaq_and_pennylane_dynamics_match_each_other(self):
        for time_scaled in DEFAULT_TIME_SCALED:
            cudaq_point = run_dynamics_point(time_scaled)
            pennylane_point = pennylane_dynamics_point(time_scaled)
            self.assertLessEqual(abs(cudaq_point["cudaq_x0_scaled"] - pennylane_point["pennylane_x0_scaled"]), 1_000)
            self.assertLessEqual(abs(cudaq_point["cudaq_x1_scaled"] - pennylane_point["pennylane_x1_scaled"]), 1_000)

    def test_pennylane_execution_is_deterministic(self):
        first = [pennylane_dynamics_point(t) for t in DEFAULT_TIME_SCALED]
        second = [pennylane_dynamics_point(t) for t in DEFAULT_TIME_SCALED]
        self.assertEqual(first, second)

    def test_receipt_contains_no_floats(self):
        def contains_float(value):
            if isinstance(value, float):
                return True
            if isinstance(value, dict):
                return any(contains_float(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return any(contains_float(v) for v in value)
            return False

        self.assertFalse(contains_float(build_crossframework_receipt()))

    def test_receipt_is_deterministic_and_research_only(self):
        first = build_crossframework_receipt()
        second = build_crossframework_receipt()
        self.assertEqual(first, second)
        self.assertEqual(first["scope"], "RESEARCH_ONLY_COMPUTATIONAL_CROSS_FRAMEWORK_WITNESS")
        self.assertEqual(first["pennylane_backend"], "default.qubit")
        self.assertEqual(first["physics_claim_effect"], "NONE")
        self.assertEqual(first["authority_effect"], "NONE")
        self.assertEqual(first["quantum_gravity_status"], "NOT_TESTED")

    def test_crossframework_status_requires_all_three_oracles(self):
        receipt = build_crossframework_receipt()
        self.assertTrue(receipt["checks"]["analytic_oracle_verified"])
        self.assertTrue(receipt["checks"]["cudaq_replay_verified"])
        self.assertTrue(receipt["checks"]["pennylane_replay_verified"])
        self.assertEqual(receipt["computational_status"], "COMPUTATIONAL_CROSS_FRAMEWORK_REPRODUCIBLE")

    def test_tamper_changes_receipt_content(self):
        receipt = build_crossframework_receipt()
        forged = copy.deepcopy(receipt)
        forged["dynamics"][0]["pennylane_x0_scaled"] += 1
        self.assertNotEqual(receipt, forged)


if __name__ == "__main__":
    unittest.main(verbosity=2)
