from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroLowerLocalizationV1.lean"


class ZeroLowerLocalizationV1Tests(unittest.TestCase):
    def test_required_lower_localization_exists(self):
        text = SOURCE.read_text()
        self.assertIn("theorem riemann_zeta_nontrivial_zero_re_pos_v1", text)
        self.assertIn("¬ ∃ n : ℕ, s = -(2 : ℂ) * (n + 1)", text)
        self.assertIn("0 < s.re", text)
        self.assertIn("LOWER_ZERO_LOCALIZATION_ONLY", text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text()
        self.assertIn("FULL_CRITICAL_STRIP_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotIn("theorem riemannHypothesis", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
