from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroShellAnalyticSynthesisV1.lean"


class ZeroShellAnalyticSynthesisV1Tests(unittest.TestCase):
    def test_required_synthesis_objects_exist(self):
        text = SOURCE.read_text()
        self.assertIn("import ZeroShellQuadraticBoundV1", text)
        self.assertIn("def ZeroHeightShellMultiplicityMassV1", text)
        self.assertIn("def HasLinearShellMultiplicityBoundV1", text)
        self.assertIn("def HasCubicShellMellinDecayV1", text)
        self.assertIn("theorem shell_count_and_mellin_decay_imply_quadratic_bound_v1", text)
        self.assertIn("WeilZeroIndexSummandV1", text)
        self.assertIn("analyticOrderNatAt riemannZeta", text)
        self.assertIn("HasQuadraticShellMassBoundV1", text)
        self.assertIn("ZERO_SHELL_ANALYTIC_SYNTHESIS_ONLY", text)

    def test_analytic_inputs_and_rh_remain_open(self):
        text = SOURCE.read_text()
        self.assertIn("ACTUAL_LINEAR_SHELL_MULTIPLICITY_BOUND_OPEN", text)
        self.assertIn("ACTUAL_CUBIC_SHELL_MELLIN_DECAY_OPEN", text)
        self.assertIn("ACTUAL_QUADRATIC_SHELL_BOUND_OPEN", text)
        self.assertIn("ZERO_COUNTING_BOUND_OPEN", text)
        self.assertIn("MELLIN_DECAY_ESTIMATE_OPEN", text)
        self.assertIn("WEIL_CLASS_SHELL_MASS_SUMMABILITY_OPEN", text)
        self.assertIn("EXPLICIT_FORMULA_OPEN", text)
        self.assertIn("CRITICAL_LINE_RE_HALF_OPEN", text)
        self.assertIn("RH_EQUIVALENCE_OPEN", text)
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotRegex(text, re.compile(r"\bopaque\b"))
        self.assertNotIn("theorem actual_quadratic_shell_bound", text)
        self.assertNotIn("s.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
