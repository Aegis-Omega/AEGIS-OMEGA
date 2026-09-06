"""Analytic physical controls and fail-closed input boundaries (no measured data)."""

import unittest

import numpy as np

from aegisq_ifg.physics import (
    IndependentFalsificationGate,
    PhysicsPolicy,
    gksl_rhs,
    wigner_origin,
)


I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.diag([1, -1]).astype(complex)
# One six-outcome POVM, equivalent to randomly selecting a Pauli axis.
PAULI_POVM = np.asarray([(I2 + sign * p) / 6 for p in (X, Y, Z) for sign in (1, -1)])


def born_probabilities(states, povm=PAULI_POVM):
    return np.asarray([[np.trace(m @ state).real for m in povm] for state in states])


def constant_case(state=None, count=5):
    state = np.diag([0.0, 1.0]) if state is None else state
    states = np.repeat(np.asarray(state, dtype=complex)[None], count, axis=0)
    return {
        "rho": states,
        "times_seconds": np.arange(count) * 0.01,
        "hamiltonian": np.zeros((2, 2), dtype=complex),
        "jumps": [],
        "povm": PAULI_POVM.copy(),
        "probabilities": born_probabilities(states),
    }


def amplitude_damping_case(rate=0.7, dt=0.005, count=11):
    times = np.arange(count) * dt
    excited = np.exp(-rate * times)
    states = np.asarray([np.diag([1 - p, p]) for p in excited], dtype=complex)
    case = constant_case(count=count)
    case.update(
        rho=states,
        times_seconds=times,
        jumps=np.asarray([[[0, np.sqrt(rate)], [0, 0]]], dtype=complex),
        probabilities=born_probabilities(states),
    )
    return case


