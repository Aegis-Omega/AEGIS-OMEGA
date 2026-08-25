import unittest
from pathlib import Path

from coq_attestation import compare_assumption_baseline, inspect_coq_source
from coq_axiom_policy import (
    ABSTRACTION_PARAMETER,
    AUTHORITY_ELIGIBLE,
    CLASSICAL_REAL_FOUNDATION,
    DIAGNOSTIC_ONLY,
    evaluate_axiom_policy,
)


BASELINE = {
    "baseline_kind": "COQ_ASSUMPTION_BASELINE_V1",
    "baseline_source_commit": "a" * 40,
    "declared_assumptions": {},
    "theorem_assumptions": {},
    "admitted_sources": {},
}

ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / "formal" / "theories"


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


def _theorem_file(path: str, symbol: str, scope: str = AUTHORITY_ELIGIBLE) -> dict:
    return {
        "path": path,
        "evidence_scope": scope,
        "axiom_symbols": [],
        "parameter_symbols": [],
        "admitted_count": 0,
        "theorems": [{"theorem": "t", "assumption_symbols": [symbol]}],
    }


class CoqDiagnosticScopeTests(unittest.TestCase):
    def test_diagnostic_assumption_is_recorded_but_not_baseline_authority(self) -> None:
        diff = compare_assumption_baseline(
            [_probe(DIAGNOSTIC_ONLY)], BASELINE, "b" * 64
        )
        self.assertFalse(diff["regression"])
        self.assertEqual(diff["regression_count"], 0)
        self.assertEqual(diff["new_theorem_assumptions"], [])

    def test_same_assumption_is_regression_when_authority_eligible(self) -> None:
        diff = compare_assumption_baseline(
            [_probe(AUTHORITY_ELIGIBLE)], BASELINE, "b" * 64
        )
        self.assertTrue(diff["regression"])
        self.assertEqual(diff["regression_count"], 1)

    def test_diagnostic_policy_observation_never_becomes_permission(self) -> None:
        files = [
            _theorem_file(
                "Weil/O0TrustProbeReals.v",
                "ClassicalDedekindReals.sig_forall_dec",
                DIAGNOSTIC_ONLY,
            )
        ]
        policy = evaluate_axiom_policy(files)
        self.assertFalse(policy["policy_violation"])
        self.assertEqual(policy["permitted_assumptions"], [])
        self.assertEqual(len(policy["diagnostic_observations"]), 1)

    def test_classical_import_is_named_when_authority_surface_uses_it(self) -> None:
        policy = evaluate_axiom_policy(
            [_theorem_file("Weil/ClassicalAnalysis.v", "ClassicalDedekindReals.sig_forall_dec")]
        )
        self.assertFalse(policy["policy_violation"])
        self.assertEqual(
            policy["permitted_assumptions"][0]["category"],
            CLASSICAL_REAL_FOUNDATION,
        )

    def test_unlisted_theorem_assumption_fails_closed(self) -> None:
        policy = evaluate_axiom_policy(
            [_theorem_file("Weil/Shortcut.v", "MyProject.assume_global_weil")]
        )
        self.assertTrue(policy["policy_violation"])
        self.assertEqual(
            policy["unpermitted_assumptions"][0]["symbol"],
            "MyProject.assume_global_weil",
        )

    def test_source_axiom_cannot_hide_behind_parameter_allowlist(self) -> None:
        policy = evaluate_axiom_policy(
            [
                {
                    "path": "Core/HashLike.v",
                    "evidence_scope": AUTHORITY_ELIGIBLE,
                    "axiom_symbols": ["sha256"],
                    "parameter_symbols": [],
                    "admitted_count": 0,
                    "theorems": [],
                }
            ]
        )
        self.assertTrue(policy["policy_violation"])
        self.assertEqual(policy["unpermitted_assumptions"][0]["kind"], "SOURCE_AXIOM")

    def test_known_implementation_parameter_is_permitted(self) -> None:
        policy = evaluate_axiom_policy(
            [
                {
                    "path": "Core/Hash.v",
                    "evidence_scope": AUTHORITY_ELIGIBLE,
                    "axiom_symbols": [],
                    "parameter_symbols": ["sha256"],
                    "admitted_count": 0,
                    "theorems": [],
                }
            ]
        )
        self.assertFalse(policy["policy_violation"])
        self.assertEqual(policy["permitted_assumptions"][0]["category"], ABSTRACTION_PARAMETER)

    def test_admitted_is_never_permitted(self) -> None:
        policy = evaluate_axiom_policy(
            [
                {
                    "path": "Weil/WorkInProgress.v",
                    "evidence_scope": AUTHORITY_ELIGIBLE,
                    "axiom_symbols": [],
                    "parameter_symbols": [],
                    "admitted_count": 1,
                    "theorems": [],
                }
            ]
        )
        self.assertTrue(policy["policy_violation"])
        self.assertEqual(policy["admitted_sources"], ["Weil/WorkInProgress.v"])

    def test_live_tree_pins_single_legacy_target_claim_axiom(self) -> None:
        files = []
        for source in sorted(FORMAL.rglob("*.v")):
            relative = source.relative_to(FORMAL).as_posix()
            files.append(
                {
                    "path": relative,
                    **inspect_coq_source(source),
                    "theorems": [],
                }
            )
        self.assertGreaterEqual(len(files), 19)
        policy = evaluate_axiom_policy(files)
        source_axiom_violations = [
            item
            for item in policy["unpermitted_assumptions"]
            if item["kind"] == "SOURCE_AXIOM"
        ]
        self.assertEqual(
            [(item["location"], item["symbol"]) for item in source_axiom_violations],
            [("Bisimulation/ThreeWay.v", "cross_runtime_bisimulation")],
        )
        self.assertEqual(policy["admitted_sources"], [])

    def test_o0_authority_sources_have_no_declared_shortcuts(self) -> None:
        paths = [
            "Weil/AnalyticDefinitions.v",
            "Weil/Globalization.v",
            "Weil/WeilCriterion.v",
            "Weil/O0.v",
        ]
        files = []
        for relative in paths:
            source = FORMAL / relative
            files.append(
                {
                    "path": relative,
                    "evidence_scope": AUTHORITY_ELIGIBLE,
                    **inspect_coq_source(source),
                    "theorems": [],
                }
            )
        policy = evaluate_axiom_policy(files)
        self.assertFalse(policy["policy_violation"], policy)
        self.assertEqual(policy["unpermitted_assumptions"], [])
        self.assertEqual(policy["admitted_sources"], [])


if __name__ == "__main__":
    unittest.main()
