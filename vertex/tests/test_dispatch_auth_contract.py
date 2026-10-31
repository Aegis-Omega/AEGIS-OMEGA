#!/usr/bin/env python3
"""Source-exact middleware tests without Redis, Anthropic, network or paid agents."""
import ast
import hashlib
import hmac
import json
import os
import sys
import time
import types
import unittest
from unittest.mock import AsyncMock, patch
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
PROXY_SOURCE = ROOT / "vertex" / "serve.py"
DISPATCH_WORKFLOW = ROOT / ".github" / "workflows" / "agent-dispatch.yml"


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code


def source_middleware(key):
    # Execute the literal production middleware AST without importing any
    # optional inference client, Redis service or global application lifespan.
    tree = ast.parse(PROXY_SOURCE.read_text(encoding="utf-8"))
    candidates = [node for node in tree.body
                  if isinstance(node, ast.AsyncFunctionDef)
                  and node.name == "observability_and_guard"]
    if len(candidates) != 1:
        raise AssertionError("expected one production middleware function")
    function = candidates[0]
    function.decorator_list = []
    tree = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    metrics = {
        "requests_total": 0,
        "errors_total": 0,
        "by_path": defaultdict(lambda: {"count": 0, "errors": 0, "latency_ms_sum": 0}),
    }
    # Read the real production route list; never hide a missing gate behind
    # test-only duplicated constants.
    gate_nodes = [
        stmt.value for stmt in tree.body
        if isinstance(stmt, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "_GATED_PREFIXES"
                for t in stmt.targets)
    ]
    if len(gate_nodes) != 1:
        raise AssertionError("expected one production gated route list")
    protected_paths = ast.literal_eval(gate_nodes[0])
    scope = {
        "Request": object,
        "PLATFORM_API_KEY": key,
        "_GATED_PREFIXES": protected_paths,
        "_client_id": lambda request: "test-client",
        "_rate_limited": lambda client: False,
        "METRICS": metrics,
        "RATE_LIMIT_PER_MIN": 60,
        "JSONResponse": FakeResponse,
        "time": time,
        "json": json,
        "hmac": hmac,
    }
    exec(compile(tree, str(PROXY_SOURCE), "exec"), scope)
    return scope["observability_and_guard"]


async def check_middleware(key, headers, path="/agents/dispatch"):
    middleware = source_middleware(key)
    counter = [0]
    request = SimpleNamespace(
        url=SimpleNamespace(path=path),
        client=SimpleNamespace(host="127.0.0.1"),
        method="POST",
        headers=headers,
    )

    async def downstream(_request):
        counter[0] += 1
        return FakeResponse({"status": "downstream"}, 200)

    response = await middleware(request, downstream)
    return response, counter[0]



def source_webhook():
    """Execute the exact production webhook AST without optional cloud clients."""
    tree = ast.parse(PROXY_SOURCE.read_text(encoding="utf-8"))
    handlers = [n for n in tree.body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "github_webhook"]
    if len(handlers) != 1:
        raise AssertionError("expected exactly one GitHub webhook handler")
    handler = handlers[0]
    handler.decorator_list = []
    scope = {
        "Request": object,
        "os": os,
        "json": json,
        "JSONResponse": FakeResponse,
        "state": SimpleNamespace(append=AsyncMock()),
        "__file__": str(PROXY_SOURCE),
    }
    module = ast.fix_missing_locations(ast.Module(body=[handler], type_ignores=[]))
    exec(compile(module, str(PROXY_SOURCE), "exec"), scope)
    return scope["github_webhook"]


class FakeWebhookRequest:
    def __init__(self, raw_body=b"{}", headers=None):
        self.raw_body = raw_body
        self.headers = headers or {}

    async def body(self):
        return self.raw_body

    async def json(self):
        return json.loads(self.raw_body)


