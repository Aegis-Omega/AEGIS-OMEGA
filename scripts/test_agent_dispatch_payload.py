#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "agent_dispatch_payload.py"


def load_module():
    spec = importlib.util.spec_from_file_location("agent_dispatch_payload", MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load agent_dispatch_payload")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class AgentDispatchPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_module()

    def test_default_branch_ci_from_same_repo_is_admitted(self) -> None:
        event = {
            "repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA", "default_branch": "main"},
            "workflow_run": {
                "conclusion": "success",
                "event": "push",
                "head_branch": "main",
                "head_sha": "a" * 40,
                "id": 123,
                "html_url": "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/123",
                "head_repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA"},
            },
        }
        request, reason = self.mod.classify_event("workflow_run", event)
        self.assertIsNotNone(request)
        self.assertEqual(reason, "ADMITTED_CI_EVENT")

    def test_fork_or_non_default_ci_is_deferred(self) -> None:
        base = {
            "repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA", "default_branch": "main"},
            "workflow_run": {
                "conclusion": "success", "event": "push", "head_branch": "main",
                "head_repository": {"full_name": "fork/AEGIS-OMEGA"},
            },
        }
        request, reason = self.mod.classify_event("workflow_run", base)
        self.assertIsNone(request)
        self.assertEqual(reason, "CI_UNTRUSTED_REPOSITORY")
        base["workflow_run"]["head_repository"]["full_name"] = "Aegis-Omega/AEGIS-OMEGA"
        base["workflow_run"]["head_branch"] = "feature"
        request, reason = self.mod.classify_event("workflow_run", base)
        self.assertIsNone(request)
        self.assertEqual(reason, "CI_NOT_DEFAULT_BRANCH_PUSH")

    def test_pr_requires_trusted_author_and_explicit_label(self) -> None:
        event = {
            "action": "synchronize",
            "number": 7,
            "pull_request": {
                "author_association": "MEMBER",
                "labels": [{"name": "aegis-agent"}],
                "title": "x",
                "html_url": "https://example.invalid/pr/7",
                "head": {"sha": "b" * 40},
            },
        }
        request, reason = self.mod.classify_event("pull_request_target", event)
        self.assertIsNotNone(request)
        self.assertEqual(reason, "ADMITTED_PR_EVENT")
        event["pull_request"]["labels"] = []
        request, reason = self.mod.classify_event("pull_request_target", event)
        self.assertIsNone(request)
        self.assertEqual(reason, "PR_EXPLICIT_DISPATCH_LABEL_MISSING")

    def test_comment_requires_trusted_author_and_explicit_mention(self) -> None:
        event = {
            "comment": {"body": "@aegis-agent inspect", "author_association": "COLLABORATOR"},
            "issue": {"number": 9, "html_url": "https://example.invalid/issues/9"},
        }
        request, reason = self.mod.classify_event("issue_comment", event)
        self.assertIsNotNone(request)
        self.assertEqual(reason, "ADMITTED_COMMENT_EVENT")
        event["comment"]["author_association"] = "NONE"
        request, reason = self.mod.classify_event("issue_comment", event)
        self.assertIsNone(request)
        self.assertEqual(reason, "COMMENT_UNTRUSTED_AUTHOR")

    def test_request_and_oidc_audience_are_bounded_and_deterministic(self) -> None:
        request = self.mod._request("x", {"body": "a" * 100})
        self.assertLessEqual(len(__import__("json").dumps(request, sort_keys=True, separators=(",", ":")).encode()), 8192)
        self.assertEqual(self.mod.oidc_audience(request), self.mod.oidc_audience(request))
        self.assertTrue(self.mod.oidc_audience(request).startswith("aegis-agent-dispatch:"))


if __name__ == "__main__":
    unittest.main()
