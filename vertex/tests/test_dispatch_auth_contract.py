#!/usr/bin/env python3
"""Source-exact middleware tests without Redis, Anthropic, network or paid agents."""
import ast
import hmac
import json
import time
import unittest
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
    scope = {
        "Request": object,
        "PLATFORM_API_KEY": key,
        "_GATED_PREFIXES": ("/platform/collaborate", "/agents/run",
                            "/agents/dispatch", "/v1/messages", "/predict"),
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

    def test_github_dispatch_uses_same_header_as_proxy(self):
        content = DISPATCH_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('X-API-Key: $PLATFORM_KEY', content)
        self.assertNotIn('Authorization: Bearer $PLATFORM_KEY', content)
        self.assertIn('google-github-actions/setup-gcloud@v3', content)
        self.assertEqual(content.count("PAYLOAD=$(jq -cn"), 5)


if __name__ == "__main__":
    unittest.main()
