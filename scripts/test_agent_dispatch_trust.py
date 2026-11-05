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
import tempfile
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
        freshness_end = "          # AEGIS_HEAD_FRESHNESS_END"
        if source.count("          # AEGIS_HEAD_FRESHNESS_BEGIN") != 1 or source.count(freshness_end) != 1:
            raise AssertionError("Source-bound exact-head gate missing or duplicated")
        cls.shell = textwrap.dedent(source.split(begin, 1)[1].split(freshness_end, 1)[0])
        cls._mock_dir = tempfile.TemporaryDirectory()
        cls.mockbin = Path(cls._mock_dir.name)
        gh = cls.mockbin / "gh"
        gh.write_text("#!/bin/sh\nset -eu\ncase \"$2\" in\n  */pulls/*) printf '%s\\n' \"$LIVE_PR_HEAD\" ;;\n  */branches/main) printf '%s\\n' \"$LIVE_MAIN_HEAD\" ;;\n  *) exit 2 ;;\nesac\n")
        gh.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls._mock_dir.cleanup()

    def decision(self, event, *, issue="", comment="", pr="", actor="", author="",
                 branch="main", source_repo="Aegis-Omega/AEGIS-OMEGA",
                 pr_head="a" * 40, wf_head="b" * 40,
                 live_pr=None, live_main=None, pr_number="775"):
        env = {**os.environ,
               "EVENT_NAME": event, "ISSUE_ASSOCIATION": issue,
               "COMMENT_ASSOCIATION": comment, "PR_ASSOCIATION": pr,
               "PR_AUTHOR": author, "ACTOR": actor,
               "WF_BRANCH": branch, "WF_HEAD_REPO": source_repo,
               "EXPECTED_REPOSITORY": "Aegis-Omega/AEGIS-OMEGA",
               "PR_NUMBER": pr_number, "PR_HEAD_SHA": pr_head, "WF_HEAD_SHA": wf_head,
               "LIVE_PR_HEAD": pr_head if live_pr is None else live_pr,
               "LIVE_MAIN_HEAD": wf_head if live_main is None else live_main,
               "PATH": f"{self.mockbin}:{os.environ.get('PATH', '')}"}
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


    def test_api_only_exact_head_contract(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("uses: actions/checkout@", source)
        self.assertIn("GH_TOKEN:", source)
        self.assertIn("gh api", source)
        self.assertIn('"source_head_sha":', source)

    def test_stale_or_malformed_pull_request_denied_before_credentials(self):
        accepted = dict(pr="MEMBER", actor="member", author="member")
        self.assertFalse(self.decision("pull_request", **accepted, live_pr="c" * 40))
        self.assertFalse(self.decision("pull_request", **accepted, pr_head="not-a-sha"))
        self.assertFalse(self.decision("pull_request", **accepted, pr_number="../bad"))

    def test_stale_or_malformed_main_workflow_denied_before_credentials(self):
        self.assertFalse(self.decision("workflow_run", live_main="c" * 40))
        self.assertFalse(self.decision("workflow_run", wf_head="not-a-sha"))

if __name__ == "__main__":
    unittest.main()
