from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "WeilZeroSideInterfaceV1.lean"


class WeilZeroSideInterfaceV1Tests(unittest.TestCase):
    def test_required_zero_side_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "def WeilNontrivialZeroV1",
            "def WeilMellinAtZeroV1",
            "theorem rh_places_nontrivial_zero_on_critical_line_v1",
            "riemannZeta",
            "RiemannHypothesis",
            "mellin f rho.1",
            "ZERO_MULTIPLICITY_ENUMERATION_OPEN",
            "ZERO_SIDE_GLOBAL_SUM_OPEN",
            "EXPLICIT_FORMULA_THEOREM_OPEN",
        ):
            self.assertIn(required, text)

    def test_scope_is_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("theorem riemann_hypothesis", lowered)
        self.assertNotIn("def WeilGlobalZeroSumV1", text)
        self.assertNotIn("∑' ρ", text)


if __name__ == "__main__":
    unittest.main()
