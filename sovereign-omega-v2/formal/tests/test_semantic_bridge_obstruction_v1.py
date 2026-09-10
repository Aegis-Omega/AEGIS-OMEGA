from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "theories" / "Weil" / "SemanticBridgeObstruction.v"


class SemanticBridgeObstructionTests(unittest.TestCase):
    def test_required_theorems_and_no_assumption_escape_hatches(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            "Theorem zero_quadratic_form_global_weil_positivity_v1", text
        )
        self.assertIn(
            "Theorem universal_global_weil_bridge_iff_target_v1", text
        )
        for forbidden in ("Axiom ", "Parameter ", "Admitted."):
            self.assertNotIn(forbidden, text)

    def test_obstruction_states_the_exact_abstract_bridge_shape(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            "(forall QW : QuadraticFormV1, GlobalWeilPositivityV1 QW -> P) <-> P",
            text,
        )
        self.assertIn("ZeroQuadraticFormV1", text)


if __name__ == "__main__":
    unittest.main()
