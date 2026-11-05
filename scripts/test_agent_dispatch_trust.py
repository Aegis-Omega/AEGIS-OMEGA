#!/usr/bin/env python3
"""Execute the actual GitHub dispatch trust gate without tokens or network.

This is an integration regression for existing agent-dispatch.yml, not a second
dispatch implementation. All external events are denied unless their exact
event-scoped author association is trusted; PR triggers additionally bind
sender identity to the trusted author.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/agent-dispatch.yml"
sys.path.insert(0, str(ROOT))
from agents.platform_access import GATED_ROUTES, github_webhook_auth_state, live_pipeline_state, platform_access_state  # noqa: E402


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


    def test_offline_preflight_is_source_bound_and_non_authoritative(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        preflight = source.split("  offline-preflight:\n", 1)[1].split("  dispatch:\n", 1)[0]
        self.assertIn("if: vars.PROXY_URL == '' && github.event_name == 'pull_request'", preflight)
        self.assertIn("pull-requests: read", preflight)
        self.assertIn("contents: read", preflight)
        self.assertNotIn("id-token: write", preflight)
        self.assertNotIn("actions/checkout", preflight)
        self.assertNotIn("ANTHROPIC_API_KEY", preflight)
        self.assertNotIn("OPENAI_API_KEY", preflight)
        self.assertIn('agent_execution: "NOT_EXECUTED"', preflight)
        self.assertIn("provider_calls: 0", preflight)
        self.assertIn("live_head", preflight)
        self.assertIn('"$live_head" == "$PR_HEAD_SHA"', preflight)
        self.assertIn("HOLD_NO_ADMISSION", preflight)
        self.assertIn("UNTRUSTED_TRIGGER_ACTOR", preflight)
        self.assertIn("UNTRUSTED_PR_AUTHOR", preflight)
        self.assertIn("# AEGIS_OFFLINE_PREFLIGHT_BEGIN", preflight)
        self.assertIn("# AEGIS_OFFLINE_PREFLIGHT_END", preflight)


    def test_live_proxy_dispatch_header_matches_existing_platform_auth(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        platform = (ROOT / "vertex/serve.py").read_text(encoding="utf-8")
        self.assertIn('@app.post("/agents/dispatch")', platform)
        self.assertIn('request.headers.get("x-api-key", "")', platform)
        self.assertIn('-H "x-api-key: $PLATFORM_KEY"', source)
        self.assertNotIn('-H "Authorization: Bearer $PLATFORM_KEY"', source)
        self.assertIn("if: vars.PROXY_URL != ''", source)

    def test_native_platform_auth_denies_missing_and_invalid_keys(self):
        for route in GATED_ROUTES:
            with self.subTest(route=route):
                self.assertEqual(platform_access_state(route, configured_key="", supplied_key=""), "SERVER_UNCONFIGURED")
                self.assertEqual(platform_access_state(route, configured_key="secret", supplied_key=""), "UNAUTHORIZED")
                self.assertEqual(platform_access_state(route, configured_key="secret", supplied_key="wrong"), "UNAUTHORIZED")
                self.assertEqual(platform_access_state(route, configured_key="secret", supplied_key="secret"), "AUTHENTICATED")
        self.assertIn("/agents/batch", GATED_ROUTES)
        self.assertEqual(platform_access_state("/health", configured_key="", supplied_key=""), "NOT_GATED")
        self.assertEqual(platform_access_state("/agents/runaway", configured_key="", supplied_key=""), "NOT_GATED")

    def test_platform_middleware_delegates_to_native_fail_closed_contract(self):
        source = (ROOT / "vertex/serve.py").read_text(encoding="utf-8")
        self.assertIn("from agents.platform_access import live_pipeline_state, platform_access_state", source)
        self.assertIn("access = platform_access_state(", source)
        self.assertIn('request.headers.get("x-api-key", "")', source)
        self.assertIn('access == "SERVER_UNCONFIGURED"', source)
        self.assertIn('access == "UNAUTHORIZED"', source)
        self.assertNotIn("if PLATFORM_API_KEY and any(", source)

    def test_direct_http_agent_run_cannot_bypass_central_coordinator(self):
        source = (ROOT / "vertex/serve.py").read_text(encoding="utf-8")
        direct_run = source.split('@app.post("/agents/run")', 1)[1].split('@app.post("/agents/dispatch")', 1)[0]
        self.assertIn("from agents.coordinator import AgentRole, dispatch_event", direct_run)
        self.assertNotIn("run_agent(", direct_run)
        self.assertIn("requested_roles=[agent_role]", direct_run)
        self.assertIn("instruction_override=task_instruction", direct_run)
        self.assertIn("max_ralph_cycles=cycles", direct_run)
        self.assertIn("CENTRAL_AUTHORITY_DENIED", direct_run)
        self.assertIn('"execution_state": "NOT_EXECUTED"', direct_run)

    def test_extended_cost_routes_and_webhook_hmac_fail_closed(self):
        import hashlib
        import hmac
        for path in ("/platform/compare", "/platform/stream", "/platform/schedule/revenue"):
            self.assertEqual(platform_access_state(path, configured_key="", supplied_key=""), "SERVER_UNCONFIGURED")
            self.assertEqual(platform_access_state(path, configured_key="key", supplied_key="key"), "AUTHENTICATED")
        body = b'{"repository":{"full_name":"Aegis-Omega/AEGIS-OMEGA"}}'
        sig = "sha256=" + hmac.new(b"test-key", body, hashlib.sha256).hexdigest()
        self.assertEqual(github_webhook_auth_state(configured_secret="", supplied_signature=sig, body=body), "SERVER_UNCONFIGURED")
        self.assertEqual(github_webhook_auth_state(configured_secret="test-key", supplied_signature="bad", body=body), "UNAUTHORIZED")
        self.assertEqual(github_webhook_auth_state(configured_secret="test-key", supplied_signature=sig, body=body), "AUTHENTICATED")
        self.assertEqual(github_webhook_auth_state(configured_secret="test-key", supplied_signature=sig, body=body+b" "), "UNAUTHORIZED")

    def test_batch_and_webhook_require_central_and_signed_boundaries(self):
        source = (ROOT / "vertex/serve.py").read_text(encoding="utf-8")
        batch = source.split('@app.post("/agents/batch")', 1)[1].split('@app.post("/platform/compare")', 1)[0]
        self.assertIn("from agents.coordinator import AgentRole, dispatch_event", batch)
        self.assertNotIn("run_agent(", batch)
        self.assertIn("requested_roles=[agent_role]", batch)
        self.assertIn("CENTRAL_AUTHORITY_DENIED", batch)
        webhook = source.split('@app.post("/platform/webhooks/github")', 1)[1]
        self.assertIn("github_webhook_auth_state(", webhook)
        self.assertIn("webhook_auth_unavailable", webhook)
        self.assertIn("repository_not_allowed", webhook)

    def test_legacy_live_pipeline_paths_deny_only(self):
        self.assertEqual(live_pipeline_state(True), "HOLD_NO_ADMISSION")
        self.assertEqual(live_pipeline_state(False), "OFFLINE_ONLY")
        source = (ROOT / "vertex/serve.py").read_text(encoding="utf-8")
        endpoints = (
            ("/platform/collaborate", "/agents/batch"),
            ("/platform/compare", "/platform/stream"),
            ("/platform/stream", "/platform/schedule/revenue"),
            ("/platform/schedule/revenue", "/platform/analytics"),
        )
        for start, end in endpoints:
            with self.subTest(endpoint=start):
                section = source.split(f'@app.post("{start}")', 1)[1].split(f'@app.', 1)[0]
                self.assertIn('if live_pipeline_state(live) == "HOLD_NO_ADMISSION":', section)
                self.assertIn("LIVE_PIPELINE_AUTHORITY_UNAVAILABLE", section)
                self.assertLess(section.index("LIVE_PIPELINE_AUTHORITY_UNAVAILABLE"), section.index("run_revenue_cycle(") if "run_revenue_cycle(" in section else len(section))

if __name__ == "__main__":
    unittest.main()
