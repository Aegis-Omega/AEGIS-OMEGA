from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroHeightTruncationV1.lean"


class ZeroHeightTruncationV1Tests(unittest.TestCase):
    def test_required_height_carrier_exists(self):
        text = SOURCE.read_text()
        self.assertIn("def NontrivialZeroHeightSetV1", text)
        self.assertIn("theorem nontrivial_zero_height_set_finite_v1", text)
        self.assertIn("|s.im| ≤ T", text)
        self.assertIn("HEIGHT_TRUNCATION_FINITE_ONLY", text)
        self.assertIn(".inter_riemannZetaZeros_finite", text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text()
        self.assertIn("HEIGHT_LIMIT_EXISTENCE_OPEN", text)
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
