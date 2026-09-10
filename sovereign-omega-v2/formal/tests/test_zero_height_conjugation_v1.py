from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroHeightConjugationV1.lean"


class ZeroHeightConjugationV1Tests(unittest.TestCase):
    def test_required_conjugation_interface_exists(self):
        text = SOURCE.read_text()
        self.assertIn("def NontrivialZeroHeightSetV1", text)
        self.assertIn("theorem nontrivial_zero_height_conj_mem_v1", text)
        self.assertIn("theorem nontrivial_zero_height_conj_iff_v1", text)
        self.assertIn("riemannZeta_conj", text)
        self.assertIn("HEIGHT_CARRIER_CONJUGATION_ONLY", text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text()
        self.assertIn("MULTIPLICITY_CONJUGATION_OPEN", text)
        self.assertIn("FINITE_SUM_CONJUGATION_PAIRING_OPEN", text)
        self.assertIn("HEIGHT_LIMIT_EXISTENCE_OPEN", text)
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
