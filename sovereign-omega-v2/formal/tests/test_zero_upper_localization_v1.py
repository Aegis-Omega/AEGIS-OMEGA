from pathlib import Path
import unittest


SOURCE = Path("sovereign-omega-v2/formal/bridges/lean/ZeroUpperLocalizationV1.lean")


class ZeroUpperLocalizationV1Tests(unittest.TestCase):
    def test_required_upper_localization_objects_exist(self):
        self.assertTrue(SOURCE.exists(), "upper-localization Lean source is missing")
        text = SOURCE.read_text(encoding="utf-8")
        for token in (
            "riemann_zeta_zero_re_lt_one_v1",
            "riemannZeta_ne_zero_of_one_le_re",
            "UPPER_ZERO_LOCALIZATION_ONLY",
            "LOWER_ZERO_LOCALIZATION_OPEN",
            "HEIGHT_TRUNCATION_EQUIVALENCE_OPEN",
            "RH_EQUIVALENCE_OPEN",
        ):
            self.assertIn(token, text)

    def test_scope_remains_fail_closed(self):
        self.assertTrue(SOURCE.exists(), "upper-localization Lean source is missing")
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertNotIn("sorry", lowered)
        self.assertNotIn("axiom ", lowered)
        self.assertNotIn("theorem riemann_zeta_zero_re_pos_v1", text)
        self.assertNotIn("theorem riemann_hypothesis", lowered)


if __name__ == "__main__":
    unittest.main()
