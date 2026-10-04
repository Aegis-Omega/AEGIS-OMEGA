from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroHeightFiniteSumV1.lean"


class ZeroHeightFiniteSumV1Tests(unittest.TestCase):
    def test_required_finite_sum_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("def NontrivialZeroHeightFinsetV1", text)
        self.assertIn("def HeightZeroMultiplicityV1", text)
        self.assertIn("theorem height_zero_multiplicity_pos_v1", text)
        self.assertIn("theorem height_zero_multiplicity_cast_eq_order_v1", text)
        self.assertIn("def WeilZeroHeightSummandV1", text)
        self.assertIn("def WeilZeroHeightTruncatedSumV1", text)
        self.assertIn(".sum", text)
        self.assertIn("FINITE_HEIGHT_SUM_ONLY", text)

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
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
