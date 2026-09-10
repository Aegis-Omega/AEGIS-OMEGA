from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bridges" / "lean" / "BombieriWeilTargetProbe.lean"


class BombieriWeilTargetProbeTests(unittest.TestCase):
    def test_probe_uses_concrete_mathlib_objects(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("def BombieriTestFunctionV1", text)
        self.assertIn("ContDiff ℝ ∞ f", text)
        self.assertIn("HasCompactSupport f", text)
        self.assertIn("tsupport f ⊆ Set.Ioi 0", text)
        self.assertIn("def BombieriMellinV1", text)
        self.assertIn("mellin f.1", text)
        self.assertIn("RiemannHypothesis", text)
        self.assertIn("riemannZeta", text)
        self.assertIn("completedRiemannZeta₀_one_sub", text)

    def test_compact_positive_support_gives_global_mellin_convergence(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("theorem bombieri_mellin_convergent_v1", text)
        self.assertIn("MellinConvergent f.1 s", text)
        self.assertIn("integrable_of_hasCompactSupport", text)

    def test_bombieri_moments_are_exact_mellin_endpoints(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("def BombieriMomentConditionsV1", text)
        self.assertIn("BombieriMellinV1 g 0 = 0", text)
        self.assertIn("BombieriMellinV1 g 1 = 0", text)
        self.assertIn("theorem bombieri_mellin_one_eq_integral_v1", text)
        self.assertIn("theorem bombieri_mellin_zero_eq_inverse_weighted_integral_v1", text)
        self.assertIn("cpow_neg_one", text)

    def test_probe_has_no_proof_escape_holes(self):
        text = SOURCE.read_text(encoding="utf-8")
        for forbidden in ("sorry", "axiom ", "opaque "):
            self.assertNotIn(forbidden, text.lower())


if __name__ == "__main__":
    unittest.main()
