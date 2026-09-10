from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZetaZeroMultiplicityV1.lean"


class ZetaZeroMultiplicityV1Tests(unittest.TestCase):
    def test_required_multiplicity_theorem_exists(self):
        text = SOURCE.read_text()
        self.assertIn("ZetaZeroMultiplicityV1", text)
        self.assertIn("analyticOrderNatAt riemannZeta", text)
        self.assertIn("riemann_zeta_zero_multiplicity_pos_v1", text)
        self.assertIn("analyticOrderAt_eq_top", text)
        self.assertIn("eqOn_of_preconnected_of_eventuallyEq", text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text()
        self.assertIn("FINITE_MULTIPLICITY_BINDING_ONLY", text)
        self.assertIn("HEIGHT_ZERO_SUM_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotIn("RiemannHypothesis :=", text)
        self.assertNotIn("∑'", text)
        self.assertNotIn("tsum", text)


if __name__ == "__main__":
    unittest.main()
