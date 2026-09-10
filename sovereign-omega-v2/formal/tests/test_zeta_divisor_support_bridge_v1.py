from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZetaDivisorSupportBridgeV1.lean"


class ZetaDivisorSupportBridgeV1Tests(unittest.TestCase):
    def test_required_bridge_theorems_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "theorem zeta_meromorphic_order_ne_top_v1",
            "theorem zeta_zero_divisor_coeff_ne_zero_v1",
            "theorem zeta_zero_mem_divisor_support_v1",
            "theorem nontrivial_zero_mem_filtered_ledger_v1",
            "theorem nontrivial_zero_occurs_in_some_finite_ledger_v1",
            "riemannZeta_ne_zero_of_one_lt_re",
            "eqOn_zero_of_preconnected_of_frequently_eq_zero",
            "meromorphicOrderAt_eq_top_iff",
            "Function.mem_support",
        ):
            self.assertIn(required, text)

    def test_scope_remains_preconvergence(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("GLOBAL_ZERO_SUM_CONVERGENCE_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_IDENTITY_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotIn("RiemannHypothesis :=", text)


if __name__ == "__main__":
    unittest.main()
