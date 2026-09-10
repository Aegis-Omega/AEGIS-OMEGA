from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroHeightShellMassV1.lean"


class ZeroHeightShellMassV1Tests(unittest.TestCase):
    def test_required_shell_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("def ZeroHeightShellIndexV1", text)
        self.assertIn("def ZeroHeightShellSetV1", text)
        self.assertIn("theorem zero_height_shell_finite_v1", text)
        self.assertIn("def ZeroHeightShellMassV1", text)
        self.assertIn("theorem zero_norm_summable_iff_shell_mass_v1", text)
        self.assertIn("summable_partition", text)
        self.assertIn("FINITE_HEIGHT_SHELL_REDUCTION_ONLY", text)

    def test_analytic_decay_and_rh_remain_open(self):
        text = SOURCE.read_text()
        self.assertIn("SHELL_MASS_DECAY_BOUND_OPEN", text)
        self.assertIn("WEIL_CLASS_SHELL_MASS_SUMMABILITY_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("theorem shell_mass_decay_bound", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
