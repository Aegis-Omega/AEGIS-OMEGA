#!/usr/bin/env python3
"""Behavioral guard for caller-bound durable execution identity."""
from __future__ import annotations

import ast
import io
import json
import os
import queue
import threading
import types
from unittest import TestCase, main, mock
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT / "sovereign-omega-v2" / "python" / "bridge.py"
EXECUTION_ID = "aegis-0123456789abcdef0123456789abcdef"
sys.path.insert(0, str(ROOT / "sovereign-omega-v2" / "python"))

import platform_helpers  # noqa: E402


def load_do_post():
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"), filename=str(BRIDGE))
    request_body_limit = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_MAX_REQUEST_BODY_BYTES"
            for target in node.targets
        )
    )
    bridge_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BridgeHandler")
    method = next(node for node in bridge_class.body if isinstance(node, ast.FunctionDef) and node.name == "do_POST")
    module = ast.fix_missing_locations(
        ast.Module(body=[request_body_limit, method], type_ignores=[])
    )
    namespace = {"json": json, "last_ack_sequence": -1}
    exec(compile(module, str(BRIDGE), "exec"), namespace)
    return namespace["do_POST"]


class ThreadStub:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def start(self):
        return None


class HandlerStub:
    path = "/platform/executions"

    def __init__(self, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Length": str(len(encoded)), "x-api-key": "aegis_test"}
        self.rfile = io.BytesIO(encoded)
        self.responses = []

    def _platform_respond(self, status, payload):
        self.responses.append((status, payload))


def runtime(executions):
    return {
        "_platform_verify_api_key": lambda _key: ("operator@example.invalid", "explorer"),
        "_validate_collab_req": lambda data: (data["objective"], data["mode"], data["live"], 0, ""),
        "_validate_tier_caps": lambda *_args: None,
        "_parse_max_agents": platform_helpers.parse_max_agents,
        "_validate_execution_id": platform_helpers.validate_execution_id,
        "_queue_mod": queue,
        "_executions": executions,
        "_exec_queues": {},
        "_executions_lock": threading.Lock(),
        "_reap_executions_locked": lambda: None,
        "_platform_run_collaboration": lambda *_args: None,
        "_platform_envelope": lambda execution_id, data: {"execution_id": execution_id, "data": data},
        "threading": types.SimpleNamespace(Thread=ThreadStub),
    }


class BridgeExecutionIdentityBindingTests(TestCase):
    def test_read_only_lookup_uses_supabase_get_not_increment_rpc(self):
        requests = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            @staticmethod
            def read():
                return json.dumps([{
                    "customer_email": "operator@example.invalid",
                    "tier": "operator",
                    "usage_count": 4,
                    "usage_limit": 5,
                }]).encode("utf-8")

        def urlopen(request, timeout):
            requests.append((request, timeout))
            return Response()

        with mock.patch.dict(os.environ, {
            "SUPABASE_URL": "https://supabase.example.invalid",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-test",
        }, clear=True), mock.patch("urllib.request.urlopen", side_effect=urlopen):
            principal = platform_helpers.verify_api_key_read_only("aegis_test")

        self.assertEqual(("operator@example.invalid", "operator"), principal)
        self.assertEqual(1, len(requests))
        request, timeout = requests[0]
        self.assertEqual("GET", request.get_method())
        self.assertEqual(5, timeout)
        self.assertIn("/rest/v1/api_key_store?", request.full_url)
        self.assertIn("revoked=eq.false", request.full_url)
        self.assertNotIn("verify_and_increment_api_key", request.full_url)
        self.assertIsNone(request.data)

    def test_effect_observation_authentication_is_read_only(self):
        info = {
            "customer_email": "operator@example.invalid",
            "tier": "operator",
            "usage_count": 4,
            "usage_limit": 5,
        }
        with mock.patch.object(platform_helpers, "query_api_key_info", return_value=info) as query:
            principal = platform_helpers.verify_api_key_read_only("aegis_test")

        self.assertEqual(("operator@example.invalid", "operator"), principal)
        query.assert_called_once_with("aegis_test")

        bridge_source = BRIDGE.read_text(encoding="utf-8")
        observation_branch = bridge_source.split("# GET /platform/executions/<id>", 1)[1].split(
            "elif self.path == '/platform/calibration'", 1
        )[0]
        self.assertIn("_platform_verify_api_key_read_only", observation_branch)
        self.assertNotIn("_platform_verify_api_key(", observation_branch)

    def test_supplied_execution_id_is_used_and_duplicate_is_rejected(self):
        do_post = load_do_post()
        executions = {}
        do_post.__globals__.update(runtime(executions))
        payload = {
            "execution_id": EXECUTION_ID,
            "objective": "Create a durable independently observable execution",
            "mode": "analysis",
            "live": False,
        }

        first = HandlerStub(payload)
        do_post(first)
        self.assertEqual(202, first.responses[-1][0])
        self.assertEqual(EXECUTION_ID, first.responses[-1][1]["execution_id"])
        self.assertIn(EXECUTION_ID, executions)

        duplicate = HandlerStub(payload)
        do_post(duplicate)
        self.assertEqual(409, duplicate.responses[-1][0])
        self.assertEqual("EXECUTION_ID_CONFLICT", duplicate.responses[-1][1]["code"])

    def test_unsafe_execution_id_is_rejected_without_creating_state(self):
        do_post = load_do_post()
        executions = {}
        do_post.__globals__.update(runtime(executions))
        request = HandlerStub({
            "execution_id": "../splice-target",
            "objective": "Attempt an unsafe execution identity",
            "mode": "analysis",
            "live": False,
        })

        do_post(request)

        self.assertEqual(400, request.responses[-1][0])
        self.assertEqual("INVALID_REQUEST", request.responses[-1][1]["code"])
        self.assertEqual({}, executions)


if __name__ == "__main__":
    main()
