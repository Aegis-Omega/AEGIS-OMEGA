from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZeroCriticalStripV1.lean"


class ZeroCriticalStripV1Tests(unittest.TestCase):
    def test_required_classification_and_strip_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "theorem bernoulli_two_mul_succ_ne_zero_v1",
            "theorem riemannZeta_neg_odd_ne_zero_v1",
            "theorem riemannZeta_neg_nat_zero_is_trivial_v1",
            "theorem riemann_nontrivial_zero_in_critical_strip_v1",
            "riemannZeta_two_mul_nat",
            "riemannZeta_neg_nat_eq_bernoulli",
            "riemannZeta_ne_zero_of_one_le_re",
            "riemannZeta_one_sub",
            "CRITICAL_STRIP_ONLY_NOT_CRITICAL_LINE",
            "HEIGHT_TRUNCATION_EQUIVALENCE_OPEN",
            "RH_EQUIVALENCE_OPEN",
        ):
            self.assertIn(required, text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("s.re = 1 / 2", text)
        self.assertNotIn("RiemannHypothesis :=", text)


if __name__ == "__main__":
    unittest.main()
