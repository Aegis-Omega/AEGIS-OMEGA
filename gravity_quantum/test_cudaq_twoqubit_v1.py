#!/usr/bin/env python3
import copy
import math
import unittest

from gravity_quantum.cudaq_twoqubit_v1 import (
    COEFFICIENT_SCALE,
    DEFAULT_TIME_SCALED,
    DYNAMICS_TOLERANCE_SCALED,
    FIELD0_SCALED,
    FIELD1_SCALED,
    INTERACTION_J_SCALED,
    PARENT_PHASE_HEAD,
    PARENT_PHASE_RECEIPT_SHA256,
    SPECTRUM_TOLERANCE_SCALED,
    TIME_SCALE,
    VALUE_SCALE,
    analytic_spectrum_scaled,
    build_twoqubit_receipt,
    cudaq_spectrum_scaled,
    run_dynamics_point,
)


EXPECTED_BY_BASIS = {
    "00": 800_000_000_000,
    "01": -400_000_000_000,
    "10": -1_000_000_000_000,
    "11": 600_000_000_000,
}
EXPECTED_SORTED = (
    -1_000_000_000_000,
    -400_000_000_000,
    600_000_000_000,
    800_000_000_000,
)


class TestCudaQTwoQubitV1(unittest.TestCase):
    def test_hamiltonian_constants_are_preregistered(self):
        self.assertEqual(COEFFICIENT_SCALE, 1_000_000)
        self.assertEqual(TIME_SCALE, 1_000_000)
        self.assertEqual(VALUE_SCALE, 1_000_000_000_000)
        self.assertEqual(INTERACTION_J_SCALED, 700_000)
        self.assertEqual(FIELD0_SCALED, 200_000)
        self.assertEqual(FIELD1_SCALED, -100_000)

    def test_analytic_spectrum_is_exact_and_non_degenerate(self):
        spectrum = analytic_spectrum_scaled()
        self.assertEqual(spectrum["by_basis"], EXPECTED_BY_BASIS)
        self.assertEqual(tuple(spectrum["sorted"]), EXPECTED_SORTED)
        self.assertEqual(len(set(spectrum["sorted"])), 4)

    def test_cudaq_reproduces_all_four_eigenvalues(self):
        observed = cudaq_spectrum_scaled()
        self.assertEqual(set(observed), set(EXPECTED_BY_BASIS))
        for basis, expected in EXPECTED_BY_BASIS.items():
            self.assertLessEqual(abs(observed[basis] - expected), SPECTRUM_TOLERANCE_SCALED)

    def test_dynamics_matches_independent_closed_form_oracle(self):
        for time_scaled in DEFAULT_TIME_SCALED:
            point = run_dynamics_point(time_scaled)
            t = time_scaled / 1_000_000
            x0_ref = int(round(math.cos(0.4 * t) * math.cos(1.4 * t) * 1_000_000_000_000))
            x1_ref = int(round(math.cos(0.2 * t) * math.cos(1.4 * t) * 1_000_000_000_000))
            self.assertEqual(point["classical_x0_scaled"], x0_ref)
            self.assertEqual(point["classical_x1_scaled"], x1_ref)
            self.assertLessEqual(point["abs_error_x0_scaled"], DYNAMICS_TOLERANCE_SCALED)
            self.assertLessEqual(point["abs_error_x1_scaled"], DYNAMICS_TOLERANCE_SCALED)

    def test_interaction_term_materially_changes_local_dynamics(self):
        point = run_dynamics_point(1_000_000)
        uncoupled_x0 = int(round(math.cos(0.4) * 1_000_000_000_000))
        uncoupled_x1 = int(round(math.cos(0.2) * 1_000_000_000_000))
        self.assertGreater(abs(point["classical_x0_scaled"] - uncoupled_x0), 100_000_000_000)
        self.assertGreater(abs(point["classical_x1_scaled"] - uncoupled_x1), 100_000_000_000)

    def test_analytic_observe_is_deterministic(self):
        first_spectrum = cudaq_spectrum_scaled()
        second_spectrum = cudaq_spectrum_scaled()
        self.assertEqual(first_spectrum, second_spectrum)
        first_points = [run_dynamics_point(t) for t in DEFAULT_TIME_SCALED]
        second_points = [run_dynamics_point(t) for t in DEFAULT_TIME_SCALED]
        self.assertEqual(first_points, second_points)

    def test_receipt_binds_parent_phase_evidence(self):
        receipt = build_twoqubit_receipt()
        self.assertEqual(PARENT_PHASE_HEAD, "fd297154264455c055ee40b10eed44f86e23edf6")
        self.assertEqual(PARENT_PHASE_RECEIPT_SHA256, "24ccf846dafbbb34ecb5471703c440a4c41f5030cb637302d5c4b80460ac1d01")
        self.assertEqual(receipt["parent_phase_head"], PARENT_PHASE_HEAD)
        self.assertEqual(receipt["parent_phase_receipt_sha256"], PARENT_PHASE_RECEIPT_SHA256)

    def test_receipt_contains_no_floats(self):
        def contains_float(value):
            if isinstance(value, float):
                return True
            if isinstance(value, dict):
                return any(contains_float(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return any(contains_float(v) for v in value)
            return False

        self.assertFalse(contains_float(build_twoqubit_receipt()))

    def test_receipt_is_deterministic_and_research_only(self):
        first = build_twoqubit_receipt()
        second = build_twoqubit_receipt()
        self.assertEqual(first, second)
        self.assertEqual(first["scope"], "RESEARCH_ONLY_COMPUTATIONAL_CROSSCHECK")
        self.assertEqual(first["spectrum_status"], "VERIFIED_IN_DECLARED_COMPUTATIONAL_SCOPE")
        self.assertEqual(first["dynamics_status"], "VERIFIED_IN_DECLARED_COMPUTATIONAL_SCOPE")
        self.assertEqual(first["physics_claim_effect"], "NONE")
        self.assertEqual(first["quantum_gravity_status"], "NOT_TESTED")
        self.assertEqual(first["authority_effect"], "NONE")

    def test_tamper_changes_receipt_content(self):
        receipt = build_twoqubit_receipt()
        forged = copy.deepcopy(receipt)
        forged["dynamics"][0]["cudaq_x0_scaled"] += 1
        self.assertNotEqual(receipt, forged)


if __name__ == "__main__":
    unittest.main(verbosity=2)
