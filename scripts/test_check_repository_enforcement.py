#!/usr/bin/env python3
from __future__ import annotations

import re
import unittest
from pathlib import Path
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
        self.assertEqual(result.source, "effective_repository_rulesets:no_splicing")
        self.assertEqual(result.missing_required_status_check_contexts, ())
        self.assertEqual(result.publisher_mismatch_contexts, ())
        self.assertEqual(result.evaluated_ruleset_id, 4242)
        self.assertEqual(result.all_effective_ruleset_ids, (4242,))
        self.assertFalse(any(path.endswith("/protection") for path in calls))

    def test_partial_guarantees_from_other_ruleset_are_not_spliced(self) -> None:
        rules = active_rules()
        for rule in rules:
            if rule["type"] in {"deletion", "required_signatures"}:
                rule["ruleset_id"] = 4343

        def fake_get(path: str, token: str | None):
            if path == f"/repos/{REPO}/branches/{BRANCH}":
                return 200, {"protected": True}
            if path == f"/repos/{REPO}/rules/branches/{BRANCH}?per_page=100":
                return 200, rules
            if path == f"/repos/{REPO}/rulesets?per_page=100&targets=branch":
                return 200, ruleset_inventory()
            self.fail(f"unexpected lookup: {path}")

        with patch.object(enforcement, "_get", side_effect=fake_get):
            result = enforcement.verify(REPO, BRANCH, "token", POLICY)

        self.assertFalse(result.ok)
        self.assertEqual(result.source, "effective_repository_rulesets:no_splicing")
        self.assertEqual(result.evaluated_ruleset_id, 4242)
        self.assertEqual(result.all_effective_ruleset_ids, (4242, 4343))
        self.assertFalse(result.deletion_blocked)
        self.assertFalse(result.signatures_required)
        self.assertEqual(result.as_dict()["production_admission"], "FORBIDDEN")

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


# T1: negative CI permission regression for untrusted PR-owned source.
# This is a source-contract check, not a GitHub provider authorization test.
def _runs_untrusted_pull_request(workflow: str) -> bool:
    lines = workflow.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("on:"):
            continue
        inline = line[3:].split("#", 1)[0].strip()
        if inline:
            return bool(re.search(r"\bpull_request\b", inline))
        for next_line in lines[i + 1:]:
            if next_line and not next_line[0].isspace():
                break
            if re.match(r"^  pull_request\s*:", next_line):
                return True
        return False
    return False


def _allows_pr_branch_mutation(workflow: str) -> bool:
    if not _runs_untrusted_pull_request(workflow):
        return False
    import re

    # A PR-owned workflow cannot inherit a repository writer or push directly.
    # OIDC is separate from the Git repository write-token capability.
    return bool(
        re.search(r"(?m)^\s*(?:contents|actions)\s*:\s*write\s*(?:#.*)?$", workflow)
        or re.search(r"(?m)^\s*permissions\s*:\s*write-all\s*(?:#.*)?$", workflow)
        or re.search(r"(?m)^\s*permissions\s*:\s*\{[^}\n]*\b(?:contents|actions)\s*:\s*write\b", workflow)
        or re.search(r"\bgit\s+push\b", workflow)
    )


class PullRequestWriteBoundaryTests(unittest.TestCase):
    def test_removed_legacy_pull_request_writer_stays_absent(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / ".github/workflows/typescript-source-lint-repair.yml").exists())

    def test_all_tracked_pull_request_workflows_are_git_read_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflows = sorted((root / ".github/workflows").glob("*.yml"))
        workflows += sorted((root / ".github/workflows").glob("*.yaml"))
        self.assertTrue(workflows, "No local workflows found; cannot audit")
        violations = [
            path.name for path in workflows
            if _allows_pr_branch_mutation(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(violations, [], f"PR workflow Git mutation risk: {violations}")

    def test_synthetic_pr_writer_with_checkout_is_denied(self) -> None:
        malicious = (
            "name: Unsafe PR mutation\non:\n  pull_request:\n"
            "permissions:\n  contents: write\n"
            "jobs:\n  mutate:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v4\n"
            "      - run: git push origin HEAD:main\n"
        )
        self.assertTrue(_allows_pr_branch_mutation(malicious))

    def test_synthetic_pr_writer_without_literal_git_push_is_denied(self) -> None:
        malicious = "on: [push, pull_request]\npermissions:\n  contents: write\n"
        self.assertTrue(_allows_pr_branch_mutation(malicious))

    def test_pr_scoped_write_all_is_denied(self) -> None:
        workflow = "on: [pull_request]\npermissions: write-all\n"
        self.assertTrue(_allows_pr_branch_mutation(workflow))

    def test_pr_scoped_inline_write_token_is_denied(self) -> None:
        workflow = "on: [pull_request]\npermissions: {contents: write}\n"
        self.assertTrue(_allows_pr_branch_mutation(workflow))

    def test_pr_scoped_read_token_does_not_allow_branch_write(self) -> None:
        safe = "on:\n  pull_request:\npermissions:\n  contents: read\n"
        self.assertFalse(_allows_pr_branch_mutation(safe))

    def test_oidc_does_not_count_as_git_repository_write_permission(self) -> None:
        oidc = "on:\n  pull_request:\npermissions:\n  contents: read\n  id-token: write\n"
        self.assertFalse(_allows_pr_branch_mutation(oidc))

    def test_manual_writer_is_not_misidentified_as_pr_execution(self) -> None:
        manual = "on:\n  workflow_dispatch:\npermissions:\n  contents: write\n"
        self.assertFalse(_allows_pr_branch_mutation(manual))


if __name__ == "__main__":
    unittest.main()
