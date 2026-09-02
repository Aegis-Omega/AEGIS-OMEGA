#!/usr/bin/env python3
"""Fail-closed verifier for the AEGIS default-branch repository ruleset.

The verifier intentionally uses GitHub's effective-rules surface, not privileged
branch-protection administration endpoints. For a public repository the effective
branch rules are observable with Metadata:read (and without authentication), which
lets CI prove the active enforcement semantics without acquiring mutation authority.
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
DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "security" / "repository-enforcement-policy.json"


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
    require_branches_up_to_date: bool
    required_status_check_contexts: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        policy = raw.get("policy")
        if not isinstance(policy, dict):
            raise EnforcementError("repository enforcement policy has no policy object")
        contexts = policy.get("required_status_check_contexts")
        if not isinstance(contexts, list) or not contexts or not all(isinstance(item, str) and item for item in contexts):
            raise EnforcementError("required_status_check_contexts must be a non-empty string list")
        return cls(
            ruleset_name=str(raw.get("ruleset_name") or "AEGIS Main Enforcement"),
            required_approving_review_count=int(policy.get("required_approving_review_count", 0)),
            dismiss_stale_reviews_on_push=bool(policy.get("dismiss_stale_reviews_on_push", False)),
            require_last_push_approval=bool(policy.get("require_last_push_approval", False)),
            require_code_owner_review=bool(policy.get("require_code_owner_review", False)),
            require_conversation_resolution=bool(policy.get("require_conversation_resolution", True)),
            require_branches_up_to_date=bool(policy.get("require_branches_up_to_date", True)),
            required_status_check_contexts=tuple(contexts),
        )


@dataclass(frozen=True)
class Result:
    protected: bool
    named_ruleset_active: bool
    pull_request_required: bool
    review_policy_matches: bool
    conversation_resolution_required: bool
    status_checks_required: bool
    required_status_check_contexts_complete: bool
    branches_up_to_date_required: bool
    force_push_blocked: bool
    deletion_blocked: bool
    signatures_required: bool
    source: str
    observed_required_approving_review_count: int = 0
    observed_dismiss_stale_reviews_on_push: bool = False
    observed_require_last_push_approval: bool = False
    observed_require_code_owner_review: bool = False
    observed_required_status_check_contexts: tuple[str, ...] = ()
    missing_required_status_check_contexts: tuple[str, ...] = ()
    effective_ruleset_ids: tuple[int, ...] = ()

    @property
    def ok(self) -> bool:
        return all(
            (
                self.protected,
                self.named_ruleset_active,
                self.pull_request_required,
                self.review_policy_matches,
                self.conversation_resolution_required,
                self.status_checks_required,
                self.required_status_check_contexts_complete,
                self.branches_up_to_date_required,
                self.force_push_blocked,
                self.deletion_blocked,
                self.signatures_required,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "protected": self.protected,
            "named_ruleset_active": self.named_ruleset_active,
            "pull_request_required": self.pull_request_required,
            "review_policy_matches": self.review_policy_matches,
            "conversation_resolution_required": self.conversation_resolution_required,
            "status_checks_required": self.status_checks_required,
            "required_status_check_contexts_complete": self.required_status_check_contexts_complete,
            "branches_up_to_date_required": self.branches_up_to_date_required,
            "force_push_blocked": self.force_push_blocked,
            "deletion_blocked": self.deletion_blocked,
            "signatures_required": self.signatures_required,
            "observed_required_approving_review_count": self.observed_required_approving_review_count,
            "observed_dismiss_stale_reviews_on_push": self.observed_dismiss_stale_reviews_on_push,
            "observed_require_last_push_approval": self.observed_require_last_push_approval,
            "observed_require_code_owner_review": self.observed_require_code_owner_review,
            "observed_required_status_check_contexts": list(self.observed_required_status_check_contexts),
            "missing_required_status_check_contexts": list(self.missing_required_status_check_contexts),
            "effective_ruleset_ids": list(self.effective_ruleset_ids),
            "source": self.source,
            "production_admission": "ELIGIBLE" if self.ok else "FORBIDDEN",
        }


def _get(path: str, token: str | None) -> tuple[int, Any]:
    req = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "aegis-repository-enforcement/2",
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


def _deny(source: str, policy: Policy) -> Result:
    return Result(
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        source,
        missing_required_status_check_contexts=policy.required_status_check_contexts,
    )


def _parameters(rule: dict[str, Any]) -> dict[str, Any]:
    value = rule.get("parameters")
    return value if isinstance(value, dict) else {}


def _named_ruleset_active(repo: str, token: str | None, policy: Policy) -> bool:
    status, rulesets = _get(f"/repos/{repo}/rulesets?per_page=100&targets=branch", token)
    if status != 200 or not isinstance(rulesets, list):
        raise EnforcementError(f"ruleset inventory lookup failed: HTTP {status}: {rulesets}")
    return any(
        isinstance(item, dict)
        and item.get("name") == policy.ruleset_name
        and item.get("enforcement") == "active"
        and item.get("source_type") == "Repository"
        and item.get("source") == repo
        for item in rulesets
    )


def _effective_rules(repo: str, branch: str, token: str | None, protected: bool, policy: Policy) -> Result:
    status, rules = _get(
        f"/repos/{repo}/rules/branches/{urllib.parse.quote(branch, safe='')}?per_page=100", token
    )
    if status != 200 or not isinstance(rules, list):
        raise EnforcementError(f"effective branch rules lookup failed: HTTP {status}: {rules}")

    by_type: dict[str, list[dict[str, Any]]] = {}
    ruleset_ids: set[int] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        by_type.setdefault(str(rule.get("type", "")), []).append(rule)
        ruleset_id = rule.get("ruleset_id")
        if isinstance(ruleset_id, int):
            ruleset_ids.add(ruleset_id)

    pull_requests = by_type.get("pull_request", [])
    pr_params = [_parameters(rule) for rule in pull_requests]
    observed_approvals = max(
        (int(params.get("required_approving_review_count") or 0) for params in pr_params),
        default=0,
    )
    observed_dismiss_stale = any(bool(params.get("dismiss_stale_reviews_on_push")) for params in pr_params)
    observed_last_push = any(bool(params.get("require_last_push_approval")) for params in pr_params)
    observed_code_owner = any(bool(params.get("require_code_owner_review")) for params in pr_params)
    observed_resolution = any(bool(params.get("required_review_thread_resolution")) for params in pr_params)

    review_policy_matches = bool(pull_requests) and all(
        (
            observed_approvals == policy.required_approving_review_count,
            observed_dismiss_stale == policy.dismiss_stale_reviews_on_push,
            observed_last_push == policy.require_last_push_approval,
            observed_code_owner == policy.require_code_owner_review,
        )
    )
    conversation_resolution_required = (
        observed_resolution if policy.require_conversation_resolution else not observed_resolution
    )

    status_rules = by_type.get("required_status_checks", [])
    observed_contexts: set[str] = set()
    strict_observed = False
    for rule in status_rules:
        params = _parameters(rule)
        strict_observed = strict_observed or bool(params.get("strict_required_status_checks_policy"))
        checks = params.get("required_status_checks")
        if not isinstance(checks, list):
            continue
        for check in checks:
            if isinstance(check, dict) and isinstance(check.get("context"), str):
                observed_contexts.add(check["context"])

    required_contexts = set(policy.required_status_check_contexts)
    missing = tuple(sorted(required_contexts - observed_contexts))
    contexts_complete = bool(status_rules) and not missing
    branches_up_to_date = strict_observed if policy.require_branches_up_to_date else True

    return Result(
        protected=protected,
        named_ruleset_active=_named_ruleset_active(repo, token, policy),
        pull_request_required=bool(pull_requests),
        review_policy_matches=review_policy_matches,
        conversation_resolution_required=conversation_resolution_required,
        status_checks_required=bool(status_rules),
        required_status_check_contexts_complete=contexts_complete,
        branches_up_to_date_required=branches_up_to_date,
        force_push_blocked=bool(by_type.get("non_fast_forward")),
        deletion_blocked=bool(by_type.get("deletion")),
        signatures_required=bool(by_type.get("required_signatures")),
        source="effective_repository_rulesets",
        observed_required_approving_review_count=observed_approvals,
        observed_dismiss_stale_reviews_on_push=observed_dismiss_stale,
        observed_require_last_push_approval=observed_last_push,
        observed_require_code_owner_review=observed_code_owner,
        observed_required_status_check_contexts=tuple(sorted(observed_contexts)),
        missing_required_status_check_contexts=missing,
        effective_ruleset_ids=tuple(sorted(ruleset_ids)),
    )


def verify(repo: str, branch: str, token: str | None, policy: Policy) -> Result:
    status, branch_data = _get(
        f"/repos/{repo}/branches/{urllib.parse.quote(branch, safe='')}", token
    )
    if status != 200 or not isinstance(branch_data, dict):
        raise EnforcementError(f"branch lookup failed: HTTP {status}: {branch_data}")

    protected = bool(branch_data.get("protected"))
    if not protected:
        return _deny("branch_endpoint:protected=false", policy)

    return _effective_rules(repo, branch, token, protected, policy)


def _write_result(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Aegis-Omega/AEGIS-OMEGA"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--json-output")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    try:
        policy = Policy.load(args.policy)
        result = verify(args.repo, args.branch, token, policy)
    except (EnforcementError, OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "repository": args.repo,
            "branch": args.branch,
            "production_admission": "FORBIDDEN",
            "verification_status": "UNKNOWN",
            "error": str(exc),
        }
        _write_result(args.json_output, payload)
        print(json.dumps(payload, sort_keys=True, indent=2))
        print(f"REPOSITORY_ENFORCEMENT=UNKNOWN error={exc}", file=sys.stderr)
        return 2

    payload = {
        "repository": args.repo,
        "branch": args.branch,
        "verification_status": "VERIFIED",
        **result.as_dict(),
    }
    rendered = json.dumps(payload, sort_keys=True, indent=2)
    print(rendered)
    _write_result(args.json_output, payload)

    if not result.ok:
        print("REPOSITORY_ENFORCEMENT=FAIL_CLOSED", file=sys.stderr)
        return 1
    print("REPOSITORY_ENFORCEMENT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
