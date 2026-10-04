from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "WeilCriterionCompactSmoothV1.lean"


class WeilCriterionCompactSmoothV1Tests(unittest.TestCase):
    def test_required_concrete_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for required in (
            "def WeilCompactSmoothGV1",
            "def WeilMomentConditionsV1",
            "def WeilAutocorrelationV1",
            "def WeilPrimeTermV1",
            "def WeilPrimeSumV1",
            "def WeilArchimedeanIntegrandV1",
            "def WeilExplicitRightSideV1",
            "def WeilExplicitRightSideConvergentV1",
            "def WeilCompactSmoothNegativityV1",
            "ArithmeticFunction.vonMangoldt",
            "Real.eulerMascheroniConstant",
            "star (g.1 y)",
        ):
            self.assertIn(required, text)

    def test_scope_is_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in ("sorry", "axiom ", "opaque ", "admit"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("RiemannHypothesis ↔ WeilCompactSmoothNegativityV1", text)
        self.assertIn("FULL_WEIL_CLASS_COVERAGE_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_THEOREM_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)


if __name__ == "__main__":
    unittest.main()
