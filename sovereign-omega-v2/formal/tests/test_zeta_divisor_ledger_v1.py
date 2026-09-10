from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZetaDivisorLedgerV1.lean"


class ZetaDivisorLedgerV1Tests(unittest.TestCase):
    def test_required_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "def ZetaAdmissibleCompactV1",
            "def ZetaDivisorV1",
            "def IsNontrivialZetaZeroV1",
            "theorem zeta_analytic_on_admissible_compact_v1",
            "theorem zeta_divisor_support_finite_v1",
            "theorem zeta_divisor_apply_eq_analytic_order_v1",
            "def ZetaNontrivialDivisorSupportFinsetV1",
            "def ZetaNontrivialWeightedLedgerSumV1",
            "analyticOn_riemannZeta",
            "MeromorphicOn.divisor",
        ):
            self.assertIn(required, text)

    def test_global_zero_sum_is_not_claimed(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("GLOBAL_ZERO_SUM_CONVERGENCE_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_IDENTITY_OPEN", text)
        self.assertNotIn("RiemannHypothesis :=", text)


if __name__ == "__main__":
    unittest.main()
