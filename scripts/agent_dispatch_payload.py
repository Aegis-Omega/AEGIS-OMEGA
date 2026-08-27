#!/usr/bin/env python3
"""Build a bounded, evidence-only dispatch request from a GitHub event.

The GitHub event file is untrusted input. This module selects a small metadata
subset, preserves the triggering action, and returns ``None`` for events that
do not have an admitted route. It never decides that an agent result is true.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MAX_REQUEST_BYTES = 8_192
MAX_TITLE_CHARS = 256
MAX_BODY_CHARS = 2_000
MAX_URL_CHARS = 2_048


def _text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    return str(value)[:limit]


def _request(event_type: str, payload: dict[str, str]) -> dict[str, Any]:
    request = {"event_type": event_type, "payload": payload}
    encoded = json.dumps(request, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("bounded dispatch request exceeds size ceiling")
    return request


def classify_event(event_name: str, event: dict[str, Any]) -> dict[str, Any] | None:
    """Return a bounded request for an admitted GitHub event, else ``None``."""

    if event_name == "workflow_run":
        run = event.get("workflow_run") or {}
        conclusion = _text(run.get("conclusion"), 32)
        if conclusion not in {"success", "failure"}:
            return None
        return _request(
            f"github_ci_{conclusion}",
            {
                "branch": _text(run.get("head_branch"), 256),
                "conclusion": conclusion,
                "head_sha": _text(run.get("head_sha"), 64),
                "run_id": _text(run.get("id"), 32),
                "url": _text(run.get("html_url"), MAX_URL_CHARS),
            },
        )

    if event_name == "pull_request":
        action = _text(event.get("action"), 64)
        if action not in {"opened", "synchronize", "review_requested"}:
            return None
        pull = event.get("pull_request") or {}
        head = pull.get("head") or {}
        return _request(
            f"github_pr_{action}",
            {
                "head_sha": _text(head.get("sha"), 64),
                "number": _text(event.get("number"), 32),
                "title": _text(pull.get("title"), MAX_TITLE_CHARS),
                "url": _text(pull.get("html_url"), MAX_URL_CHARS),
            },
        )

    if event_name == "issues":
        action = _text(event.get("action"), 64)
        label = event.get("label") or {}
        label_name = _text(label.get("name"), 128)
        if action != "labeled" or label_name.lower() != "aegis-agent":
            return None
        issue = event.get("issue") or {}
        return _request(
            f"github_issue_{action}",
            {
                "body": _text(issue.get("body"), MAX_BODY_CHARS),
                "label": label_name,
                "number": _text(issue.get("number"), 32),
                "title": _text(issue.get("title"), MAX_TITLE_CHARS),
                "url": _text(issue.get("html_url"), MAX_URL_CHARS),
            },
        )

    if event_name == "issue_comment":
        comment = event.get("comment") or {}
        body = _text(comment.get("body"), MAX_BODY_CHARS)
        if "@aegis-agent" not in body.lower():
            return None
        issue = event.get("issue") or {}
        return _request(
            "github_issue_comment_mention",
            {
                "body": body,
                "number": _text(issue.get("number"), 32),
                "url": _text(issue.get("html_url"), MAX_URL_CHARS),
            },
        )

    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = json.loads(args.event_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GitHub event root must be an object")
    request = classify_event(args.event_name, raw)
    if request is None:
        return 2
    args.output.write_text(
        json.dumps(request, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
