#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

import check_repository_enforcement as enforcement


REPO = "Aegis-Omega/AEGIS-OMEGA"
BRANCH = "main"
GITHUB_ACTIONS_APP_ID = 15368
CONTEXTS = (
    "Body cites current head",
    "aegis / kernel-one",
    "scan-pr / osv-scan",
    "Main branch enforcement",
)
POLICY = enforcement.Policy(
    ruleset_name="AEGIS Main Enforcement",
    required_approving_review_count=0,
    dismiss_stale_reviews_on_push=False,
    require_last_push_approval=False,
    require_code_owner_review=False,
    require_conversation_resolution=True,
    require_branches_up_to_date=True,
    required_status_check_integration_id=GITHUB_ACTIONS_APP_ID,
    required_status_check_contexts=CONTEXTS,
)


def active_rules(
    contexts: tuple[str, ...] = CONTEXTS,
    *,
    strict: bool = True,
    integration_id: int | None = GITHUB_ACTIONS_APP_ID,
):
    checks = []
    for context in contexts:
        check = {"context": context}
        if integration_id is not None:
            check["integration_id"] = integration_id
        checks.append(check)
    return [
        {
            "type": "deletion",
            "ruleset_source_type": "Repository",
            "ruleset_source": REPO,
            "ruleset_id": 4242,
        },
        {
            "type": "non_fast_forward",
            "ruleset_source_type": "Repository",
            "ruleset_source": REPO,
            "ruleset_id": 4242,
        },
        {
            "type": "required_signatures",
            "ruleset_source_type": "Repository",
            "ruleset_source": REPO,
            "ruleset_id": 4242,
        },
        {
            "type": "pull_request",
            "ruleset_source_type": "Repository",
            "ruleset_source": REPO,
            "ruleset_id": 4242,
            "parameters": {
                "allowed_merge_methods": ["merge", "squash", "rebase"],
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_approving_review_count": 0,
                "required_review_thread_resolution": True,
            },
        },
        {
            "type": "required_status_checks",
            "ruleset_source_type": "Repository",
            "ruleset_source": REPO,
            "ruleset_id": 4242,
            "parameters": {
                "do_not_enforce_on_create": False,
                "required_status_checks": checks,
                "strict_required_status_checks_policy": strict,
            },
        },
    ]


def ruleset_inventory():
    return [
        {
            "id": 4242,
            "name": "AEGIS Main Enforcement",
            "target": "branch",
            "source_type": "Repository",
            "source": REPO,
            "enforcement": "active",
        }
    ]


class RepositoryEnforcementTests(unittest.TestCase):
    def test_unprotected_branch_denies_without_ruleset_lookup(self) -> None:
        calls: list[str] = []

        def fake_get(path: str, token: str | None):
            calls.append(path)
            if path == f"/repos/{REPO}/branches/{BRANCH}":
                return 200, {"name": BRANCH, "protected": False}
            self.fail(f"unexpected lookup: {path}")

        with patch.object(enforcement, "_get", side_effect=fake_get):
            result = enforcement.verify(REPO, BRANCH, "token", POLICY)

        self.assertFalse(result.ok)
        self.assertEqual(result.source, "branch_endpoint:protected=false")
        self.assertEqual(calls, [f"/repos/{REPO}/branches/{BRANCH}"])
        self.assertEqual(result.as_dict()["production_admission"], "FORBIDDEN")
        self.assertEqual(set(result.missing_required_status_check_contexts), set(CONTEXTS))

    def test_active_effective_rules_satisfy_contract_without_privileged_protection_api(self) -> None:
        calls: list[str] = []

        def fake_get(path: str, token: str | None):
            calls.append(path)
            if path == f"/repos/{REPO}/branches/{BRANCH}":
                return 200, {"name": BRANCH, "protected": True}
            if path == f"/repos/{REPO}/rules/branches/{BRANCH}?per_page=100":
                return 200, active_rules()
            if path == f"/repos/{REPO}/rulesets?per_page=100&targets=branch":
                return 200, ruleset_inventory()
            self.fail(f"unexpected lookup: {path}")

        with patch.object(enforcement, "_get", side_effect=fake_get):
            result = enforcement.verify(REPO, BRANCH, "token", POLICY)

        self.assertTrue(result.ok)
        self.assertEqual(result.source, "effective_repository_rulesets")
        self.assertEqual(result.missing_required_status_check_contexts, ())
        self.assertEqual(result.publisher_mismatch_contexts, ())
        self.assertEqual(result.effective_ruleset_ids, (4242,))
        self.assertFalse(any(path.endswith("/protection") for path in calls))

    def test_missing_required_check_is_verified_deny(self) -> None:
        missing = CONTEXTS[:-1]

        def fake_get(path: str, token: str | None):
            if path == f"/repos/{REPO}/branches/{BRANCH}":
                return 200, {"protected": True}
            if path == f"/repos/{REPO}/rules/branches/{BRANCH}?per_page=100":
                return 200, active_rules(missing)
            if path == f"/repos/{REPO}/rulesets?per_page=100&targets=branch":
                return 200, ruleset_inventory()
            self.fail(f"unexpected lookup: {path}")

        with patch.object(enforcement, "_get", side_effect=fake_get):
            result = enforcement.verify(REPO, BRANCH, "token", POLICY)

        self.assertFalse(result.ok)
        self.assertFalse(result.required_status_check_contexts_complete)
        self.assertEqual(result.missing_required_status_check_contexts, ("Main branch enforcement",))
        self.assertEqual(result.as_dict()["production_admission"], "FORBIDDEN")

    def test_non_strict_required_checks_are_rejected(self) -> None:
        def fake_get(path: str, token: str | None):
            if path == f"/repos/{REPO}/branches/{BRANCH}":
                return 200, {"protected": True}
            if path == f"/repos/{REPO}/rules/branches/{BRANCH}?per_page=100":
                return 200, active_rules(strict=False)
            if path == f"/repos/{REPO}/rulesets?per_page=100&targets=branch":
                return 200, ruleset_inventory()
            self.fail(f"unexpected lookup: {path}")

        with patch.object(enforcement, "_get", side_effect=fake_get):
            result = enforcement.verify(REPO, BRANCH, "token", POLICY)

        self.assertFalse(result.ok)
        self.assertFalse(result.branches_up_to_date_required)

    def test_unpinned_same_name_status_checks_are_rejected(self) -> None:
        def fake_get(path: str, token: str | None):
            if path == f"/repos/{REPO}/branches/{BRANCH}":
                return 200, {"protected": True}
            if path == f"/repos/{REPO}/rules/branches/{BRANCH}?per_page=100":
                return 200, active_rules(integration_id=None)
            if path == f"/repos/{REPO}/rulesets?per_page=100&targets=branch":
                return 200, ruleset_inventory()
            self.fail(f"unexpected lookup: {path}")

        with patch.object(enforcement, "_get", side_effect=fake_get):
            result = enforcement.verify(REPO, BRANCH, "token", POLICY)

        self.assertFalse(result.ok)
        self.assertFalse(result.required_status_check_publishers_pinned)
        self.assertEqual(set(result.publisher_mismatch_contexts), set(CONTEXTS))


if __name__ == "__main__":
    unittest.main()
