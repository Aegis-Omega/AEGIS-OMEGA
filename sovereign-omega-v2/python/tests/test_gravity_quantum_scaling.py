from __future__ import annotations

import unittest

from gravity_quantum_scaling import (
    SCALING_SIGNATURES,
    ScalingPoint,
    aziz_howl_eq10_proxy,
    classify_scaling,
    measured_signature,
    perturbative_qg_proxy,
)


class GravityQuantumScalingTests(unittest.TestCase):
    def setUp(self):
        self.point = ScalingPoint(
            M=3.0,
            t=5.0,
            Delta_x=0.2,
            d=7.0,
            R=0.4,
        )

    def assert_signature(self, actual, expected):
        for axis, exponent in expected.items():
            self.assertAlmostEqual(actual[axis], exponent, places=12)

    def test_perturbative_qg_small_dx_signature(self):
        signature = measured_signature(
            perturbative_qg_proxy,
            self.point,
        )
        self.assert_signature(
            signature,
            SCALING_SIGNATURES["PERTURBATIVE_QG_NEWTONIAN_SMALL_DX"],
        )
        result = classify_scaling(signature)
        self.assertEqual(
            result["best_matching_registered_formula_signature"],
            "PERTURBATIVE_QG_NEWTONIAN_SMALL_DX",
        )
        self.assertEqual(result["authority_effect"], "NONE")

    def test_aziz_howl_eq10_small_dx_signature(self):
        signature = measured_signature(
            aziz_howl_eq10_proxy,
            self.point,
        )
        self.assert_signature(
            signature,
            SCALING_SIGNATURES["AZIZ_HOWL_2025_EQ10_SMALL_DX"],
        )
        result = classify_scaling(signature)
        self.assertEqual(
            result["best_matching_registered_formula_signature"],
            "AZIZ_HOWL_2025_EQ10_SMALL_DX",
        )
        self.assertEqual(result["aziz_howl_interpretation"], "CONTESTED")
        self.assertEqual(result["claim_scope"], "FORMULA_SCALING_COMPARISON_ONLY")

    def test_formula_match_never_grants_physical_authority(self):
        signature = measured_signature(
            aziz_howl_eq10_proxy,
            self.point,
        )
        result = classify_scaling(signature)
        self.assertNotIn("gravity_quantized", result)
        self.assertNotIn("classical_gravity_true", result)
        self.assertEqual(result["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
