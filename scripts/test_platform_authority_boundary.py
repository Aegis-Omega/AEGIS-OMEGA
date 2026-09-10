#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "vertex" / "authority_boundary.py"


def load_module():
    spec = importlib.util.spec_from_file_location("aegis_authority_boundary", MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load authority boundary")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def call_app(boundary, path: str, headers: list[tuple[bytes, bytes]] | None = None):
    sent: list[dict] = []
    called = {"value": False}

    async def downstream(scope, receive, send):
        called["value"] = True
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    wrapped = boundary(downstream)
    scope = {"type": "http", "method": "POST", "path": path, "headers": headers or []}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await wrapped(scope, receive, send)
    status = next(message["status"] for message in sent if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    return status, called["value"], body


class PlatformAuthorityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_module()

    def test_paid_route_without_platform_key_is_unavailable(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            status, called, body = asyncio.run(call_app(self.mod.AuthorityBoundary, "/agents/dispatch"))
        self.assertEqual(status, 503)
        self.assertFalse(called)
        self.assertIn(b"AUTHORITY_UNAVAILABLE", body)

    def test_wrong_key_is_denied(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_API_KEY": "correct"}, clear=True):
            status, called, _ = asyncio.run(call_app(
                self.mod.AuthorityBoundary,
                "/agents/dispatch",
                [(b"x-api-key", b"wrong")],
            ))
        self.assertEqual(status, 401)
        self.assertFalse(called)

    def test_exact_key_reaches_application(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_API_KEY": "correct"}, clear=True):
            status, called, _ = asyncio.run(call_app(
                self.mod.AuthorityBoundary,
                "/agents/dispatch",
                [(b"x-api-key", b"correct")],
            ))
        self.assertEqual(status, 204)
        self.assertTrue(called)

    def test_public_health_remains_public(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            status, called, _ = asyncio.run(call_app(self.mod.AuthorityBoundary, "/health"))
        self.assertEqual(status, 204)
        self.assertTrue(called)

    def test_webhook_secret_cannot_be_implicitly_optional(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_API_KEY": "correct"}, clear=True):
            status, called, body = asyncio.run(call_app(self.mod.AuthorityBoundary, "/platform/webhooks/github"))
        self.assertEqual(status, 503)
        self.assertFalse(called)
        self.assertIn(b"WEBHOOK_AUTHORITY_UNAVAILABLE", body)

    def test_all_known_paid_prefixes_are_gated(self) -> None:
        expected = {
            "/predict", "/v1/messages", "/agents/run", "/agents/dispatch", "/agents/batch",
            "/platform/collaborate", "/platform/compare", "/platform/stream", "/platform/schedule/",
        }
        self.assertLessEqual(expected, set(self.mod.GATED_PREFIXES))


if __name__ == "__main__":
    unittest.main()
