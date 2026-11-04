#!/usr/bin/env python3
"""Execute the actual GitHub dispatch trust gate without tokens or network.

This is an integration regression for existing agent-dispatch.yml, not a second
dispatch implementation. All external events are denied unless their exact
event-scoped author association is trusted; PR triggers additionally bind
sender identity to the trusted author.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/agent-dispatch.yml"


class DispatchTrustGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = WORKFLOW.read_text(encoding="utf-8")
        begin = "          # AEGIS_TRUST_GATE_BEGIN\n"
        end = "          # AEGIS_TRUST_GATE_END"
        if source.count(begin) != 1 or source.count(end) != 1:
            raise AssertionError("Source-bound trust gate markers missing or duplicated")
        cls.shell = textwrap.dedent(source.split(begin, 1)[1].split(end, 1)[0])

    def decision(self, event, *, issue="", comment="", pr="", actor="", author="",
                 branch="main", source_repo="Aegis-Omega/AEGIS-OMEGA"):
        env = {**os.environ,
               "EVENT_NAME": event, "ISSUE_ASSOCIATION": issue,
               "COMMENT_ASSOCIATION": comment, "PR_ASSOCIATION": pr,
               "PR_AUTHOR": author, "ACTOR": actor,
               "WF_BRANCH": branch, "WF_HEAD_REPO": source_repo,
               "EXPECTED_REPOSITORY": "Aegis-Omega/AEGIS-OMEGA"}
        result = subprocess.run(
            ["bash", "-c", "set -euo pipefail\n" + self.shell],
            env=env, capture_output=True, text=True, check=False, timeout=5,
        )
        return result.returncode == 0

    def test_event_bindings_are_specific_and_no_fake_context(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("github.actor_association }}", source)
        self.assertIn("github.event.issue.author_association", source)
        self.assertIn("github.event.comment.author_association", source)
        self.assertIn("github.event.pull_request.author_association", source)
        self.assertIn("github.event.pull_request.user.login", source)
        self.assertIn("github.event.workflow_run.head_repository.full_name", source)
        self.assertIn("if: vars.PROXY_URL != ''", source)

    def test_issue_author_association(self):
        for role in ("OWNER", "MEMBER", "COLLABORATOR"):
            with self.subTest(role=role):
                self.assertTrue(self.decision("issues", issue=role))
        for role in ("", "NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR"):
            with self.subTest(role=role):
                self.assertFalse(self.decision("issues", issue=role))

    def test_comment_author_association(self):
        for role in ("OWNER", "MEMBER", "COLLABORATOR"):
            with self.subTest(role=role):
                self.assertTrue(self.decision("issue_comment", comment=role))
        for role in ("", "NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR"):
            with self.subTest(role=role):
                self.assertFalse(self.decision("issue_comment", comment=role))

    def test_pr_author_must_be_trusted_and_match_actor(self):
        for role in ("OWNER", "MEMBER", "COLLABORATOR"):
            with self.subTest(role=role):
                self.assertTrue(self.decision("pull_request", pr=role, actor="member", author="member"))
        self.assertFalse(self.decision("pull_request", pr="NONE", actor="member", author="member"))
        self.assertFalse(self.decision("pull_request", pr="MEMBER", actor="reviewer", author="member"))
        self.assertFalse(self.decision("pull_request", pr="MEMBER", actor="", author="member"))
        self.assertFalse(self.decision("pull_request", pr="MEMBER", actor="member", author=""))

    def test_workflow_run_bound_to_internal_main(self):
        self.assertTrue(self.decision("workflow_run"))
        self.assertFalse(self.decision("workflow_run", branch="feature/untrusted"))
        self.assertFalse(self.decision("workflow_run", source_repo="outsider/fork"))
        self.assertFalse(self.decision("workflow_run", source_repo=""))

    def test_unknown_event_denied(self):
        self.assertFalse(self.decision("repository_dispatch", issue="OWNER"))
        self.assertFalse(self.decision("workflow_dispatch", issue="OWNER"))


if __name__ == "__main__":
    unittest.main()
