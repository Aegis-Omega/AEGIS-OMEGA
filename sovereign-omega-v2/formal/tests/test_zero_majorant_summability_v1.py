from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroMajorantSummabilityV1.lean"


class ZeroMajorantSummabilityV1Tests(unittest.TestCase):
    def test_required_majorant_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("def HasSummableZeroMajorantV1", text)
        self.assertIn("theorem zero_summable_of_majorant_v1", text)
        self.assertIn("Summable.of_norm_bounded", text)
        self.assertIn("theorem majorant_implies_height_limit_exists_v1", text)
        self.assertIn("hasSum_implies_height_limit_v1", text)
        self.assertIn("theorem majorant_height_limit_eq_tsum_v1", text)
        self.assertIn("ZERO_MAJORANT_SUFFICIENT_ONLY", text)

    def test_actual_majorant_and_rh_remain_open(self):
        text = SOURCE.read_text()
        self.assertIn("ACTUAL_MAJORANT_CONSTRUCTION_OPEN", text)
        self.assertIn("WEIL_CLASS_MAJORANT_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("theorem actual_majorant_exists", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
