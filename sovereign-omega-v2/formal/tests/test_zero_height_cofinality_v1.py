from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroHeightCofinalityV1.lean"

class ZeroHeightCofinalityV1Tests(unittest.TestCase):
    def test_required_cofinality_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("HEIGHT_FAMILY_COFINAL_ONLY", text)
        self.assertIn("theorem nontrivial_zero_height_finset_mono_v1", text)
        self.assertIn("theorem finite_nontrivial_zero_subset_height_v1", text)
        self.assertIn("NontrivialZeroHeightFinsetV1", text)
        self.assertIn("Finset.single_le_sum", text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text()
        self.assertIn("HEIGHT_LIMIT_EXISTENCE_OPEN", text)
        self.assertIn("ZERO_SUM_CONVERGENCE_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("theorem zero_sum_converges", text)
        self.assertNotIn("s.re = 1 / 2", text)

if __name__ == "__main__":
    unittest.main()
