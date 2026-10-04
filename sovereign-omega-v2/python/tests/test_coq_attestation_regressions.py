import tempfile
import unittest
from pathlib import Path

from coq_attestation import compare_assumption_baseline, inspect_coq_source


class CoqAssumptionRegressionTests(unittest.TestCase):
    def test_added_parameter_symbol_on_same_statement_is_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ThreeWayLike.v"
            path.write_text("Parameter a b : nat.\n", encoding="utf-8")
            baseline_manifest = inspect_coq_source(path)

            path.write_text("Parameter a b c : nat.\n", encoding="utf-8")
            current_manifest = inspect_coq_source(path)

            self.assertEqual(baseline_manifest["parameter_statement_count"], 1)
            self.assertEqual(current_manifest["parameter_statement_count"], 1)
            self.assertEqual(baseline_manifest["parameter_symbol_count"], 2)
            self.assertEqual(current_manifest["parameter_symbol_count"], 3)

            files = [
                {
                    "path": "Bisimulation/ThreeWayLike.v",
                    "axiom_symbols": current_manifest["axiom_symbols"],
                    "parameter_symbols": current_manifest["parameter_symbols"],
                    "admitted_count": 0,
                    "theorems": [],
                }
            ]
            baseline = {
                "baseline_kind": "COQ_ASSUMPTION_BASELINE_V1",
                "baseline_source_commit": "a" * 40,
                "declared_assumptions": {
                    "Bisimulation/ThreeWayLike.v": baseline_manifest[
                        "parameter_symbols"
                    ]
                },
                "theorem_assumptions": {},
                "admitted_sources": {},
            }

            diff = compare_assumption_baseline(files, baseline, "b" * 64)
            self.assertTrue(diff["regression"])
            self.assertEqual(diff["regression_count"], 1)
            self.assertEqual(
                diff["new_declared_assumptions"],
                [{"location": "Bisimulation/ThreeWayLike.v", "symbol": "c"}],
            )

    def test_new_admitted_source_is_regression_even_when_compile_can_pass(self) -> None:
        files = [
            {
                "path": "Core/Temporary.v",
                "axiom_symbols": [],
                "parameter_symbols": [],
                "admitted_count": 1,
                "theorems": [],
            }
        ]
        baseline = {
            "baseline_kind": "COQ_ASSUMPTION_BASELINE_V1",
            "baseline_source_commit": "c" * 40,
            "declared_assumptions": {},
            "theorem_assumptions": {},
            "admitted_sources": {},
        }

        diff = compare_assumption_baseline(files, baseline, "d" * 64)
        self.assertTrue(diff["regression"])
        self.assertEqual(diff["regression_count"], 1)
        self.assertEqual(
            diff["new_admitted_sources"],
            [
                {
                    "path": "Core/Temporary.v",
                    "baseline_count": 0,
                    "current_count": 1,
                }
            ],
        )

    def test_removed_assumption_is_strengthening_not_regression(self) -> None:
        files = [
            {
                "path": "Core/Hash.v",
                "axiom_symbols": [],
                "parameter_symbols": [],
                "admitted_count": 0,
                "theorems": [],
            }
        ]
        baseline = {
            "baseline_kind": "COQ_ASSUMPTION_BASELINE_V1",
            "baseline_source_commit": "e" * 40,
            "declared_assumptions": {"Core/Hash.v": ["sha256"]},
            "theorem_assumptions": {},
            "admitted_sources": {},
        }

        diff = compare_assumption_baseline(files, baseline, "f" * 64)
        self.assertFalse(diff["regression"])
        self.assertEqual(diff["regression_count"], 0)
        self.assertEqual(
            diff["removed_declared_assumptions"],
            [{"location": "Core/Hash.v", "symbol": "sha256"}],
        )


if __name__ == "__main__":
    unittest.main()
