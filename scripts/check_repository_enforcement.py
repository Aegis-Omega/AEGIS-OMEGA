#!/usr/bin/env python3
"""Fail-closed verifier for GitHub default-branch enforcement.

This checker deliberately separates repository evidence from repository authority:
a green CI run is not production admission unless GitHub itself enforces the branch.
It accepts either classic branch protection or repository rulesets, but requires the
same core invariants in either mechanism.
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
from typing import Any

API = "https://api.github.com"


class EnforcementError(RuntimeError):
    pass


@dataclass(frozen=True)
class Result:
    protected: bool
    pull_request_required: bool
    approving_review_required: bool
    status_checks_required: bool
    force_push_blocked: bool
    deletion_blocked: bool
    signatures_required: bool
    conversation_resolution_required: bool
    source: str

    @property
    def ok(self) -> bool:
        return all(
            (
                self.protected,
                self.pull_request_required,
                self.approving_review_required,
                self.status_checks_required,
                self.force_push_blocked,
                self.deletion_blocked,
                self.signatures_required,
                self.conversation_resolution_required,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "protected": self.protected,
            "pull_request_required": self.pull_request_required,
            "approving_review_required": self.approving_review_required,
            "status_checks_required": self.status_checks_required,
            "force_push_blocked": self.force_push_blocked,
            "deletion_blocked": self.deletion_blocked,
            "signatures_required": self.signatures_required,
            "conversation_resolution_required": self.conversation_resolution_required,
            "source": self.source,
            "production_admission": "ELIGIBLE" if self.ok else "FORBIDDEN",
        }


def _get(path: str, token: str | None) -> tuple[int, Any]:
    req = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "aegis-repository-enforcement/1",
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


def _classic(repo: str, branch: str, token: str | None, protected: bool) -> Result | None:
    status, protection = _get(
        f"/repos/{repo}/branches/{urllib.parse.quote(branch, safe='')}/protection", token
    )
    if status == 404:
        return None
    if status != 200 or not isinstance(protection, dict):
        raise EnforcementError(f"classic protection lookup failed: HTTP {status}: {protection}")

    reviews = protection.get("required_pull_request_reviews") or {}
    checks = protection.get("required_status_checks") or {}
    enforce_admins = protection.get("enforce_admins") or {}
    signatures = protection.get("required_signatures") or {}
    conversations = protection.get("required_conversation_resolution") or {}
    allow_force = protection.get("allow_force_pushes") or {}
    allow_delete = protection.get("allow_deletions") or {}

    # Admin enforcement is not exposed as a separate Result field, but a classic
    # policy that permits admin bypass is not accepted as a protected authority boundary.
    classic_protected = protected and bool(enforce_admins.get("enabled"))

    contexts = checks.get("contexts") or []
    check_objects = checks.get("checks") or []
    return Result(
        protected=classic_protected,
        pull_request_required=bool(reviews),
        approving_review_required=int(reviews.get("required_approving_review_count") or 0) >= 1,
        status_checks_required=bool(checks) and bool(contexts or check_objects),
        force_push_blocked=not bool(allow_force.get("enabled", False)),
        deletion_blocked=not bool(allow_delete.get("enabled", False)),
        signatures_required=bool(signatures.get("enabled")),
        conversation_resolution_required=bool(conversations.get("enabled")),
        source="classic_branch_protection",
    )


def _rulesets(repo: str, branch: str, token: str | None, protected: bool) -> Result | None:
    status, rules = _get(
        f"/repos/{repo}/rules/branches/{urllib.parse.quote(branch, safe='')}", token
    )
    if status == 404:
        return None
    if status != 200 or not isinstance(rules, list):
        raise EnforcementError(f"branch rules lookup failed: HTTP {status}: {rules}")

    by_type: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        if isinstance(rule, dict):
            by_type.setdefault(str(rule.get("type", "")), []).append(rule)

    prs = by_type.get("pull_request", [])
    checks = by_type.get("required_status_checks", [])

    def params(rule: dict[str, Any]) -> dict[str, Any]:
        value = rule.get("parameters")
        return value if isinstance(value, dict) else {}

    approving_review_required = any(
        int(params(rule).get("required_approving_review_count") or 0) >= 1 for rule in prs
    )
    conversation_resolution_required = any(
        bool(params(rule).get("required_review_thread_resolution")) for rule in prs
    )
    status_checks_required = any(
        bool(params(rule).get("required_status_checks")) for rule in checks
    )

    return Result(
        protected=protected,
        pull_request_required=bool(prs),
        approving_review_required=approving_review_required,
        status_checks_required=status_checks_required,
        force_push_blocked=bool(by_type.get("non_fast_forward")),
        deletion_blocked=bool(by_type.get("deletion")),
        signatures_required=bool(by_type.get("required_signatures")),
        conversation_resolution_required=conversation_resolution_required,
        source="repository_rulesets",
    )


def verify(repo: str, branch: str, token: str | None) -> Result:
    status, branch_data = _get(
        f"/repos/{repo}/branches/{urllib.parse.quote(branch, safe='')}", token
    )
    if status != 200 or not isinstance(branch_data, dict):
        raise EnforcementError(f"branch lookup failed: HTTP {status}: {branch_data}")
    protected = bool(branch_data.get("protected"))

    candidates = [
        result
        for result in (
            _classic(repo, branch, token, protected),
            _rulesets(repo, branch, token, protected),
        )
        if result is not None
    ]
    if not candidates:
        return Result(False, False, False, False, False, False, False, False, "none")

    # Multiple mechanisms may coexist. Accept only if one mechanism independently
    # establishes the full authority boundary; do not splice partial guarantees.
    for result in candidates:
        if result.ok:
            return result
    return max(candidates, key=lambda item: sum(bool(v) for k, v in item.as_dict().items() if k not in {"source", "production_admission"}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Aegis-Omega/AEGIS-OMEGA"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--json-output")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    try:
        result = verify(args.repo, args.branch, token)
    except EnforcementError as exc:
        print(f"REPOSITORY_ENFORCEMENT=UNKNOWN error={exc}", file=sys.stderr)
        return 2

    payload = result.as_dict()
    rendered = json.dumps(payload, sort_keys=True, indent=2)
    print(rendered)
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")

    if not result.ok:
        print("REPOSITORY_ENFORCEMENT=FAIL_CLOSED", file=sys.stderr)
        return 1
    print("REPOSITORY_ENFORCEMENT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
