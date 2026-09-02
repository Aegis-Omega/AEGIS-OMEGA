#!/usr/bin/env python3
"""Build a bounded, evidence-only AEGIS dispatch request from a GitHub event."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MAX_REQUEST_BYTES = 8_192
MAX_TITLE_CHARS = 256
MAX_BODY_CHARS = 2_000
MAX_URL_CHARS = 2_048
OIDC_AUDIENCE_PREFIX = "aegis-agent-dispatch:"
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
DISPATCH_LABEL = "aegis-agent"


def _text(value: Any, limit: int) -> str:
    return "" if value is None else str(value)[:limit]


def _request(event_type: str, payload: dict[str, str]) -> dict[str, Any]:
    request = {"event_type": event_type, "payload": payload}
    encoded = json.dumps(request, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("bounded dispatch request exceeds size ceiling")
    return request


def oidc_audience(request: dict[str, Any]) -> str:
    payload = json.dumps(
        {"domain": "AEGIS_AGENT_DISPATCH_REQUEST_V1", "value": request},
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return OIDC_AUDIENCE_PREFIX + hashlib.sha256(payload).hexdigest()


def classify_event(event_name: str, event: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    repo = event.get("repository") or {}

    if event_name == "workflow_run":
        run = event.get("workflow_run") or {}
        conclusion = _text(run.get("conclusion"), 32)
        head_repo = run.get("head_repository") or {}
        if conclusion not in {"success", "failure"}:
            return None, "CI_CONCLUSION_NOT_ACTIONABLE"
        if _text(run.get("event"), 32) != "push":
            return None, "CI_NOT_DEFAULT_BRANCH_PUSH"
        if _text(run.get("head_branch"), 256) != _text(repo.get("default_branch"), 256):
            return None, "CI_NOT_DEFAULT_BRANCH_PUSH"
        if _text(head_repo.get("full_name"), 256) != _text(repo.get("full_name"), 256):
            return None, "CI_UNTRUSTED_REPOSITORY"
        return _request(
            f"github_ci_{conclusion}",
            {
                "branch": _text(run.get("head_branch"), 256),
                "conclusion": conclusion,
                "head_sha": _text(run.get("head_sha"), 64),
                "run_id": _text(run.get("id"), 32),
                "url": _text(run.get("html_url"), MAX_URL_CHARS),
            },
        ), "ADMITTED_CI_EVENT"

    if event_name == "pull_request_target":
        action = _text(event.get("action"), 64)
        pull = event.get("pull_request") or {}
        association = _text(pull.get("author_association"), 32)
        labels = {str((item or {}).get("name", "")).lower() for item in pull.get("labels", [])}
        if association not in TRUSTED_ASSOCIATIONS:
            return None, "PR_UNTRUSTED_AUTHOR"
        if DISPATCH_LABEL not in labels:
            return None, "PR_EXPLICIT_DISPATCH_LABEL_MISSING"
        if action not in {"opened", "synchronize", "review_requested", "labeled"}:
            return None, "PR_ACTION_NOT_ACTIONABLE"
        head = pull.get("head") or {}
        return _request(
            f"github_pr_{action}",
            {
                "head_sha": _text(head.get("sha"), 64),
                "number": _text(event.get("number"), 32),
                "title": _text(pull.get("title"), MAX_TITLE_CHARS),
                "url": _text(pull.get("html_url"), MAX_URL_CHARS),
            },
        ), "ADMITTED_PR_EVENT"

    if event_name == "issues":
        action = _text(event.get("action"), 64)
        label = event.get("label") or {}
        if action != "labeled" or _text(label.get("name"), 128).lower() != DISPATCH_LABEL:
            return None, "ISSUE_EXPLICIT_DISPATCH_LABEL_MISSING"
        issue = event.get("issue") or {}
        return _request(
            "github_issue_labeled",
            {
                "body": _text(issue.get("body"), MAX_BODY_CHARS),
                "number": _text(issue.get("number"), 32),
                "title": _text(issue.get("title"), MAX_TITLE_CHARS),
                "url": _text(issue.get("html_url"), MAX_URL_CHARS),
            },
        ), "ADMITTED_ISSUE_EVENT"

    if event_name == "issue_comment":
        comment = event.get("comment") or {}
        body = _text(comment.get("body"), MAX_BODY_CHARS)
        association = _text(comment.get("author_association"), 32)
        if association not in TRUSTED_ASSOCIATIONS:
            return None, "COMMENT_UNTRUSTED_AUTHOR"
        if "@aegis-agent" not in body.lower():
            return None, "COMMENT_EXPLICIT_MENTION_MISSING"
        issue = event.get("issue") or {}
        return _request(
            "github_issue_comment_mention",
            {
                "body": body,
                "number": _text(issue.get("number"), 32),
                "url": _text(issue.get("html_url"), MAX_URL_CHARS),
            },
        ), "ADMITTED_COMMENT_EVENT"

    return None, "EVENT_NOT_DISPATCHABLE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audience-output", type=Path, required=True)
    parser.add_argument("--decision-output", type=Path, required=True)
    args = parser.parse_args()

    raw = json.loads(args.event_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GitHub event root must be an object")
    request, reason = classify_event(args.event_name, raw)
    decision = {"schema": "aegis.agent-dispatch-classification.v1", "actionable": request is not None, "reason": reason}
    args.decision_output.write_text(json.dumps(decision, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    if request is None:
        return 2
    args.output.write_text(json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    args.audience_output.write_text(oidc_audience(request) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
