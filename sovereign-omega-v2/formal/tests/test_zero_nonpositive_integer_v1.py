from pathlib import Path
import unittest

SOURCE = Path("sovereign-omega-v2/formal/bridges/lean/ZeroNonpositiveIntegerV1.lean")

class ZeroNonpositiveIntegerV1Tests(unittest.TestCase):
    def test_required_objects_exist(self):
        self.assertTrue(SOURCE.exists(), "nonpositive-integer Lean source is missing")
        text = SOURCE.read_text(encoding="utf-8")
        for token in (
            "riemann_zeta_zero_nonpos_is_neg_nat_v1",
            "riemannZeta_one_sub",
            "riemannZeta_ne_zero_of_one_le_re",
            "NONPOSITIVE_ZERO_INTEGER_REDUCTION_ONLY",
            "NEGATIVE_INTEGER_PARITY_CLASSIFICATION_OPEN",
            "LOWER_ZERO_LOCALIZATION_OPEN",
            "RH_EQUIVALENCE_OPEN",
        ):
            self.assertIn(token, text)

    def test_scope_remains_fail_closed(self):
        self.assertTrue(SOURCE.exists(), "nonpositive-integer Lean source is missing")
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertNotIn("sorry", lowered)
        self.assertNotIn("axiom ", lowered)
        self.assertNotIn("riemann_zeta_nontrivial_zero_re_pos_v1", text)
        self.assertNotIn("negative_even", lowered)
        self.assertNotIn("theorem riemann_hypothesis", lowered)

if __name__ == "__main__":
    unittest.main()
