import unittest
from pathlib import Path


SOURCE = Path("sovereign-omega-v2/formal/bridges/lean/ZeroNonpositiveTrivialV1.lean")


class ZeroNonpositiveTrivialV1Tests(unittest.TestCase):
    def test_required_composition_exists(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("riemann_zeta_zero_nonpos_is_trivial_v1", text)
        self.assertIn("NONPOSITIVE_ZERO_IS_TRIVIAL_ONLY", text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("axiom ", text)
        self.assertNotIn("sorry", text)
        self.assertIn("LOWER_ZERO_LOCALIZATION_OPEN", text)
        self.assertIn("FULL_CRITICAL_STRIP_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotIn("riemann_zeta_nontrivial_zero_re_pos_v1", text)
        self.assertNotIn("riemann_zeta_nontrivial_zero_critical_strip_v1", text)
        self.assertNotIn("theorem riemann_hypothesis", text.lower())


if __name__ == "__main__":
    unittest.main()
