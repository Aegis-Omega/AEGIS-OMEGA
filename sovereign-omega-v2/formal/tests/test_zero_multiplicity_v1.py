from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZeroMultiplicityV1.lean"


class ZeroMultiplicityV1Tests(unittest.TestCase):
    def test_required_pointwise_multiplicity_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "def RiemannZeroMultiplicityV1",
            "theorem riemannZeta_order_ne_top_at_zero_v1",
            "theorem riemann_zero_multiplicity_pos_v1",
            "theorem riemann_zero_multiplicity_cast_eq_order_v1",
            "def WeilZeroSummandV1",
            "analyticOrderNatAt riemannZeta",
            "mellin f rho.1",
            "ZERO_MULTIPLICITY_SAFE_POINTWISE_ONLY",
            "GLOBAL_ZERO_SUM_OPEN",
            "GLOBAL_ZERO_SUM_CONVERGENCE_OPEN",
            "EXPLICIT_FORMULA_THEOREM_OPEN",
        ):
            self.assertIn(required, text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("∑'", text)
        self.assertNotIn("tsum", lowered)
        self.assertNotIn("RiemannHypothesis :=", text)


if __name__ == "__main__":
    unittest.main()
