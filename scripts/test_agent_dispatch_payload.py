"""Regression tests for the bounded GitHub-to-agent dispatch envelope."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("agent_dispatch_payload.py")
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
WORKFLOW = ROOT / ".github" / "workflows" / "agent-dispatch.yml"
AUTH_WORKFLOW = ROOT / ".github" / "workflows" / "authorization-effect-chain.yml"
VERTEX = ROOT / "vertex" / "serve.py"
COORDINATOR = ROOT / "agents" / "coordinator_legacy.py"
AUTOMATON3 = ROOT / "scripts" / "validate-automaton3.py"

from harness.sdk.sovereign_execution import canonical_hash  # noqa: E402


def _load_module():
    spec = importlib.util.spec_from_file_location("agent_dispatch_payload", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load agent dispatch payload module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentDispatchPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_workflow_run_uses_conclusion_and_stable_metadata(self) -> None:
        request = self.module.classify_event(
            "workflow_run",
            {
                "workflow_run": {
                    "id": 42,
                    "conclusion": "failure",
                    "head_branch": "feat/example",
                    "head_sha": "a" * 40,
                    "html_url": "https://github.example/runs/42",
                }
            },
        )

        self.assertEqual(request["event_type"], "github_ci_failure")
        self.assertEqual(request["payload"]["run_id"], "42")
        self.assertEqual(request["payload"]["head_sha"], "a" * 40)

    def test_pull_request_action_is_not_collapsed_to_opened(self) -> None:
        request = self.module.classify_event(
            "pull_request",
            {
                "action": "synchronize",
                "number": 334,
                "pull_request": {
                    "title": "Bounded title",
                    "html_url": "https://github.example/pull/334",
                    "head": {"sha": "b" * 40},
                },
            },
        )

        self.assertEqual(request["event_type"], "github_pr_synchronize")
        self.assertEqual(request["payload"]["number"], "334")

    def test_issue_action_is_preserved_and_untrusted_text_is_bounded(self) -> None:
        request = self.module.classify_event(
            "issues",
            {
                "action": "labeled",
                "issue": {
                    "number": 9,
                    "title": "t" * 400,
                    "body": "b" * 10_000,
                    "html_url": "https://github.example/issues/9",
                },
                "label": {"name": "aegis-agent"},
            },
        )

        self.assertEqual(request["event_type"], "github_issue_labeled")
        self.assertLessEqual(len(request["payload"]["title"]), 256)
        self.assertLessEqual(len(request["payload"]["body"]), 2_000)
        self.assertEqual(request["payload"]["label"], "aegis-agent")

        ignored = self.module.classify_event(
            "issues",
            {
                "action": "labeled",
                "issue": {"number": 9, "title": "Not explicitly routed"},
                "label": {"name": "bug"},
            },
        )
        self.assertIsNone(ignored)

    def test_comment_requires_explicit_mention_and_is_bounded(self) -> None:
        ignored = self.module.classify_event(
            "issue_comment", {"comment": {"body": "ordinary comment"}}
        )
        self.assertIsNone(ignored)

        request = self.module.classify_event(
            "issue_comment",
            {
                "comment": {"body": "@aegis-agent " + "x" * 10_000},
                "issue": {"number": 12, "html_url": "https://github.example/issues/12"},
            },
        )
        self.assertEqual(request["event_type"], "github_issue_comment_mention")
        self.assertLessEqual(len(request["payload"]["body"]), 2_000)

    def test_serialized_request_has_a_hard_size_ceiling(self) -> None:
        request = self.module.classify_event(
            "issues",
            {
                "action": "labeled",
                "issue": {"title": "t" * 10_000, "body": "b" * 50_000},
                "label": {"name": "aegis-agent"},
            },
        )
        encoded = json.dumps(request, separators=(",", ":"), sort_keys=True).encode()
        self.assertLessEqual(len(encoded), self.module.MAX_REQUEST_BYTES)

    def test_unknown_event_fails_closed(self) -> None:
        self.assertIsNone(self.module.classify_event("repository_dispatch", {}))

    def test_oidc_audience_matches_server_request_commitment(self) -> None:
        request = {
            "event_type": "github_ci_failure",
            "payload": {"head_sha": "a" * 40, "run_id": "42"},
        }
        expected = "aegis-agent-dispatch:" + canonical_hash(
            "AEGIS_AGENT_DISPATCH_REQUEST_V1", request
        )

        try:
            actual = self.module.oidc_audience(request)
        except AttributeError as exc:
            self.fail(f"payload builder lacks request-bound OIDC audience: {exc}")
        self.assertEqual(actual, expected)

    def test_workflow_has_visible_preflight_and_real_ci_trigger(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('workflows: ["⊕ AEGIS-Ω Constitutional Automaton"]', workflow)
        self.assertNotIn("pull_request:\n", workflow)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", workflow)
        self.assertNotIn("if: vars.PROXY_URL != ''", workflow)
        self.assertIn("DEFERRED_NOT_CONFIGURED", workflow)
        self.assertIn("scripts/agent_dispatch_payload.py", workflow)

    def test_network_dispatch_is_authenticated_bounded_and_checked(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("secrets.AGENT_DISPATCH_API_KEY", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("--audience-output", workflow)
        self.assertIn('x-api-key: $DISPATCH_API_KEY', workflow)
        self.assertIn('x-aegis-github-oidc: $oidc_token', workflow)
        self.assertIn("--max-time 30", workflow)
        self.assertIn("--max-filesize 65536", workflow)
        self.assertIn("--fail-with-body", workflow)
        self.assertIn("jq -e", workflow)

    def test_authority_receipts_and_event_routes_are_replay_bound(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        vertex = VERTEX.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        automaton3 = AUTOMATON3.read_text(encoding="utf-8")

        self.assertIn('"routing_receipts": last_dispatch_receipts()', vertex)
        self.assertIn("MAX_AGENT_DISPATCH_REQUEST_BYTES = 8_192", vertex)
        self.assertIn("async for chunk in request.stream():", vertex)
        self.assertNotIn("raw_body = await request.body()", vertex)
        self.assertIn("dispatch_replay_key", vertex)
        self.assertIn("AEGIS_IMAGE_SOURCE_COMMIT", vertex)
        self.assertIn("if event_type not in EVENT_ROUTING:", vertex)
        self.assertIn('dispatch_status="EXECUTED"', workflow)
        self.assertIn('dispatch_status="DENIED"', workflow)
        self.assertIn("routing_receipt_count", workflow)
        self.assertIn("response_sha256", workflow)
        self.assertIn('"github_pr_synchronize"', coordinator)
        self.assertIn('"github_pr_review_requested"', coordinator)
        self.assertIn('"github_issue_labeled"', coordinator)
        self.assertIn('"github_issue_comment_mention"', coordinator)
        self.assertIn('"scripts/agent_dispatch_payload.py"', automaton3)
        self.assertIn('"scripts/test_agent_dispatch_payload.py"', automaton3)

    def test_authorization_ci_builds_and_inspects_the_deployable_image(self) -> None:
        workflow = AUTH_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("docker build --tag", workflow)
        self.assertIn("--file vertex/Dockerfile", workflow)
        self.assertIn("AEGIS_IMAGE_SOURCE_COMMIT", workflow)
        self.assertIn("/app/CONSTITUTIONAL_DECLARATION.md", workflow)
        self.assertIn("/app/.claude.json", workflow)
        self.assertIn("/app/skill-hashes.sha256", workflow)
        self.assertIn("/app/docs/claims.json", workflow)
        self.assertIn("harness.sdk.github_dispatch_identity", workflow)


if __name__ == "__main__":
    unittest.main()
