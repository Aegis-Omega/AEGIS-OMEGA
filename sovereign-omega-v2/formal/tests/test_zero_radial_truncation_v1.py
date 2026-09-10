from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZeroRadialTruncationV1.lean"


class ZeroRadialTruncationV1Tests(unittest.TestCase):
    def test_required_finite_truncation_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "open scoped BigOperators",
            "def RiemannRadialZeroSetV1",
            "theorem riemann_radial_zero_set_finite_v1",
            "def RiemannRadialZeroFinsetV1",
            "theorem mem_riemann_radial_zero_finset_v1",
            "def WeilRadialZeroSumV1",
            "theorem nontrivial_zero_mem_radial_at_norm_v1",
            "Metric.closedBall",
            "inter_riemannZetaZeros_finite",
            "WeilZeroSummandV1",
            "FINITE_RADIAL_ZERO_SUM_ONLY",
            "SUMMATION_CONVENTION_EQ_BOMBIERI_OPEN",
            "TRUNCATED_LIMIT_CONVERGENCE_OPEN",
            "EXPLICIT_FORMULA_THEOREM_OPEN",
        ):
            self.assertIn(required, text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("tsum", lowered)
        self.assertNotIn("RiemannHypothesis :=", text)
        self.assertNotIn("TRUNCATED_LIMIT_CONVERGENCE_VERIFIED", text)


if __name__ == "__main__":
    unittest.main()