class PhysicalControlTests(unittest.TestCase):
    def setUp(self):
        self.gate = IndependentFalsificationGate()

    def assertDenied(self, case, reason=None, gate=None):
        result = (gate or self.gate).evaluate(**case)
        self.assertEqual(result["status"], "DENY", result)
        self.assertFalse(result["clinical_admission"])
        if reason:
            self.assertIn(reason, result["reasons"], result)
        return result

    def test_amplitude_damping_matches_analytic_populations(self):
        case = amplitude_damping_case()
        result = self.gate.evaluate(**case)
        self.assertEqual(result["status"], "PASS_RESEARCH_ONLY", result)
        self.assertEqual(result["metrics"]["measurement_rank"], 3)
        self.assertLess(result["metrics"]["max_transition_residual"], 1e-13)
        # Midpoint finite differences have a nonzero truncation error even when
        # every sample lies exactly on the solution of the master equation.
        k, dt = 0.7, 0.005
        expected_midpoint_error = np.sqrt(2) * abs(
            (np.exp(-k * dt) - 1) / dt + k * (1 + np.exp(-k * dt)) / 2
        )
        self.assertAlmostEqual(
            result["metrics"]["max_midpoint_residual_per_second"],
            expected_midpoint_error,
            delta=2e-13,
        )
        self.assertGreater(expected_midpoint_error, 0)
        np.testing.assert_allclose(case["probabilities"][0], [1/6, 1/6, 1/6, 1/6, 0, 1/3])
        np.testing.assert_allclose(
            gksl_rhs(case["rho"][0], case["hamiltonian"], case["jumps"]),
            np.diag([k, -k]),
        )

    def test_coarse_exact_trajectory_can_fail_midpoint_bound(self):
        case = amplitude_damping_case(rate=1, dt=0.5, count=4)
        result = self.assertDenied(case, "LINDBLAD_RESIDUAL")
        self.assertNotIn("TRANSITION_MISMATCH", result["reasons"])
        self.assertLess(result["metrics"]["max_transition_residual"], 1e-13)

    def test_coherent_rotation_checks_commutator_sign_and_vectorization(self):
        times = np.arange(7) * 0.001
        omega = 1.3
        vectors = [np.array([np.cos(omega*t/2), -1j*np.sin(omega*t/2)]) for t in times]
        states = np.asarray([np.outer(v, v.conj()) for v in vectors])
        case = constant_case(count=len(times))
        case.update(rho=states, times_seconds=times, hamiltonian=omega*X/2,
                    probabilities=born_probabilities(states))
        result = self.gate.evaluate(**case)
        self.assertEqual(result["status"], "PASS_RESEARCH_ONLY", result)
        self.assertLess(result["metrics"]["max_transition_residual"], 1e-13)
        case["hamiltonian"] *= -1
        self.assertDenied(case, "TRANSITION_MISMATCH")

    def test_physical_one_photon_state_passes_despite_negative_wigner(self):
        case = constant_case()
        result = self.gate.evaluate(**case)
        self.assertEqual(result["status"], "PASS_RESEARCH_ONLY", result)
        self.assertEqual(result["quantum_nonclassicality"], "NOT_TESTED_BY_PHYSICAL_GATE")
        self.assertFalse(result["clinical_admission"])
        self.assertAlmostEqual(wigner_origin(case["rho"][0])["value"], -2 / np.pi)

    def test_vacuum_wigner_is_positive(self):
        self.assertAlmostEqual(wigner_origin(np.diag([1, 0]))["value"], 2 / np.pi)

    def test_negative_eigenvalue_is_denied(self):
        self.assertDenied(constant_case(np.diag([-1e-5, 1 + 1e-5])), "PSD_VIOLATION")

    def test_nonhermitian_state_is_not_silently_repaired(self):
        self.assertDenied(constant_case(np.array([[0.5, 0.1], [0, 0.5]])), "NON_HERMITIAN_STATE")

    def test_trace_violation_is_denied(self):
        self.assertDenied(constant_case(np.diag([0.5, 0.51])), "TRACE_VIOLATION")

    def test_invalid_middle_state_cannot_hide_between_valid_endpoints(self):
        case = constant_case()
        case["rho"][2] = np.diag([-0.01, 1.01])
        self.assertDenied(case, "PSD_VIOLATION")

    def test_nonfinite_inputs_are_denied(self):
        for field in ("rho", "times_seconds", "hamiltonian", "jumps", "povm", "probabilities"):
            for value in (np.nan, np.inf, -np.inf):
                with self.subTest(field=field, value=value):
                    case = amplitude_damping_case()
                    case[field] = np.array(case[field], copy=True)
                    case[field].flat[0] = value
                    self.assertDenied(case, "NONFINITE_INPUT")

    def test_time_grid_order_and_shape_are_checked(self):
        for times in ([0, 0.01, 0.01, 0.03, 0.04], [0.04, 0.03, 0.02, 0.01, 0],
                      [0, 0.01, 0.02], [[0, 0.01, 0.02, 0.03, 0.04]]):
            with self.subTest(times=times):
                case = constant_case()
                case["times_seconds"] = times
                self.assertDenied(case, "INVALID_TIME_GRID")

    def test_too_few_samples_are_denied(self):
        self.assertDenied(constant_case(count=2), "INVALID_TIME_GRID")

    def test_times_must_be_real_numeric_seconds(self):
        for times in (["0 s", "1 s", "2 s", "3 s", "4 s"], np.arange(5, dtype=complex)):
            case = constant_case()
            case["times_seconds"] = times
            self.assertDenied(case, "NON_NUMERIC_OR_WRONG_DTYPE")

    def test_milliseconds_mislabeled_as_seconds_break_dynamics(self):
        # No numeric validator can infer units. Here the independently supplied
        # SI generator makes the incorrect time scale observably inconsistent.
        case = amplitude_damping_case()
        case["times_seconds"] *= 1000
        self.assertDenied(case, "TRANSITION_MISMATCH")

    def test_malformed_state_generator_and_measurement_shapes(self):
        cases = [
            ("rho", np.eye(2), "INVALID_STATE_SHAPE"),
            ("rho", np.ones((5, 2, 3)), "INVALID_STATE_SHAPE"),
            ("hamiltonian", np.eye(3), "INVALID_HAMILTONIAN_SHAPE"),
            ("jumps", np.eye(2), "INVALID_JUMP_SHAPE"),
            ("jumps", np.ones((1, 3, 3)), "INVALID_JUMP_SHAPE"),
            ("povm", np.eye(2), "INVALID_POVM_SHAPE"),
            ("probabilities", np.ones((5, 5)), "INVALID_PROBABILITY_SHAPE"),
        ]
        for field, value, reason in cases:
            with self.subTest(field=field, reason=reason):
                case = constant_case()
                case[field] = value
                self.assertDenied(case, reason)

    def test_nonhermitian_hamiltonian_is_denied(self):
        case = constant_case()
        case["hamiltonian"] = np.array([[0, 1], [0, 0]])
        self.assertDenied(case, "NON_HERMITIAN_HAMILTONIAN")

    def test_incomplete_nonpositive_or_nonhermitian_povm_is_denied(self):
        for mutation in ("incomplete", "negative", "nonhermitian"):
            case = constant_case()
            if mutation == "incomplete":
                case["povm"] *= 0.9
            elif mutation == "negative":
                case["povm"][0, 0, 0] -= 1
                case["povm"][1, 0, 0] += 1
            else:
                case["povm"][0, 0, 1] += 0.1
            with self.subTest(mutation=mutation):
                self.assertDenied(case, "INVALID_POVM")

    def test_measurement_model_mismatch_is_denied(self):
        case = constant_case()
        case["probabilities"][:, 0] += 0.01
        case["probabilities"][:, 1] -= 0.01
        self.assertDenied(case, "MEASUREMENT_MISMATCH")

    def test_invalid_probabilities_are_denied(self):
        for value in (-0.01, 1.01, 0.5):
            with self.subTest(value=value):
                case = constant_case()
                case["probabilities"][0, 0] = value
                self.assertDenied(case, "INVALID_PROBABILITIES")

    def test_z_only_tomography_is_not_identifiable(self):
        case = constant_case()
        case["povm"] = np.asarray([np.diag([1, 0]), np.diag([0, 1])])
        case["probabilities"] = born_probabilities(case["rho"], case["povm"])
        result = self.assertDenied(case, "NOT_IDENTIFIABLE")
        self.assertEqual(result["metrics"]["measurement_rank"], 1)

    def test_state_independent_povm_has_zero_rank(self):
        case = constant_case()
        case["povm"] = np.asarray([I2])
        case["probabilities"] = np.ones((5, 1))
        result = self.assertDenied(case, "NOT_IDENTIFIABLE")
        self.assertEqual(result["metrics"]["measurement_rank"], 0)

    def test_wrong_dissipative_generator_is_denied(self):
        case = amplitude_damping_case()
        case["jumps"] = []
        result = self.assertDenied(case, "TRANSITION_MISMATCH")
        self.assertIn("LINDBLAD_RESIDUAL", result["reasons"])

    def test_single_bad_interval_cannot_be_hidden_by_average(self):
        case = constant_case(count=101)
        case["times_seconds"] = np.arange(101, dtype=float)
        case["rho"][50] = np.diag([0.01, 0.99])
        case["probabilities"] = born_probabilities(case["rho"])
        # Average residual is approximately 0.00028, below 0.001. The maximum
        # interval residual is sqrt(2)*0.01 and must force rejection.
        result = self.assertDenied(case, "LINDBLAD_RESIDUAL")
        self.assertAlmostEqual(result["metrics"]["max_midpoint_residual_per_second"], np.sqrt(2)*0.01)

    def test_finite_extreme_inputs_cannot_overflow_to_pass(self):
        for field, value in (
            ("jumps", np.asarray([[[0, 1e200], [0, 0]]], dtype=complex)),
            ("hamiltonian", np.asarray([[0, 1e308], [1e308, 0]], dtype=complex)),
            ("times_seconds", np.asarray([-1e308, 1e308, 1.1e308, 1.2e308, 1.3e308])),
        ):
            with self.subTest(field=field):
                case = constant_case()
                case[field] = value
                result = self.assertDenied(case)
                for metric in result["metrics"].values():
                    if isinstance(metric, (float, int)):
                        self.assertTrue(np.isfinite(metric))

    def test_invalid_wigner_inputs_raise(self):
        for state in (np.diag([-0.01, 1.01]), np.eye(2), [[0.5, 1], [0, 0.5]],
                      [[np.nan, 0], [0, 1]], [1, 0]):
            with self.subTest(state=state), self.assertRaises(ValueError):
                wigner_origin(state)


class PolicyContractTests(unittest.TestCase):
    def test_invalid_scalar_bounds_are_rejected(self):
        for value in (0, -1, np.nan, np.inf, True, 1j):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                PhysicsPolicy(transition_residual=value)

    def test_relative_rank_threshold_must_be_less_than_one(self):
        with self.assertRaises(ValueError):
            PhysicsPolicy(identifiability_rtol=1)

    def test_dimension_budget_is_bounded_integer(self):
        for dimension in (0, 1, 33, 2.0, True):
            with self.subTest(dimension=dimension), self.assertRaises(ValueError):
                PhysicsPolicy(max_dimension=dimension)

    def test_invalid_policy_object_is_rejected(self):
        with self.assertRaises(TypeError):
            IndependentFalsificationGate(policy={"trace_tolerance": 1})

    def test_bool_and_array_tolerances_are_rejected(self):
        for value in (np.bool_(True), np.array([1e-5]), np.array(1e-5)):
            with self.subTest(value=repr(value)), self.assertRaises((ValueError, TypeError)):
                PhysicsPolicy(transition_residual=value)


if __name__ == "__main__":
    unittest.main()
