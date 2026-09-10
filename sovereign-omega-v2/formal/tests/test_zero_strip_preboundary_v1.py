from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZeroStripPreboundaryV1.lean"


class ZeroStripPreboundaryV1Tests(unittest.TestCase):
    def test_required_localization_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "theorem riemann_zero_re_lt_one_v1",
            "theorem riemann_zero_not_left_halfplane_if_not_neg_nat_v1",
            "theorem riemann_zero_re_pos_if_not_neg_nat_v1",
            "riemannZeta_ne_zero_of_one_le_re",
            "riemannZeta_one_sub",
            "NEGATIVE_INTEGER_ZERO_CLASSIFICATION_OPEN",
            "HEIGHT_TRUNCATION_EQUIVALENCE_OPEN",
            "RH_EQUIVALENCE_OPEN",
        ):
            self.assertIn(required, text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("RiemannHypothesis :=", text)
        self.assertNotIn("theorem riemann_nontrivial_zero_in_critical_strip_v1", text)


if __name__ == "__main__":
    unittest.main()
