#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "security" / "repository-enforcement-policy.json"
RULESET_PATH = ROOT / "security" / "main-branch-ruleset.payload.json"

GITHUB_ACTIONS_APP_ID = 15368
REQUIRED_CONTEXTS = (
    "Body cites current head",
    "aegis / kernel-one",
    "scan-pr / osv-scan",
    "aegis / automaton-2",
    "aegis / automaton-3",
    "Main branch enforcement",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RepositoryEnforcementContractTests(unittest.TestCase):
    def test_policy_and_payload_require_the_exact_pinned_check_set(self) -> None:
        policy = load(POLICY_PATH)
        payload = load(RULESET_PATH)
        policy_contexts = tuple(policy["policy"]["required_status_check_contexts"])
        self.assertEqual(policy_contexts, REQUIRED_CONTEXTS)
        self.assertEqual(
            policy["policy"]["required_status_check_integration_id"],
            GITHUB_ACTIONS_APP_ID,
        )

        status_rules = [
            rule for rule in payload["rules"] if rule.get("type") == "required_status_checks"
        ]
        self.assertEqual(len(status_rules), 1)
        parameters = status_rules[0]["parameters"]
        self.assertTrue(parameters["strict_required_status_checks_policy"])
        checks = parameters["required_status_checks"]
        self.assertEqual(tuple(check["context"] for check in checks), REQUIRED_CONTEXTS)
        self.assertTrue(
            all(check.get("integration_id") == GITHUB_ACTIONS_APP_ID for check in checks)
        )

    def test_ruleset_is_active_default_branch_only_and_has_no_bypass(self) -> None:
        payload = load(RULESET_PATH)
        self.assertEqual(payload["name"], "AEGIS Main Enforcement")
        self.assertEqual(payload["target"], "branch")
        self.assertEqual(payload["enforcement"], "active")
        self.assertEqual(payload["bypass_actors"], [])
        self.assertEqual(payload["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(payload["conditions"]["ref_name"]["exclude"], [])
        rule_types = {rule["type"] for rule in payload["rules"]}
        self.assertLessEqual(
            {
                "deletion",
                "non_fast_forward",
                "required_signatures",
                "pull_request",
                "required_status_checks",
            },
            rule_types,
        )


if __name__ == "__main__":
    unittest.main()
