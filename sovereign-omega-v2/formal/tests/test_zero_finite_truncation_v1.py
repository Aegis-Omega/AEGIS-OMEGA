from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "ZeroFiniteTruncationV1.lean"


class ZeroFiniteTruncationV1Tests(unittest.TestCase):
    def test_required_finite_truncation_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "def RiemannNontrivialZeroSetV1",
            "def ZeroRadialRegionV1",
            "def ZeroRadialSetV1",
            "theorem zero_radial_set_finite_v1",
            "def ZeroRadialFinsetV1",
            "theorem mem_zero_radial_finset_v1",
            "def WeilZeroRadialTruncatedSumV1",
            "def WeilZeroRadialLimitConventionV1",
            "FINITE_ZERO_TRUNCATION_ONLY",
            "GLOBAL_ZERO_LIMIT_PROOF_OPEN",
            "HEIGHT_TRUNCATION_EQUIVALENCE_OPEN",
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
        self.assertNotIn("theorem global_zero_limit", lowered)
        self.assertNotIn("RiemannHypothesis :=", text)


if __name__ == "__main__":
    unittest.main()
