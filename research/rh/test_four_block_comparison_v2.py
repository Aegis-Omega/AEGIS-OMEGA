"""Exact positive/negative controls for the comparison certificate."""
from fractions import Fraction as Q
from pathlib import Path
import unittest

from four_block_comparison_v2 import (
    BOUND, DIAGONAL_TARGET, comparison_matrix, quadratic, receipt,
    sos_terms, validate_sos,
)


class FourBlockComparisonTests(unittest.TestCase):
    def test_complete_polynomial_identity(self):
        self.assertTrue(validate_sos(comparison_matrix(), BOUND, sos_terms()))

    def test_positive_sos_coefficients(self):
        self.assertTrue(all(c > 0 for c, _ in sos_terms()))

    def test_original_generalization_is_false(self):
        x = tuple(map(Q, (4, 5, 5, 4)))
        value = Q(9, 8)*sum(v*v for v in x)-quadratic(comparison_matrix(r=Q(0)), x)
        self.assertEqual(value, Q(-57, 20))

    def test_original_equal_coefficient_identity_is_preserved(self):
        x = (Q(1),)*4
        self.assertEqual(Q(9, 8)*4-quadratic(comparison_matrix(r=Q(0)), x), 0)

    def test_farthest_pair_cannot_be_silently_discarded(self):
        x = (Q(1),)*4
        self.assertEqual(Q(9, 8)*4-quadratic(comparison_matrix(), x), Q(-13, 25))
        with self.assertRaises(ValueError):
            validate_sos(comparison_matrix(r=Q(0)), BOUND, sos_terms())

    def test_old_threshold_rejected(self):
        with self.assertRaises(ValueError):
            validate_sos(comparison_matrix(), Q(9, 8), sos_terms())

    def test_larger_farthest_constant_rejected(self):
        with self.assertRaises(ValueError):
            validate_sos(comparison_matrix(r=Q(3, 10)), BOUND, sos_terms())

    def test_tampered_positive_coefficient_rejected(self):
        terms = list(sos_terms())
        terms[0] = (terms[0][0]+Q(1, 100000), terms[0][1])
        with self.assertRaises(ValueError):
            validate_sos(comparison_matrix(), BOUND, terms)

    def test_negative_coefficient_rejected(self):
        terms = list(sos_terms())
        terms[0] = (-terms[0][0], terms[0][1])
        with self.assertRaises(ValueError):
            validate_sos(comparison_matrix(), BOUND, terms)

    def test_floats_rejected(self):
        with self.assertRaises(TypeError):
            comparison_matrix(r=0.26)
        with self.assertRaises(TypeError):
            validate_sos(comparison_matrix(), 1.264, sos_terms())

    def test_exact_margin_and_weighted_residual(self):
        self.assertEqual(DIAGONAL_TARGET-BOUND, Q(2, 125))
        matrix = comparison_matrix()
        weights = tuple(map(Q, (13, 15, 15, 13)))
        residual = tuple(BOUND-sum(matrix[i][j]*weights[j] for j in range(4))/weights[i]
                         for i in range(4))
        self.assertEqual(residual, (Q(1,6500), Q(0), Q(0), Q(1,6500)))

    def test_narrow_middle_interval_gain(self):
        self.assertEqual(16*(Q(1,32)-Q(1,64)), Q(1,4))
        self.assertEqual(Q(103,100)+Q(1,4), Q(32,25))

    def test_sinh_rational_envelope(self):
        self.assertEqual((Q(16,15)-Q(31,32))/2, Q(47,960))
        self.assertLess(Q(47,960), Q(1,16))

    def test_zero_vector_has_no_division_by_energy(self):
        self.assertEqual(quadratic(comparison_matrix(), (Q(0),)*4), 0)

    def test_receipt_does_not_promote_scope(self):
        result = receipt()
        self.assertEqual(result["lean_kernel"], "NOT_RUN")
        self.assertEqual(result["actual_four_packet_analytic_premises"], "NOT_DISCHARGED")
        self.assertEqual(result["riemann_hypothesis"], "NOT_PROVEN")
        self.assertEqual(result["authority_effect"], "NONE")

    def test_actual_lean_interface_keeps_all_analytic_premises(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "sovereign-omega-v2/formal/bridges/lean/RHFourBlockActualBridgeV2.lean").read_text()
        for name in ("h0", "h1", "h2", "h3", "h01", "h02", "h03", "h12", "h13", "h23"):
            self.assertIn(f"({name} :", source)
        self.assertIn("(h03 : ‖B g0 g3‖ ≤ (13 / 50 : ℝ) * E)", source)
        self.assertIn("actual_four_block_expansion_v2", source)
        self.assertNotRegex(source, r"(?m)^\s*(axiom|sorry|admit)\b")


if __name__ == "__main__":
    unittest.main(verbosity=2)
