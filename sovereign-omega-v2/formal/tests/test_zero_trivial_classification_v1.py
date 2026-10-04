import unittest
from pathlib import Path


SOURCE = Path("sovereign-omega-v2/formal/bridges/lean/ZeroTrivialClassificationV1.lean")


class ZeroTrivialClassificationV1Tests(unittest.TestCase):
    def test_required_objects_exist(self):
        text = SOURCE.read_text(encoding="utf-8")
        for name in (
            "bernoulli_two_mul_ne_zero_v1",
            "riemann_zeta_neg_odd_ne_zero_v1",
            "riemann_zeta_neg_nat_zero_iff_trivial_v1",
        ):
            self.assertIn(name, text)

    def test_scope_remains_fail_closed(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("axiom ", text)
        self.assertNotIn("sorry", text)
        self.assertNotIn("theorem riemann_hypothesis", text.lower())
        self.assertNotIn("theorem full_critical_strip", text.lower())
        self.assertNotIn("theorem lower_zero_localization", text.lower())


if __name__ == "__main__":
    unittest.main()
