"""Meta-verification of the independent System Foundry acceptance oracle."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from harness.sdk.generator.oracle_mutation import run_mutation_campaign


def sample():
    return {
        "system_id": "meta-verify-api", "kind": "readonly-json-api",
        "routes": {
            "/health": {"status": "ok"},
            "/count": {"count": 3},
        },
    }


class OracleMutationSensitivityTests(unittest.TestCase):
    def test_nine_known_behavioral_mutants_must_be_detected(self):
        audit = run_mutation_campaign(sample())
        self.assertEqual(audit["mutant_count"], 9)
        self.assertEqual(audit["mutants_killed"], 9)
        self.assertEqual(audit["outcome"], "ORACLE_SENSITIVITY_PASS")
        self.assertEqual(audit["admission"], "NOT_ADMITTED")
        self.assertFalse(audit["authority_granted"])
        self.assertEqual(audit["baseline"]["outcome"], "ORACLE_PASS")
        self.assertTrue(all(m["killed_by_oracle"] for m in audit["mutations"]))

    def test_oracle_that_approves_everything_fails_meta_test(self):
        from harness.sdk.generator.oracle_mutation import _MUTATIONS
        n = len(_MUTATIONS) + 1
        with patch(
            "harness.sdk.generator.oracle_mutation._run_oracle",
            return_value={"outcome": "ORACLE_PASS", "exit_code": 0,
                          "passed": 8, "total": 8},
        ):
            audit = run_mutation_campaign(sample())
        self.assertEqual(audit["mutants_killed"], 0)
        self.assertEqual(audit["outcome"], "ORACLE_SENSITIVITY_FAIL")

    def test_broken_baseline_denied(self):
        with patch(
            "harness.sdk.generator.oracle_mutation._run_oracle",
            return_value={"outcome": "ORACLE_FAIL", "exit_code": 1},
        ):
            with self.assertRaisesRegex(ValueError, "BASELINE_ORACLE"):
                run_mutation_campaign(sample())

    def test_mutation_anchor_must_be_exact(self):
        with patch(
            "harness.sdk.generator.oracle_mutation._MUTATIONS",
            (("INVALID_MUTATION", "a line never present", "changed"),),
        ):
            with self.assertRaisesRegex(ValueError, "MUTATION_ANCHOR_INVALID"):
                run_mutation_campaign(sample())

    def test_malformed_timeout_denied(self):
        for timeout in (0, 31, -1, True, "12"):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                run_mutation_campaign(sample(), timeout=timeout)


if __name__ == "__main__":
    unittest.main()
