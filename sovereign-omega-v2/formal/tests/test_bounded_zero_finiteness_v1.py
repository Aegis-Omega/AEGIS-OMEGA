from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "BoundedZeroFinitenessV1.lean"


class BoundedZeroFinitenessV1Tests(unittest.TestCase):
    def test_required_objects_and_theorems_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "def RiemannZeroSetOnV1",
            "theorem riemannZeta_analyticOrderAt_ne_top_v1",
            "theorem riemann_zero_set_finite_on_compact_away_one_v1",
            "analyticOn_riemannZeta",
            "analyticOrderAt_eq_top",
            "eqOn_of_preconnected_of_eventuallyEq",
            "divisor_support_finite_of_subset",
            "riemannZeta_zero",
            "BOUNDED_ZERO_FINITE_SUPPORT_ONLY",
            "GLOBAL_ZERO_ENUMERATION_OPEN",
            "GLOBAL_ZERO_SUM_OPEN",
        ):
            self.assertIn(required, text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("def GlobalZeroEnumeration", text)
        self.assertNotIn("∑' rho", text)
        self.assertNotIn("RiemannHypothesis :=", text)


if __name__ == "__main__":
    unittest.main()
