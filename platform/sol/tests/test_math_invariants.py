from __future__ import annotations

from pathlib import Path
import sys
import unittest

VERIFIER_DIR = Path(__file__).resolve().parents[1] / "verifiers"
sys.path.insert(0, str(VERIFIER_DIR))

from math_invariants import (  # noqa: E402
    MathInvariantError,
    attention_score,
    to_evidence,
    verify_golden_quorum,
)


class MathInvariantTests(unittest.TestCase):
    def test_618_is_approximate_golden_conjugate_not_its_inverse(self):
        result = verify_golden_quorum()
        self.assertEqual(result.threshold, "0.618")
        self.assertFalse(result.equals_inverse_of_defined_phi)
        self.assertLess(float(result.absolute_error), 0.0001)

    def test_verification_is_deterministic_and_non_authoritative(self):
        first = verify_golden_quorum()
        second = verify_golden_quorum()
        self.assertEqual(first.evidence_digest, second.evidence_digest)
        self.assertFalse(to_evidence(first)["grants_authority"])

    def test_attention_score_increases_with_stress(self):
        low = attention_score(sigma_one=1.0, d_k=64, atp=2100, stress_norm=0.2)
        high = attention_score(sigma_one=1.0, d_k=64, atp=2100, stress_norm=0.8)
        self.assertGreater(high, low)

    def test_attention_score_decreases_with_atp(self):
        low_atp = attention_score(sigma_one=1.0, d_k=64, atp=500, stress_norm=0.4)
        high_atp = attention_score(sigma_one=1.0, d_k=64, atp=2100, stress_norm=0.4)
        self.assertGreater(low_atp, high_atp)

    def test_attention_score_rejects_undefined_denominator(self):
        with self.assertRaises(MathInvariantError):
            attention_score(sigma_one=1.0, d_k=64, atp=0, stress_norm=0.4)


if __name__ == "__main__":
    unittest.main()
