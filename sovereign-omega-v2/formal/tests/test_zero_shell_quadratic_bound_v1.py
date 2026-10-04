from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroShellQuadraticBoundV1.lean"


class ZeroShellQuadraticBoundV1Tests(unittest.TestCase):
    def test_required_quadratic_reduction_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("def HasQuadraticShellMassBoundV1", text)
        self.assertIn("theorem quadratic_shell_bound_implies_summable_v1", text)
        self.assertIn("summable_one_div_nat_pow", text)
        self.assertIn("Summable.of_nonneg_of_le", text)
        self.assertIn("theorem quadratic_shell_bound_implies_height_limit_v1", text)
        self.assertIn("shell_mass_implies_height_limit_exists_v1", text)
        self.assertIn("QUADRATIC_SHELL_BOUND_SUFFICIENT_ONLY", text)

    def test_actual_decay_and_rh_remain_open(self):
        text = SOURCE.read_text()
        self.assertIn("ACTUAL_QUADRATIC_SHELL_BOUND_OPEN", text)
        self.assertIn("MELLIN_DECAY_ESTIMATE_OPEN", text)
        self.assertIn("ZERO_COUNTING_BOUND_OPEN", text)
        self.assertIn("WEIL_CLASS_SHELL_MASS_SUMMABILITY_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("theorem actual_quadratic_shell_bound", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
