"""Research CMI falsification tests; synthetic inputs are not clinical evidence."""

import json
import unittest

import numpy as np
from scipy.stats import norm

from aegisq_ifg.cmi import SUPPORTED_ASSUMPTIONS, gaussian_cmi_lcb


class GaussianCMITests(unittest.TestCase):
    def setUp(self):
        self.n = 400
        random = np.random.default_rng(20260906)
        columns = random.normal(size=(self.n, 5))
        columns -= columns.mean(axis=0)
        self.basis, _ = np.linalg.qr(columns)
        self.z = self.basis[:, :2]
        self.e1, self.e2 = self.basis[:, 2], self.basis[:, 3]
        self.x = 3 * self.z[:, 0] - self.z[:, 1] + self.e1
        self.y = 2 * self.z[:, 0] + self.z[:, 1] + 0.75 * self.e1 + np.sqrt(1 - 0.75**2) * self.e2
        self.ids = [f"independent-unit-{i}" for i in range(self.n)]

    def call(self, x=None, y=None, z="default", **kwargs):
        parameters = {
            "unit_ids": self.ids,
            "assumptions": SUPPORTED_ASSUMPTIONS,
        }
        parameters.update(kwargs)
        if isinstance(z, str) and z == "default":
            z = self.z
        result = gaussian_cmi_lcb(
            self.x if x is None else x,
            self.y if y is None else y,
            z,
            **parameters,
        )
        # Every success/failure result must satisfy strict JSON, including NaN cases.
        json.dumps(result, allow_nan=False)
        return result

    def assert_denied(self, result, reason):
        self.assertEqual(result["status"], "DENY")
        self.assertIn(reason, result["reasons"])

    def test_partial_correlation_matches_precision_matrix_and_analytical_value(self):
        result = self.call()
        self.assertEqual(result["status"], "PASS_RESEARCH_ONLY")
        self.assertAlmostEqual(result["partial_r"], 0.75, places=12)
        covariance = np.cov(np.column_stack((self.x, self.y, self.z)), rowvar=False)
        precision = np.linalg.inv(covariance)
        analytic = -precision[0, 1] / np.sqrt(precision[0, 0] * precision[1, 1])
        self.assertAlmostEqual(result["partial_r"], analytic, places=12)
        self.assertAlmostEqual(result["estimate_nats"], -0.5 * np.log(1 - 0.75**2), places=12)
        self.assertFalse(result["causal_evidence"])
        self.assertFalse(result["clinical_validation"])
        self.assertFalse(result["assumptions_verified"])

    def test_fisher_bound_matches_specified_formula(self):
        result = self.call(family_size=5)
        se = 1 / np.sqrt(self.n - self.z.shape[1] - 3)
        lower_r = np.tanh(np.arctanh(0.75) - norm.ppf(1 - 0.05 / (2 * 5)) * se)
        expected = -0.5 * np.log1p(-lower_r**2)
        self.assertAlmostEqual(result["lcb_nats"], expected, places=12)

    def test_observed_confounding_is_not_incremental_information(self):
        x = 6 * self.z[:, 0] + self.e1
        y = 6 * self.z[:, 0] + self.e2
        self.assertGreater(np.corrcoef(x, y)[0, 1], 0.95)
        result = self.call(x=x, y=y)
        self.assert_denied(result, "CMI_LCB_BELOW_THRESHOLD")
        self.assertAlmostEqual(result["partial_r"], 0, places=12)
        self.assertEqual(result["lcb_nats"], 0)
        self.assertEqual(self.call(x=x, y=y, z=None)["status"], "PASS_RESEARCH_ONLY")

    def test_negative_dependence_preserves_information(self):
        positive = self.call()
        negative = self.call(y=-self.y)
        self.assertEqual(negative["status"], "PASS_RESEARCH_ONLY")
        self.assertAlmostEqual(negative["partial_r"], -0.75, places=12)
        self.assertAlmostEqual(negative["lcb_nats"], positive["lcb_nats"], places=12)

    def test_scaling_and_offset_robustness(self):
        baseline = self.call()
        scaled = self.call(
            x=self.x * 1e250 + 3e250,
            y=self.y * 1e-250 - 5e-250,
            z=self.z * np.array([1e200, 1e-200]),
        )
        self.assertEqual(scaled["status"], "PASS_RESEARCH_ONLY")
        self.assertAlmostEqual(scaled["partial_r"], baseline["partial_r"], places=11)
        self.assertAlmostEqual(scaled["lcb_nats"], baseline["lcb_nats"], places=11)

    def test_family_correction_reduces_lcb(self):
        single = self.call()
        multiple = self.call(family_size=100)
        self.assertLess(multiple["lcb_nats"], single["lcb_nats"])
        self.assertEqual(multiple["estimate_nats"], single["estimate_nats"])

    def test_threshold_is_enforced(self):
        self.assert_denied(self.call(gamma_nats=0.7), "CMI_LCB_BELOW_THRESHOLD")

    def test_unsupported_or_missing_assumptions(self):
        for assumptions in [None, {}, "", "iid", "time_series", "iid_joint_gaussian"]:
            with self.subTest(assumptions=assumptions):
                self.assert_denied(self.call(assumptions=assumptions), "UNSUPPORTED_OR_MISSING_ASSUMPTIONS")

    def test_missing_required_assertion_does_not_run(self):
        with self.assertRaises(TypeError):
            gaussian_cmi_lcb(self.x, self.y, self.z, unit_ids=self.ids)

    def test_bad_parameters(self):
        invalid = {
            "alpha": [0, 1, -0.05, float("nan"), float("inf"), True, "0.05", 10**1000],
            "gamma_nats": [0, -0.1, float("nan"), float("inf"), True, "0.02", 10**1000],
            "family_size": [0, -1, 1.5, True, float("nan"), "2"],
        }
        for parameter, values in invalid.items():
            for value in values:
                with self.subTest(parameter=parameter, value=value):
                    self.assert_denied(self.call(**{parameter: value}), f"INVALID_{parameter.upper()}")

    def test_extreme_multiplicity_cannot_create_spurious_certainty(self):
        self.assert_denied(self.call(family_size=10**1000), "UNCERTAINTY_NUMERIC_FAILURE")

    def test_nonfinite_data(self):
        for name in ["x", "y", "z"]:
            for value in [float("nan"), float("inf"), -float("inf")]:
                with self.subTest(name=name, value=value):
                    array = getattr(self, name).copy()
                    array.flat[0] = value
                    self.assert_denied(self.call(**{name: array}), f"{name.upper()}_NONFINITE")

    def test_complex_data_rejected_even_with_zero_imaginary_part(self):
        for name in ["x", "y", "z"]:
            with self.subTest(name=name):
                array = getattr(self, name).astype(complex)
                self.assert_denied(self.call(**{name: array}), f"{name.upper()}_COMPLEX_UNSUPPORTED")

    def test_binary_labels_and_binary_feature_rejected(self):
        for name in ["x", "y"]:
            with self.subTest(name=name):
                array = np.arange(self.n) % 2
                self.assert_denied(self.call(**{name: array}), "BINARY_OR_CONSTANT_X_Y_UNSUPPORTED")

    def test_duplicate_and_empty_ids(self):
        duplicate = self.ids.copy()
        duplicate[-1] = duplicate[0]
        self.assert_denied(self.call(unit_ids=duplicate), "DUPLICATE_UNIT_IDS_CLUSTERED_DATA_UNSUPPORTED")
        for ids in [None, [], self.ids[:-1], [""] * self.n, [" "] * self.n, list(range(self.n))]:
            with self.subTest(ids_type=type(ids).__name__):
                self.assertEqual(self.call(unit_ids=ids)["status"], "DENY")

    def test_rank_deficient_or_ill_conditioned_z(self):
        for z in [
            np.column_stack((self.z[:, 0], self.z[:, 0])),
            np.column_stack((self.z[:, 0], self.z[:, 0] + 1e-12 * self.z[:, 1])),
        ]:
            self.assert_denied(self.call(z=z), "Z_DESIGN_RANK_DEFICIENT_OR_ILL_CONDITIONED")
        self.assert_denied(self.call(z=np.ones((self.n, 1))), "Z_CONSTANT_FEATURE")

    def test_zero_residual_variance_denied(self):
        self.assert_denied(self.call(x=self.z[:, 0]), "ZERO_OR_NEAR_ZERO_RESIDUAL_VARIANCE")

    def test_perfect_residual_correlation_denied(self):
        for y in [self.x, -self.x, 3 * self.x + 1]:
            self.assert_denied(self.call(y=y), "PERFECT_OR_NEAR_PERFECT_RESIDUAL_CORRELATION")

    def test_sample_size_and_shapes(self):
        self.assert_denied(
            self.call(x=self.x[:20], y=self.y[:20], z=self.z[:20], unit_ids=self.ids[:20]),
            "INSUFFICIENT_INDEPENDENT_UNITS",
        )
        self.assert_denied(
            self.call(x=self.x[:30], y=self.y[:30], z=np.ones((30, 26)), unit_ids=self.ids[:30]),
            "INSUFFICIENT_INDEPENDENT_UNITS",
        )
        self.assert_denied(self.call(x=self.x[:, None]), "SCALAR_X_Y_MATCHING_VECTORS_REQUIRED")
        self.assert_denied(self.call(z=self.z[:-1]), "Z_SHAPE_MISMATCH")
        self.assert_denied(self.call(z=np.zeros((self.n, 1, 1))), "Z_SHAPE_MISMATCH")

    def test_one_dimensional_z_matches_column_matrix(self):
        vector = self.call(z=self.z[:, 0])
        matrix = self.call(z=self.z[:, :1])
        self.assertAlmostEqual(vector["partial_r"], matrix["partial_r"], places=14)


if __name__ == "__main__":
    unittest.main()
