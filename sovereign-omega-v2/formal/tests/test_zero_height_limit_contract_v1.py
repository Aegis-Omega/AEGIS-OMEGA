from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroHeightLimitContractV1.lean"


class ZeroHeightLimitContractV1Tests(unittest.TestCase):
    def test_required_contract_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("def HasWeilZeroHeightLimitV1", text)
        self.assertIn("Tendsto", text)
        self.assertIn("atTop", text)
        self.assertIn("WeilZeroHeightTruncatedSumV1", text)
        self.assertIn("def WeilZeroHeightLimitExistsV1", text)
        self.assertIn("theorem weil_zero_height_limit_unique_v1", text)
        self.assertIn("tendsto_nhds_unique", text)
        self.assertIn("HEIGHT_LIMIT_CONTRACT_ONLY", text)

    def test_existence_and_rh_remain_open(self):
        text = SOURCE.read_text()
        self.assertIn("HEIGHT_LIMIT_EXISTENCE_OPEN", text)
        self.assertIn("ZERO_SUM_CONVERGENCE_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("theorem height_limit_exists", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
