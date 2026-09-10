from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZetaDivisorExhaustionV1.lean"


class ZetaDivisorExhaustionV1Tests(unittest.TestCase):
    def test_required_exhaustion_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "def ZetaExhaustionRegionV1",
            "def ZetaExhaustionAdmissibleShapeV1",
            "def IsNontrivialZetaZeroShapeV1",
            "theorem zeta_exhaustion_exclusion_pos_v1",
            "theorem zeta_exhaustion_region_compact_v1",
            "theorem zeta_exhaustion_region_avoids_one_v1",
            "theorem zeta_exhaustion_region_admissible_shape_v1",
            "theorem zeta_exhaustion_covers_ne_one_v1",
            "theorem nontrivial_zeta_zero_covered_by_exhaustion_v1",
            "exists_nat_gt",
            "exists_nat_one_div_lt",
            "isCompact_closedBall",
            "Metric.isOpen_ball",
        ):
            self.assertIn(required, text)

    def test_scope_remains_preconvergence(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("GLOBAL_ZERO_SUM_CONVERGENCE_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_IDENTITY_OPEN", text)
        self.assertIn("DIVISOR_SUPPORT_MEMBERSHIP_BRIDGE_OPEN", text)
        self.assertNotIn("RiemannHypothesis :=", text)


if __name__ == "__main__":
    unittest.main()