class DispatchAuthContract(unittest.IsolatedAsyncioTestCase):
    async def test_missing_platform_key_denies_before_dispatch(self):
        response, calls = await check_middleware("", {})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(calls, 0)
        self.assertEqual(response.body["error"], "dispatch_auth_unconfigured")

    async def test_wrong_key_denies_before_dispatch(self):
        response, calls = await check_middleware(
            "test-secret", {"x-api-key": "wrong"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(calls, 0)

    async def test_bearer_header_does_not_bypass_x_api_key(self):
        response, calls = await check_middleware(
            "test-secret", {"Authorization": "Bearer test-secret"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(calls, 0)

    async def test_matching_key_reaches_only_intended_handler(self):
        response, calls = await check_middleware(
            "test-secret", {"x-api-key": "test-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, 1)

    async def test_non_cost_health_remains_available_without_key(self):
        response, calls = await check_middleware("", {}, "/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, 1)

    async def test_agent_run_existing_key_gate_still_denies_invalid(self):
        response, calls = await check_middleware(
            "test-secret", {}, "/agents/run")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(calls, 0)


    async def test_all_compute_routes_deny_without_platform_key(self):
        routes = (
            "/platform/collaborate", "/platform/compare", "/platform/stream",
            "/platform/schedule/revenue", "/agents/run", "/agents/dispatch",
            "/agents/batch", "/v1/messages", "/predict",
        )
        for path in routes:
            with self.subTest(path=path):
                response, calls = await check_middleware("", {}, path)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(calls, 0)

    async def test_all_compute_routes_reject_invalid_platform_key(self):
        routes = (
            "/platform/collaborate", "/platform/compare", "/platform/stream",
            "/platform/schedule/revenue", "/agents/run", "/agents/dispatch",
            "/agents/batch", "/v1/messages", "/predict",
        )
        for path in routes:
            with self.subTest(path=path):
                response, calls = await check_middleware(
                    "test-secret", {"x-api-key": "wrong"}, path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(calls, 0)

    async def test_all_compute_routes_require_correct_platform_key(self):
        for path in (
            "/platform/collaborate", "/platform/compare", "/platform/stream",
            "/platform/schedule/revenue", "/agents/run", "/agents/dispatch",
            "/agents/batch", "/v1/messages", "/predict",
        ):
            with self.subTest(path=path):
                response, calls = await check_middleware(
                    "test-secret", {"x-api-key": "test-secret"}, path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(calls, 1)

    def test_github_dispatch_uses_same_header_as_proxy(self):
        content = DISPATCH_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('X-API-Key: $PLATFORM_KEY', content)
        self.assertNotIn('Authorization: Bearer $PLATFORM_KEY', content)
        self.assertIn('google-github-actions/setup-gcloud@v3', content)
        self.assertEqual(content.count("PAYLOAD=$(jq -cn"), 5)



class GithubWebhookSignatureContract(unittest.IsolatedAsyncioTestCase):
    async def test_unconfigured_secret_denies_before_json_or_dispatch(self):
        req = FakeWebhookRequest(b'{"synthetic": true}', {"x-github-event": "push"})
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": ""}):
            response = await source_webhook()(req)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.body["error"], "webhook_auth_unconfigured")

    async def test_bad_or_missing_signature_denied(self):
        body = b'{"repository":{"full_name":"Aegis-Omega/AEGIS-OMEGA"}}'
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "test-signing-key"}):
            for sig in ("", "sha256=" + "0" * 64, "sha1=invalid"):
                req = FakeWebhookRequest(body, {
                    "x-hub-signature-256": sig, "x-github-event": "push"})
                response = await source_webhook()(req)
                self.assertEqual(response.status_code, 401)

    async def test_valid_signature_required_even_for_malformed_json(self):
        secret = "test-signing-key"
        for body, expected_status in [(b"not json", 400), (b"[]", 400),
                                      (b"x" * 262145, 413)]:
            sig = "sha256=" + hmac.new(
                secret.encode(), body, hashlib.sha256).hexdigest()
            with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
                req = FakeWebhookRequest(body, {
                    "x-hub-signature-256": sig, "x-github-event": "push"})
                response = await source_webhook()(req)
            self.assertEqual(response.status_code, expected_status)

    async def test_signed_other_repo_cannot_dispatch(self):
        secret = "test-signing-key"
        for body in (
            b'{"repository":{"full_name":"attacker/other"}}',
            b'{"repository":{"full_name":"Aegis-Omega/AEGIS-OMEGA-fork"}}',
            b'{"repository":null}',
            b'{"repository":"Aegis-Omega/AEGIS-OMEGA"}',
            b'{}',
        ):
            with self.subTest(body=body):
                sig = "sha256=" + hmac.new(
                    secret.encode(), body, hashlib.sha256).hexdigest()
                with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
                    req = FakeWebhookRequest(body, {
                        "x-hub-signature-256": sig,
                        "x-github-event": "push",
                    })
                    response = await source_webhook()(req)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.body["error"], "untrusted_webhook_repository")

    async def test_signed_unknown_event_cannot_dispatch(self):
        secret = "test-signing-key"
        body = b'{"repository":{"full_name":"Aegis-Omega/AEGIS-OMEGA"}}'
        sig = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256).hexdigest()
        for event in ("", "deployment", "untrusted_external", "workflow_dispatch"):
            with self.subTest(event=event):
                with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
                    req = FakeWebhookRequest(body, {
                        "x-hub-signature-256": sig,
                        "x-github-event": event,
                    })
                    response = await source_webhook()(req)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.body["error"], "unsupported_webhook_event")

    async def test_signed_untrusted_pr_and_issue_actor_denied(self):
        secret = "test-signing-key"
        base = {"repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA"},
                "sender": {"login": "attacker"}, "action": "opened"}
        variants = [
            ("pull_request", {
                "pull_request": {
                    "user": {"login": "trusted-owner"}, "author_association": "OWNER",
                    "head": {"repo": {"full_name": "Aegis-Omega/AEGIS-OMEGA"}}}}),
            ("pull_request", {
                "pull_request": {
                    "user": {"login": "attacker"}, "author_association": "OWNER",
                    "head": {"repo": {"full_name": "outsider/fork"}}}}),
            ("pull_request", {
                "pull_request": {
                    "user": {"login": "attacker"}, "author_association": "NONE",
                    "head": {"repo": {"full_name": "Aegis-Omega/AEGIS-OMEGA"}}}}),
            ("issues", {"issue": {
                "user": {"login": "trusted-owner"}, "author_association": "OWNER"}}),
            ("issues", {"issue": {
                "user": {"login": "attacker"}, "author_association": "NONE"}}),
            ("pull_request_review", {
                "review": {"user": {"login": "trusted-owner"},
                           "author_association": "OWNER"},
                "pull_request": {"head": {"repo": {
                    "full_name": "Aegis-Omega/AEGIS-OMEGA"}}}}),
        ]
        for event, addition in variants:
            with self.subTest(event=event, addition=addition):
                payload = dict(base, **addition)
                raw = json.dumps(payload, sort_keys=True).encode("utf8")
                sig = "sha256=" + hmac.new(
                    secret.encode(), raw, hashlib.sha256).hexdigest()
                with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
                    req = FakeWebhookRequest(raw, {
                        "x-hub-signature-256": sig,
                        "x-github-event": event,
                    })
                    result = await source_webhook()(req)
                self.assertEqual(result.status_code, 403)
                self.assertEqual(result.body["error"], "untrusted_webhook_actor")

    async def test_signed_push_must_be_normal_protected_main(self):
        secret = "test-signing-key"
        base = {"repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA"},
                "sender": {"login": "trusted-owner"},
                "pusher": {"name": "trusted-owner"},
                "ref": "refs/heads/main", "deleted": False, "forced": False}
        for field, value in (("ref", "refs/heads/feature"),
                             ("deleted", True), ("forced", True),
                             ("pusher", {"name": "someone-else"})):
            with self.subTest(field=field):
                raw = json.dumps(dict(base, **{field: value})).encode("utf8")
                sig = "sha256=" + hmac.new(
                    secret.encode(), raw, hashlib.sha256).hexdigest()
                with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
                    req = FakeWebhookRequest(raw, {
                        "x-hub-signature-256": sig, "x-github-event": "push"})
                    result = await source_webhook()(req)
                self.assertEqual(result.status_code, 403)

    async def test_signed_check_run_requires_completed_actions_main(self):
        secret = "test-signing-key"
        base = {"repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA"},
                "sender": {"login": "github-actions[bot]"},
                "action": "completed",
                "check_run": {"app": {"slug": "github-actions"},
                              "check_suite": {"head_branch": "main"}}}
        for field, value in (
                ("action", "created"),
                ("check_run", {"app": {"slug": "outside-app"},
                               "check_suite": {"head_branch": "main"}}),
                ("check_run", {"app": {"slug": "github-actions"},
                               "check_suite": {"head_branch": "pr-123"}})):
            raw = json.dumps(dict(base, **{field: value})).encode("utf8")
            sig = "sha256=" + hmac.new(
                secret.encode(), raw, hashlib.sha256).hexdigest()
            with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
                req = FakeWebhookRequest(raw, {
                    "x-hub-signature-256": sig, "x-github-event": "check_run"})
                result = await source_webhook()(req)
            self.assertEqual(result.status_code, 403)

    async def test_signed_webhooks_route_only_canonical_coordinator_events(self):
        secret = "test-signing-key"
        base = {"repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA"},
                "sender": {"login": "trusted-owner"}}
        examples = [
            ("pull_request", dict(base, action="opened", pull_request={
                "user": {"login": "trusted-owner"}, "author_association": "OWNER",
                "head": {"repo": {"full_name": "Aegis-Omega/AEGIS-OMEGA"}},
                "title": "Review source", "number": 569, "html_url": "https://github.com/example"
            }), "github_pr_opened", "title"),
            ("issues", dict(base, action="opened", issue={
                "user": {"login": "trusted-owner"}, "author_association": "OWNER",
                "title": "Fix issue", "number": 10, "body": "Minimal description"
            }), "github_issue_opened", "title"),
            ("pull_request_review", dict(base, action="submitted",
                review={"user": {"login": "trusted-owner"},
                        "author_association": "OWNER", "body": "Review body"},
                pull_request={"number": 569, "head": {"repo": {
                    "full_name": "Aegis-Omega/AEGIS-OMEGA"}}}
            ), "github_pr_comment", "body"),
            ("check_run", dict(base, action="completed",
                check_run={"app": {"slug": "github-actions"},
                           "check_suite": {"head_branch": "main"},
                           "conclusion": "failure", "id": 42,
                           "name": "static gate"}
            ), "github_ci_failure", "failures"),
        ]
        for kind, payload, expected, required_field in examples:
            with self.subTest(kind=kind):
                seen = []
                async def fake_dispatch(event, data):
                    seen.append((event, data))
                    return [object()]
                agents = types.ModuleType("agents")
                coordinator = types.ModuleType("agents.coordinator")
                coordinator.dispatch_event = fake_dispatch
                agents.coordinator = coordinator
                raw = json.dumps(payload).encode("utf8")
                sig = "sha256=" + hmac.new(
                    secret.encode(), raw, hashlib.sha256).hexdigest()
                with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
                    with patch.dict(sys.modules, {"agents": agents,
                                                   "agents.coordinator": coordinator}):
                        req = FakeWebhookRequest(raw, {
                            "x-hub-signature-256": sig, "x-github-event": kind})
                        response = await source_webhook()(req)
                self.assertEqual(response["dispatched_to_agents"], 1)
                self.assertEqual(len(seen), 1)
                self.assertEqual(seen[0][0], expected)
                self.assertIn(required_field, seen[0][1])
                self.assertNotIn("repository", seen[0][1])
                self.assertNotIn("sender", seen[0][1])

    async def test_signed_nonfinal_check_run_cannot_route_agents(self):
        secret = "test-signing-key"
        payload = {"repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA"},
                   "sender": {"login": "github-actions[bot]"},
                   "action": "completed",
                   "check_run": {"app": {"slug": "github-actions"},
                                 "check_suite": {"head_branch": "main"},
                                 "conclusion": "neutral"}}
        raw = json.dumps(payload).encode("utf8")
        sig = "sha256=" + hmac.new(
            secret.encode(), raw, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            req = FakeWebhookRequest(raw, {
                "x-hub-signature-256": sig, "x-github-event": "check_run"})
            response = await source_webhook()(req)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.body["error"], "unsupported_check_conclusion")

    async def test_signed_valid_event_invokes_only_stubbed_agent(self):
        secret = "test-signing-key"
        body = (b'{"repository":{"full_name":"Aegis-Omega/AEGIS-OMEGA"},'
                b'"sender":{"login":"trusted-owner"},'
                b'"pusher":{"name":"trusted-owner"},'
                b'"ref":"refs/heads/main","deleted":false,"forced":false}')
        signature = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256).hexdigest()
        seen = []
        async def fake_dispatch(event, payload):
            seen.append((event, payload))
            return [object()]
        agents = types.ModuleType("agents")
        coordinator = types.ModuleType("agents.coordinator")
        coordinator.dispatch_event = fake_dispatch
        agents.coordinator = coordinator
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            with patch.dict(sys.modules, {
                "agents": agents,
                "agents.coordinator": coordinator,
            }):
                req = FakeWebhookRequest(body, {
                    "x-hub-signature-256": signature,
                    "x-github-event": "push",
                })
                response = await source_webhook()(req)
        self.assertEqual(response["dispatched_to_agents"], 1)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], "github_main_push")
        self.assertEqual(seen[0][1]["branch"], "main")
        self.assertNotIn("repository", seen[0][1])


if __name__ == "__main__":
    unittest.main()
