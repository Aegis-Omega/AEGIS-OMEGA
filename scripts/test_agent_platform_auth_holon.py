"""Execute exact production HTTP middleware and webhook functions in isolation.

No FastAPI/Anthropic/Redis imports, real sockets, secrets, or model charges.
Extract the actual AST nodes from vertex/serve.py to test code, not a rewrite.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import hmac
import json
import os
import sys
import time
import types
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "vertex" / "serve.py"
DISPATCH = REPO / ".github" / "workflows" / "agent-dispatch.yml"
REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
COST_ROUTES = (
    "/platform/collaborate",
    "/platform/compare",
    "/platform/stream",
    "/platform/schedule/revenue",
    "/agents/run",
    "/agents/batch",
    "/agents/dispatch",
    "/v1/messages",
    "/predict",
)


class FakeResponse:
    def __init__(self, content=None, status_code=200):
        self.content = content or {}
        self.status_code = status_code


class FakeRequest:
    def __init__(self, path, headers=None, body=b""):
        self.url = SimpleNamespace(path=path)
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.client = SimpleNamespace(host="127.0.0.1")
        self.method = "POST"
        self._body = body

    async def body(self):
        return self._body

    async def json(self):
        return json.loads(self._body)


class FakeState:
    def __init__(self):
        self.events = []

    async def append(self, payload, tier="T2"):
        self.events.append((payload, tier))


def load_real_function(name, *, key=""):
    syntax = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    selected = next(
        (copy.deepcopy(node) for node in syntax.body
         if isinstance(node, ast.AsyncFunctionDef) and node.name == name),
        None,
    )
    if selected is None:
        raise AssertionError(f"real FastAPI function missing: {name}")
    selected.decorator_list = []
    node = ast.fix_missing_locations(ast.Module(body=[selected], type_ignores=[]))
    state = FakeState()
    metrics = {
        "requests_total": 0,
        "errors_total": 0,
        "by_path": defaultdict(
            lambda: {"count": 0, "errors": 0, "latency_ms_sum": 0}
        ),
    }
    scope = {
        "__file__": str(SOURCE),
        "Request": object,
        "JSONResponse": lambda content, status_code=200: FakeResponse(content, status_code),
        "PLATFORM_API_KEY": key,
        "RATE_LIMIT_PER_MIN": 60,
        "_GATED_PREFIXES": COST_ROUTES,
        "_client_id": lambda request: request.client.host,
        "_rate_limited": lambda client: False,
        "METRICS": metrics,
        "time": time,
        "json": json,
        "hmac": hmac,
        "hashlib": hashlib,
        "os": os,
        "sys": sys,
        "state": state,
    }
    exec(compile(node, str(SOURCE), "exec"), scope)
    return scope[name], metrics, state


def run_guard(path, *, key="", headers=None):
    guard, metrics, _ = load_real_function("observability_and_guard", key=key)
    visited = []

    async def downstream(request):
        visited.append(request.url.path)
        return FakeResponse({"dispatched": True}, 200)

    response = asyncio.run(guard(FakeRequest(path, headers), downstream))
    return response, visited, metrics


def run_webhook(*, secret=None, headers=None, payload=None, raw=None):
    callback, _, state = load_real_function("github_webhook")
    if payload is None:
        payload = {"repository": {"full_name": REPOSITORY}, "action": "opened"}
    if raw is None:
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    headers = dict(headers or {})
    headers.setdefault("x-github-event", "issues")
    invokes = []
    coordinator = types.ModuleType("agents.coordinator")

    async def fake_dispatch_event(event_name, body):
        invokes.append((event_name, body))
        return [SimpleNamespace()]

    coordinator.dispatch_event = fake_dispatch_event
    agents = types.ModuleType("agents")
    agents.__path__ = []
    environment = {"AEGIS_GITHUB_REPOSITORY": REPOSITORY}
    if secret is not None:
        environment["GITHUB_WEBHOOK_SECRET"] = secret
    with mock.patch.dict(os.environ, environment, clear=True), mock.patch.dict(
        sys.modules, {"agents": agents, "agents.coordinator": coordinator}
    ):
        response = asyncio.run(
            callback(FakeRequest("/platform/webhooks/github", headers, raw))
        )
    return response, invokes, state.events


class AgentPlatformAuthHolonTests(unittest.TestCase):
    def test_costly_routes_require_configured_host_key(self):
        for route in COST_ROUTES:
            with self.subTest(route=route):
                resp, calls, _ = run_guard(route)
                self.assertEqual(resp.status_code, 503)
                self.assertEqual(resp.content["error"], "platform_auth_unconfigured")
                self.assertEqual(calls, [])

    def test_health_is_not_blocked(self):
        response, calls, _ = run_guard("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ["/health"])

    def test_status_is_not_costly_inference(self):
        response, calls, _ = run_guard("/platform/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ["/platform/status"])

    def test_configured_key_missing_is_denied(self):
        response, calls, _ = run_guard("/agents/dispatch", key="test-key")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(calls, [])

    def test_x_api_key_clients_still_work(self):
        response, calls, _ = run_guard(
            "/agents/run", key="test-key",
            headers={"x-api-key": "test-key"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ["/agents/run"])

    def test_dispatcher_bearer_contract_works(self):
        response, calls, _ = run_guard(
            "/agents/dispatch", key="test-key",
            headers={"authorization": "Bearer test-key"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ["/agents/dispatch"])

    def test_wrong_bearer_is_denied(self):
        resp, calls, _ = run_guard(
            "/agents/dispatch", key="test-key",
            headers={"authorization": "Bearer wrong"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(calls, [])

    def test_non_ascii_key_denied(self):
        resp, calls, _ = run_guard(
            "/agents/dispatch", key="test-key", headers={"x-api-key": "🤖"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(calls, [])

    def test_two_conflicting_header_credentials_denied(self):
        resp, calls, _ = run_guard(
            "/agents/dispatch", key="test-key",
            headers={"x-api-key": "test-key", "authorization": "Bearer different"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(calls, [])

    def test_actual_dispatcher_uses_supported_bearer_scheme(self):
        source = DISPATCH.read_text(encoding="utf-8")
        self.assertIn('Authorization: Bearer $PLATFORM_KEY', source)
        self.assertIn('if: vars.PROXY_URL != ' + "''", source)

    def test_webhook_missing_secret_never_dispatches(self):
        response, calls, _ = run_webhook(secret=None)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(calls, [])

    def test_webhook_forged_or_missing_hmac_is_denied(self):
        for sig in (None, "sha256=" + "0" * 64):
            with self.subTest(sig=sig):
                headers = {"x-hub-signature-256": sig} if sig else {}
                response, calls, _ = run_webhook(secret="unit-test", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(calls, [])

    def test_signed_forged_repository_is_denied(self):
        payload = {"repository": {"full_name": "attacker/forged"}, "action": "opened"}
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        sig = "sha256=" + hmac.new(b"unit-test", raw, hashlib.sha256).hexdigest()
        response, calls, _ = run_webhook(
            secret="unit-test", raw=raw, headers={"x-hub-signature-256": sig}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(calls, [])

    def test_signed_malformed_json_is_denied(self):
        raw = b'{"repository": broken json'
        sig = "sha256=" + hmac.new(b"unit-test", raw, hashlib.sha256).hexdigest()
        response, calls, _ = run_webhook(
            secret="unit-test", raw=raw, headers={"x-hub-signature-256": sig}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(calls, [])

    def test_signed_array_not_repository_is_denied(self):
        raw = b"[]"
        sig = "sha256=" + hmac.new(b"unit-test", raw, hashlib.sha256).hexdigest()
        response, calls, _ = run_webhook(
            secret="unit-test", raw=raw, headers={"x-hub-signature-256": sig}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(calls, [])

    def test_signed_unexpected_event_denied(self):
        payload = {"repository": {"full_name": REPOSITORY}, "action": "opened"}
        raw = json.dumps(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(b"unit-test", raw, hashlib.sha256).hexdigest()
        response, calls, _ = run_webhook(secret="unit-test", raw=raw, headers={
            "x-hub-signature-256": sig, "x-github-event": "fork",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(calls, [])

    def test_verified_webhook_dispatches_exact_signed_payload(self):
        payload = {"repository": {"full_name": REPOSITORY}, "action": "opened"}
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        sig = "sha256=" + hmac.new(b"unit-test", raw, hashlib.sha256).hexdigest()
        response, calls, evidence = run_webhook(
            secret="unit-test", raw=raw, headers={
                "x-hub-signature-256": sig, "x-github-event": "issues",
            }
        )
        self.assertIsInstance(response, dict)
        self.assertEqual(response["dispatched_to_agents"], 1)
        self.assertEqual(calls, [("issues", payload)])
        self.assertEqual(evidence[0][0]["dispatched_to_agents"], 1)


if __name__ == "__main__":
    unittest.main()
