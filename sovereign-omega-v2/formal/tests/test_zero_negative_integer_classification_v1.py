from pathlib import Path
import unittest

SOURCE = Path("sovereign-omega-v2/formal/bridges/lean/ZeroNegativeIntegerClassificationV1.lean")

class ZeroNegativeIntegerClassificationV1Tests(unittest.TestCase):
    def test_required_objects_exist(self):
        self.assertTrue(SOURCE.exists(), "negative-integer classification Lean source is missing")
        text = SOURCE.read_text(encoding="utf-8")
        for token in (
            "bernoulli_two_mul_succ_ne_zero_v1",
            "riemann_zeta_neg_nat_zero_is_trivial_index_v1",
            "riemannZeta_two_mul_nat",
            "riemannZeta_neg_nat_eq_bernoulli",
            "NEGATIVE_INTEGER_ZERO_CLASSIFICATION_ONLY",
            "LOWER_NONTRIVIAL_ZERO_LOCALIZATION_OPEN",
            "RH_EQUIVALENCE_OPEN",
        ):
            self.assertIn(token, text)

    def test_scope_remains_fail_closed(self):
        self.assertTrue(SOURCE.exists(), "negative-integer classification Lean source is missing")
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertNotIn("sorry", lowered)
        self.assertNotIn("axiom ", lowered)
        self.assertNotIn("riemann_nontrivial_zero_re_pos_v1", text)
        self.assertNotIn("theorem riemann_hypothesis", lowered)

if __name__ == "__main__":
    unittest.main()
