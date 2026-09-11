from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).parents[1] / "bridges" / "lean" / "ZeroCountingBoundV1.lean"


class ZeroCountingBoundV1Tests(unittest.TestCase):
    def test_required_actual_zero_counting_object_exists(self):
        text = SOURCE.read_text()
        self.assertIn("import ZeroShellAnalyticSynthesisV1", text)
        self.assertIn("def HasQuadraticShellMultiplicityBoundV1", text)
        self.assertIn("theorem riemann_zeta_has_quadratic_shell_multiplicity_bound_v1", text)
        self.assertIn("ZeroHeightShellMultiplicityMassV1", text)
        self.assertIn("ZERO_COUNTING_QUADRATIC_BOUND_V1", text)

    def test_scope_stays_quantitative_non_circular_and_admission_free(self):
        text = SOURCE.read_text()
        self.assertNotRegex(text, re.compile(r"\bsorry\b"))
        self.assertNotRegex(text, re.compile(r"\baxiom\b"))
        self.assertNotRegex(text, re.compile(r"\bopaque\b"))
        self.assertNotIn("RiemannHypothesis", text)
        self.assertNotIn("s.re = 1 / 2", text)
        self.assertNotIn("rho.re = 1 / 2", text)


if __name__ == "__main__":
    unittest.main()
