import unittest

from coq_attestation import compare_assumption_baseline


BASELINE = {
    "baseline_kind": "COQ_ASSUMPTION_BASELINE_V1",
    "baseline_source_commit": "a" * 40,
    "declared_assumptions": {},
    "theorem_assumptions": {},
    "admitted_sources": {},
}


def _probe(scope: str) -> dict:
    return {
        "path": "Weil/O0TrustProbeReals.v",
        "evidence_scope": scope,
        "axiom_symbols": [],
        "parameter_symbols": [],
        "admitted_count": 0,
        "theorems": [
            {
                "theorem": "o0_trust_probe_reals_reflexive",
                "assumption_symbols": ["Classical.foo"],
            }
        ],
    }


class CoqDiagnosticScopeTests(unittest.TestCase):
    def test_diagnostic_assumption_is_recorded_but_not_baseline_authority(self) -> None:
        diff = compare_assumption_baseline(
            [_probe("DIAGNOSTIC_ONLY")], BASELINE, "b" * 64
        )
        self.assertFalse(diff["regression"])
        self.assertEqual(diff["regression_count"], 0)
        self.assertEqual(diff["new_theorem_assumptions"], [])

    def test_same_assumption_is_regression_when_authority_eligible(self) -> None:
        diff = compare_assumption_baseline(
            [_probe("AUTHORITY_ELIGIBLE")], BASELINE, "b" * 64
        )
        self.assertTrue(diff["regression"])
        self.assertEqual(diff["regression_count"], 1)
        self.assertEqual(
            diff["new_theorem_assumptions"],
            [
                {
                    "location": (
                        "Weil/O0TrustProbeReals.v::"
                        "o0_trust_probe_reals_reflexive"
                    ),
                    "symbol": "Classical.foo",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
