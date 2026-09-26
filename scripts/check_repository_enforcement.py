#!/usr/bin/env python3
"""Fail-closed verifier for the AEGIS default-branch repository ruleset.

V3 requires exact equality between the source contract and the named live
repository ruleset for publisher-bound status checks, and verifies the live
`require_extra_approval_for_unattributed_changes` pull-request control.
Unmodeled live checks are drift, not harmless strengthening.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API = "https://api.github.com"
API_VERSION = "2026-03-10"
DEFAULT_POLICY = (
    Path(__file__).resolve().parents[1]
    / "security"
    / "repository-enforcement-policy.json"
)


class EnforcementError(RuntimeError):
    pass


@dataclass(frozen=True)
class Policy:
    ruleset_name: str
    required_approving_review_count: int
    dismiss_stale_reviews_on_push: bool
    require_last_push_approval: bool
    require_code_owner_review: bool
    require_conversation_resolution: bool
    require_extra_approval_for_unattributed_changes: bool
    require_branches_up_to_date: bool
    required_status_check_integration_id: int
    required_status_check_contexts: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        policy = raw.get("policy")
        if not isinstance(policy, dict):
            raise EnforcementError("repository enforcement policy has no policy object")
        contexts = policy.get("required_status_check_contexts")
        if (
            not isinstance(contexts, list)
            or not contexts
            or not all(isinstance(x, str) and x for x in contexts)
            or len(contexts) != len(set(contexts))
        ):
            raise EnforcementError(
                "required_status_check_contexts must be unique non-empty strings"
            )
        integration_id = policy.get("required_status_check_integration_id")
        if not isinstance(integration_id, int) or integration_id <= 0:
            raise EnforcementError(
                "required_status_check_integration_id must be a positive integer"
            )
        return cls(
            ruleset_name=str(raw.get("ruleset_name") or "AEGIS Main Enforcement"),
            required_approving_review_count=int(
                policy.get("required_approving_review_count", 0)
            ),
            dismiss_stale_reviews_on_push=bool(
                policy.get("dismiss_stale_reviews_on_push", False)
            ),
            require_last_push_approval=bool(
                policy.get("require_last_push_approval", False)
            ),
            require_code_owner_review=bool(
                policy.get("require_code_owner_review", False)
            ),
            require_conversation_resolution=bool(
                policy.get("require_conversation_resolution", True)
            ),
            require_extra_approval_for_unattributed_changes=bool(
                policy.get(
                    "require_extra_approval_for_unattributed_changes",
                    False,
                )
            ),
            require_branches_up_to_date=bool(
                policy.get("require_branches_up_to_date", True)
            ),
            required_status_check_integration_id=integration_id,
            required_status_check_contexts=tuple(contexts),
        )


@dataclass(frozen=True)
class Result:
    protected: bool
    named_ruleset_active: bool
    pull_request_required: bool
    review_policy_matches: bool
    conversation_resolution_required: bool
    extra_approval_for_unattributed_changes_matches: bool
    status_checks_required: bool
    required_status_check_bindings_exact: bool
    branches_up_to_date_required: bool
    force_push_blocked: bool
    deletion_blocked: bool
    signatures_required: bool
    source: str
    evaluated_ruleset_id: int | None = None
    observed_require_extra_approval_for_unattributed_changes: bool = False
    observed_required_status_check_bindings: tuple[tuple[str, int | None], ...] = ()
    missing_required_status_check_bindings: tuple[tuple[str, int], ...] = ()
    unexpected_required_status_check_bindings: tuple[
        tuple[str, int | None], ...
    ] = ()
    all_effective_ruleset_ids: tuple[int, ...] = ()

    @property
    def ok(self) -> bool:
        return all(
            (
                self.protected,
                self.named_ruleset_active,
                self.pull_request_required,
                self.review_policy_matches,
                self.conversation_resolution_required,
                self.extra_approval_for_unattributed_changes_matches,
                self.status_checks_required,
                self.required_status_check_bindings_exact,
                self.branches_up_to_date_required,
                self.force_push_blocked,
                self.deletion_blocked,
                self.signatures_required,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        observed_contexts = sorted(
            {context for context, _ in self.observed_required_status_check_bindings}
        )
        missing_contexts = sorted(
            {context for context, _ in self.missing_required_status_check_bindings}
        )
        unexpected_contexts = sorted(
            {context for context, _ in self.unexpected_required_status_check_bindings}
        )
        return {
            "protected": self.protected,
            "named_ruleset_active": self.named_ruleset_active,
            "pull_request_required": self.pull_request_required,
            "review_policy_matches": self.review_policy_matches,
            "conversation_resolution_required": self.conversation_resolution_required,
            "extra_approval_for_unattributed_changes_matches":
                self.extra_approval_for_unattributed_changes_matches,
            "observed_require_extra_approval_for_unattributed_changes":
                self.observed_require_extra_approval_for_unattributed_changes,
            "status_checks_required": self.status_checks_required,
            "required_status_check_bindings_exact":
                self.required_status_check_bindings_exact,
            # Backward-readable field names:
            "required_status_check_contexts_complete":
                self.required_status_check_bindings_exact,
            "required_status_check_publishers_pinned":
                self.required_status_check_bindings_exact,
            "branches_up_to_date_required": self.branches_up_to_date_required,
            "force_push_blocked": self.force_push_blocked,
            "deletion_blocked": self.deletion_blocked,
            "signatures_required": self.signatures_required,
            "evaluated_ruleset_id": self.evaluated_ruleset_id,
            "observed_required_status_check_contexts": observed_contexts,
            "missing_required_status_check_contexts": missing_contexts,
            "unexpected_required_status_check_contexts": unexpected_contexts,
            "observed_required_status_check_bindings": [
                {"context": c, "integration_id": i}
                for c, i in self.observed_required_status_check_bindings
            ],
            "missing_required_status_check_bindings": [
                {"context": c, "integration_id": i}
                for c, i in self.missing_required_status_check_bindings
            ],
            "unexpected_required_status_check_bindings": [
                {"context": c, "integration_id": i}
                for c, i in self.unexpected_required_status_check_bindings
            ],
            "all_effective_ruleset_ids": list(self.all_effective_ruleset_ids),
            "source": self.source,
            "production_admission": "ELIGIBLE" if self.ok else "FORBIDDEN",
        }


def _get(path: str, token: str | None) -> tuple[int, Any]:
    req = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "aegis-repository-enforcement/3",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"message": body}
        return exc.code, parsed


def _parameters(rule: dict[str, Any]) -> dict[str, Any]:
    value = rule.get("parameters")
    return value if isinstance(value, dict) else {}


def _named_active_ruleset_id(
    repo: str, token: str | None, policy: Policy
) -> int | None:
    status, rulesets = _get(
        f"/repos/{repo}/rulesets?per_page=100&targets=branch", token
    )
    if status != 200 or not isinstance(rulesets, list):
        raise EnforcementError(
            f"ruleset inventory lookup failed: HTTP {status}: {rulesets}"
        )
    matches = [
        item.get("id")
        for item in rulesets
        if isinstance(item, dict)
        and item.get("name") == policy.ruleset_name
        and item.get("enforcement") == "active"
        and item.get("source_type") == "Repository"
        and item.get("source") == repo
        and isinstance(item.get("id"), int)
    ]
    if len(matches) > 1:
        raise EnforcementError(
            f"ambiguous active rulesets named {policy.ruleset_name!r}: {matches}"
        )
    return matches[0] if matches else None


def _deny(source: str, policy: Policy, *, protected: bool = False) -> Result:
    required = tuple(
        sorted(
            (context, policy.required_status_check_integration_id)
            for context in policy.required_status_check_contexts
        )
    )
    return Result(
        protected=protected,
        named_ruleset_active=False,
        pull_request_required=False,
        review_policy_matches=False,
        conversation_resolution_required=False,
        extra_approval_for_unattributed_changes_matches=False,
        status_checks_required=False,
        required_status_check_bindings_exact=False,
        branches_up_to_date_required=False,
        force_push_blocked=False,
        deletion_blocked=False,
        signatures_required=False,
        source=source,
        missing_required_status_check_bindings=required,
    )


def _effective_rules(
    repo: str,
    branch: str,
    token: str | None,
    protected: bool,
    policy: Policy,
) -> Result:
    named_ruleset_id = _named_active_ruleset_id(repo, token, policy)
    if named_ruleset_id is None:
        return _deny("named_ruleset_not_active", policy, protected=protected)

    status, rules = _get(
        f"/repos/{repo}/rules/branches/"
        f"{urllib.parse.quote(branch, safe='')}?per_page=100",
        token,
    )
    if status != 200 or not isinstance(rules, list):
        raise EnforcementError(
            f"effective branch rules lookup failed: HTTP {status}: {rules}"
        )

    all_ruleset_ids: set[int] = set()
    named_rules: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        ruleset_id = rule.get("ruleset_id")
        if isinstance(ruleset_id, int):
            all_ruleset_ids.add(ruleset_id)
        if ruleset_id == named_ruleset_id:
            named_rules.append(rule)

    by_type: dict[str, list[dict[str, Any]]] = {}
    for rule in named_rules:
        by_type.setdefault(str(rule.get("type", "")), []).append(rule)

    pull_requests = by_type.get("pull_request", [])
    pr_params = [_parameters(rule) for rule in pull_requests]
    observed_approvals = max(
        (
            int(params.get("required_approving_review_count") or 0)
            for params in pr_params
        ),
        default=0,
    )
    observed_dismiss_stale = any(
        bool(params.get("dismiss_stale_reviews_on_push"))
        for params in pr_params
    )
    observed_last_push = any(
        bool(params.get("require_last_push_approval"))
        for params in pr_params
    )
    observed_code_owner = any(
        bool(params.get("require_code_owner_review"))
        for params in pr_params
    )
    observed_resolution = any(
        bool(params.get("required_review_thread_resolution"))
        for params in pr_params
    )
    observed_extra_approval = any(
        bool(params.get("require_extra_approval_for_unattributed_changes"))
        for params in pr_params
    )

    review_policy_matches = bool(pull_requests) and all(
        (
            observed_approvals == policy.required_approving_review_count,
            observed_dismiss_stale == policy.dismiss_stale_reviews_on_push,
            observed_last_push == policy.require_last_push_approval,
            observed_code_owner == policy.require_code_owner_review,
        )
    )
    conversation_resolution_required = (
        observed_resolution
        if policy.require_conversation_resolution
        else not observed_resolution
    )
    extra_approval_matches = (
        observed_extra_approval
        == policy.require_extra_approval_for_unattributed_changes
    )

    status_rules = by_type.get("required_status_checks", [])
    observed_bindings: set[tuple[str, int | None]] = set()
    strict_observed = False
    for rule in status_rules:
        params = _parameters(rule)
        strict_observed = strict_observed or bool(
            params.get("strict_required_status_checks_policy")
        )
        checks = params.get("required_status_checks")
        if not isinstance(checks, list):
            continue
        for check in checks:
            if (
                not isinstance(check, dict)
                or not isinstance(check.get("context"), str)
            ):
                continue
            integration_id = check.get("integration_id")
            observed_bindings.add(
                (
                    check["context"],
                    integration_id if isinstance(integration_id, int) else None,
                )
            )

    required_bindings = {
        (context, policy.required_status_check_integration_id)
        for context in policy.required_status_check_contexts
    }
    missing = tuple(sorted(required_bindings - observed_bindings))
    unexpected = tuple(sorted(observed_bindings - required_bindings))
    exact_bindings = bool(status_rules) and not missing and not unexpected
    branches_up_to_date = (
        strict_observed if policy.require_branches_up_to_date else True
    )

    return Result(
        protected=protected,
        named_ruleset_active=True,
        pull_request_required=bool(pull_requests),
        review_policy_matches=review_policy_matches,
        conversation_resolution_required=conversation_resolution_required,
        extra_approval_for_unattributed_changes_matches=extra_approval_matches,
        status_checks_required=bool(status_rules),
        required_status_check_bindings_exact=exact_bindings,
        branches_up_to_date_required=branches_up_to_date,
        force_push_blocked=bool(by_type.get("non_fast_forward")),
        deletion_blocked=bool(by_type.get("deletion")),
        signatures_required=bool(by_type.get("required_signatures")),
        source="effective_repository_rulesets:no_splicing:exact_contract",
        evaluated_ruleset_id=named_ruleset_id,
        observed_require_extra_approval_for_unattributed_changes=
            observed_extra_approval,
        observed_required_status_check_bindings=tuple(
            sorted(observed_bindings)
        ),
        missing_required_status_check_bindings=missing,
        unexpected_required_status_check_bindings=unexpected,
        all_effective_ruleset_ids=tuple(sorted(all_ruleset_ids)),
    )


def verify(repo: str, branch: str, token: str | None, policy: Policy) -> Result:
    status, branch_data = _get(
        f"/repos/{repo}/branches/{urllib.parse.quote(branch, safe='')}", token
    )
    if status != 200 or not isinstance(branch_data, dict):
        raise EnforcementError(
            f"branch lookup failed: HTTP {status}: {branch_data}"
        )

    protected = bool(branch_data.get("protected"))
    if not protected:
        return _deny("branch_endpoint:protected=false", policy)

    return _effective_rules(repo, branch, token, protected, policy)


def _write_result(path: str | None, payload: dict[str, Any]) -> None:
    if path:
        Path(path).write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        default=os.environ.get(
            "GITHUB_REPOSITORY", "Aegis-Omega/AEGIS-OMEGA"
        ),
    )
    parser.add_argument("--branch", default="main")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--json-output")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    try:
        policy = Policy.load(args.policy)
        result = verify(args.repo, args.branch, token, policy)
    except (
        EnforcementError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        payload = {
            "repository": args.repo,
            "branch": args.branch,
            "production_admission": "FORBIDDEN",
            "verification_status": "UNKNOWN",
            "error": str(exc),
        }
        _write_result(args.json_output, payload)
        print(json.dumps(payload, sort_keys=True, indent=2))
        print(
            f"REPOSITORY_ENFORCEMENT=UNKNOWN error={exc}",
            file=sys.stderr,
        )
        return 2

    payload = {
        "repository": args.repo,
        "branch": args.branch,
        "verification_status": "VERIFIED",
        **result.as_dict(),
    }
    print(json.dumps(payload, sort_keys=True, indent=2))
    _write_result(args.json_output, payload)

    if not result.ok:
        print("REPOSITORY_ENFORCEMENT=FAIL_CLOSED", file=sys.stderr)
        return 1
    print("REPOSITORY_ENFORCEMENT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())