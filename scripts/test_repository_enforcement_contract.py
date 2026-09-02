#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "security" / "repository-enforcement-policy.json"
RULESET_PATH = ROOT / "security" / "main-branch-ruleset.payload.json"
TRUSTED_WORKFLOW_RULESET_PATH = ROOT / "security" / "org-main-trusted-admission.payload.json"

GITHUB_ACTIONS_APP_ID = 15368
REQUIRED_CONTEXTS = (
    "Body cites current head",
    "aegis / kernel-one",
    "scan-pr / osv-scan",
    "aegis / automaton-2",
    "aegis / automaton-3",
    "Main branch enforcement",
)
TRUSTED_WORKFLOW = ".github/workflows/trusted-cognitive-admission.yml"
TRUSTED_SOURCE_REF = "refs/heads/main"
TRUSTED_SOURCE_SHA = "3934ef62316ad5e63a78042fd01fd4b75a082cb5"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RepositoryEnforcementContractTests(unittest.TestCase):
    def test_policy_and_deployable_ruleset_require_exact_a2_a3_gate_set(self) -> None:
        policy = load(POLICY_PATH)
        payload = load(RULESET_PATH)
        policy_contexts = tuple(policy["policy"]["required_status_check_contexts"])
        self.assertEqual(policy_contexts, REQUIRED_CONTEXTS)
        self.assertEqual(policy["policy"]["required_status_check_integration_id"], GITHUB_ACTIONS_APP_ID)
        required_checks_rules = [rule for rule in payload["rules"] if rule.get("type") == "required_status_checks"]
        self.assertEqual(len(required_checks_rules), 1)
        params = required_checks_rules[0]["parameters"]
        self.assertTrue(params["strict_required_status_checks_policy"])
        checks = params["required_status_checks"]
        self.assertEqual(tuple(check["context"] for check in checks), REQUIRED_CONTEXTS)
        self.assertTrue(all(check.get("integration_id") == GITHUB_ACTIONS_APP_ID for check in checks))
        self.assertIn("aegis / automaton-2", policy_contexts)
        self.assertIn("aegis / automaton-3", policy_contexts)

    def test_ruleset_is_active_default_branch_only_and_has_no_bypass(self) -> None:
        payload = load(RULESET_PATH)
        self.assertEqual(payload["name"], "AEGIS Main Enforcement")
        self.assertEqual(payload["target"], "branch")
        self.assertEqual(payload["enforcement"], "active")
        self.assertEqual(payload["bypass_actors"], [])
        self.assertEqual(payload["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(payload["conditions"]["ref_name"]["exclude"], [])
        rule_types = {rule["type"] for rule in payload["rules"]}
        self.assertTrue({"deletion", "non_fast_forward", "required_signatures", "pull_request", "required_status_checks"} <= rule_types)

    def test_trusted_admission_is_source_pinned_to_verified_main_not_feature_branch(self) -> None:
        payload = load(TRUSTED_WORKFLOW_RULESET_PATH)
        self.assertEqual(payload["bypass_actors"], [])
        self.assertEqual(payload["conditions"]["repository_id"]["repository_ids"], [1095915905])
        workflow_rules = [rule for rule in payload["rules"] if rule.get("type") == "workflows"]
        self.assertEqual(len(workflow_rules), 1)
        workflows = workflow_rules[0]["parameters"]["workflows"]
        self.assertEqual(len(workflows), 1)
        workflow = workflows[0]
        self.assertEqual(workflow["path"], TRUSTED_WORKFLOW)
        self.assertEqual(workflow["ref"], TRUSTED_SOURCE_REF)
        self.assertEqual(workflow["repository_id"], 1095915905)
        self.assertEqual(workflow["sha"], TRUSTED_SOURCE_SHA)
        self.assertNotIn("repair/", workflow["ref"])


if __name__ == "__main__":
    unittest.main()
