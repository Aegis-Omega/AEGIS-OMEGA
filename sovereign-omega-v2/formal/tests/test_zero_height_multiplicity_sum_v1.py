from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroHeightMultiplicitySumV1.lean"


class ZeroHeightMultiplicitySumV1Tests(unittest.TestCase):
    def test_required_finite_sum_interface_exists(self):
        text = SOURCE.read_text()
        self.assertIn("def NontrivialZeroHeightSetV1", text)
        self.assertIn("theorem nontrivial_zero_height_set_finite_v1", text)
        self.assertIn("def RiemannZeroMultiplicityAtHeightV1", text)
        self.assertIn("theorem zero_height_multiplicity_pos_v1", text)
        self.assertIn("def NontrivialZeroHeightFinsetV1", text)
        self.assertIn("def WeilZeroHeightSumV1", text)
        self.assertIn("analyticOrderNatAt", text)
        self.assertIn("mellin", text)
        self.assertIn(".sum", text)
        self.assertIn("FINITE_HEIGHT_MULTIPLICITY_SUM_ONLY", text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text()
        self.assertIn("HEIGHT_LIMIT_EXISTENCE_OPEN", text)
        self.assertIn("ZERO_SUM_CONVERGENCE_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("∑'", text)
        self.assertNotIn("tsum", text)
        self.assertNotIn("Tendsto", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
