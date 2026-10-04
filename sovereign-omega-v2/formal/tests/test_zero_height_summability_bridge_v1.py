from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroHeightSummabilityBridgeV1.lean"


class ZeroHeightSummabilityBridgeV1Tests(unittest.TestCase):
    def test_required_conditional_bridge_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("def RiemannNontrivialZeroIndexV2", text)
        self.assertIn("NontrivialZeroHeightIndexFinsetV1", text)
        self.assertIn("tendsto_nontrivial_zero_height_index_finset_atTop_v1", text)
        self.assertIn("HasSum", text)
        self.assertIn("hasSum_implies_height_limit_v1", text)
        self.assertIn("HasWeilZeroHeightLimitV1", text)
        self.assertIn("UNCONDITIONAL_SUMMABILITY_SUFFICIENT_ONLY", text)

    def test_actual_summability_and_rh_remain_open(self):
        text = SOURCE.read_text()
        self.assertIn("ACTUAL_ZERO_SUM_SUMMABILITY_OPEN", text)
        self.assertIn("HEIGHT_LIMIT_EXISTENCE_UNCONDITIONAL_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("theorem zero_sum_summable", text)
        self.assertNotIn("theorem height_limit_exists", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
