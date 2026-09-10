#!/usr/bin/env python3
import unittest

from gravity_quantum.counterfactual_v3 import (
    build_counterfactual_grid,
    comment_magnetic_prefactor,
    discrimination_delta,
    qgi_eq3_mass_equal_prefactor,
    reply_generalized_prefactor,
)


def contains_float(value):
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(contains_float(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_float(v) for v in value)
    return False


class TestCounterfactualV3(unittest.TestCase):
    def test_levitation_control_is_degenerate_for_general_mass_ratio(self):
        # r = a/g and k = m_g/m_i. Levitation is r=k.
        reply = reply_generalized_prefactor(3, 2, 3, 2)
        comment = comment_magnetic_prefactor(3, 2)
        self.assertEqual(reply, {"numerator": -3, "denominator": 4})
        self.assertEqual(comment, {"numerator": -3, "denominator": 4})
        self.assertEqual(discrimination_delta(3, 2, 3, 2), {"numerator": 0, "denominator": 1})

    def test_mass_equal_qgi_and_reply_agree_after_time_convention_alignment(self):
        for r_num, r_den in ((1, 2), (1, 1), (3, 2), (2, 1)):
            self.assertEqual(
                qgi_eq3_mass_equal_prefactor(r_num, r_den),
                reply_generalized_prefactor(r_num, r_den, 1, 1),
            )

    def test_off_levitation_half_g_separates_published_formula_forms(self):
        self.assertEqual(qgi_eq3_mass_equal_prefactor(1, 2), {"numerator": -1, "denominator": 4})
        self.assertEqual(comment_magnetic_prefactor(1, 2), {"numerator": -1, "denominator": 12})
        self.assertEqual(discrimination_delta(1, 2, 1, 1), {"numerator": -1, "denominator": 6})

    def test_off_levitation_three_halves_g_separates_published_formula_forms(self):
        self.assertEqual(qgi_eq3_mass_equal_prefactor(3, 2), {"numerator": -1, "denominator": 4})
        self.assertEqual(comment_magnetic_prefactor(3, 2), {"numerator": -3, "denominator": 4})
        self.assertEqual(discrimination_delta(3, 2, 1, 1), {"numerator": 1, "denominator": 2})

    def test_grid_marks_comment_off_levitation_use_as_contested_extrapolation(self):
        grid = build_counterfactual_grid()
        control = next(row for row in grid["rows"] if row["r"] == {"numerator": 1, "denominator": 1})
        off = next(row for row in grid["rows"] if row["r"] == {"numerator": 3, "denominator": 2})
        self.assertFalse(control["formula_divergence"])
        self.assertTrue(off["formula_divergence"])
        self.assertEqual(off["comment_eq6_domain_status"], "CONTESTED_EXTRAPOLATION_OUTSIDE_LEVITATION")
        self.assertEqual(grid["empirical_model_selection"], "BLOCKED")
        self.assertFalse(contains_float(grid))


if __name__ == "__main__":
    unittest.main(verbosity=2)
