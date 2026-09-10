from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroShellFactorizationV1.lean"


class ZeroShellFactorizationV1Tests(unittest.TestCase):
    def test_required_factorization_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("def WeightedZeroShellCountV1", text)
        self.assertIn("def HasUniformMellinShellBoundV1", text)
        self.assertIn("theorem zero_height_shell_mass_le_weighted_count_mul_v1", text)
        self.assertIn("Complex.norm_natCast", text)
        self.assertIn("Finset.sum_le_sum", text)
        self.assertIn("MULTIPLICITY_WEIGHTED_SHELL_FACTORIZATION_ONLY", text)

    def test_quantitative_inputs_and_rh_remain_open(self):
        text = SOURCE.read_text()
        self.assertIn("WEIGHTED_ZERO_COUNT_BOUND_OPEN", text)
        self.assertIn("UNIFORM_MELLIN_DECAY_BOUND_OPEN", text)
        self.assertIn("ACTUAL_QUADRATIC_SHELL_BOUND_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("theorem weighted_zero_count_bound", text)
        self.assertNotIn("theorem uniform_mellin_decay_bound", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
