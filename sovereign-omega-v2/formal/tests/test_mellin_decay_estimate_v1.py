from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "MellinDecayEstimateV1.lean"


class MellinDecayEstimateV1Tests(unittest.TestCase):
    def test_required_actual_decay_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("import WeilCriterionCompactSmoothV1", text)
        self.assertIn("import ZeroShellAnalyticSynthesisV1", text)
        self.assertIn("def HasUniformMellinVerticalCubicDecayV1", text)
        self.assertIn("theorem weil_compact_smooth_mellin_vertical_cubic_decay_v1", text)
        self.assertIn("theorem uniform_mellin_vertical_cubic_decay_implies_shell_decay_v1", text)
        self.assertIn("theorem weil_compact_smooth_has_cubic_shell_mellin_decay_v1", text)
        self.assertIn("MELLIN_VERTICAL_CUBIC_DECAY_V1", text)

    def test_scope_stays_non_circular_and_admission_free(self):
        text = SOURCE.read_text()
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotRegex(text, re.compile(r"\bopaque\b"))
        self.assertNotIn("s.re = 1 / 2", text)
        self.assertNotIn("rho.re = 1 / 2", text)
        self.assertNotIn("RiemannHypothesis", text)


if __name__ == "__main__":
    unittest.main()
