"""Outer ASGI authority boundary for the AEGIS agent platform.

This module is intentionally standard-library only.  It executes before the
FastAPI application and prevents a missing runtime secret from silently turning
paid agent/model routes into public capabilities.
"""
from __future__ import annotations

import hmac
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

ASGIApp = Callable[[dict[str, Any], Callable[..., Awaitable[dict[str, Any]]], Callable[..., Awaitable[None]]], Awaitable[None]]

GATED_PREFIXES = (
    "/predict",
    "/v1/messages",
    "/agents/run",
    "/agents/dispatch",
    "/agents/batch",
    "/platform/collaborate",
    "/platform/compare",
    "/platform/stream",
    "/platform/schedule/",
)
GITHUB_WEBHOOK_PREFIX = "/platform/webhooks/github"


async def _json_response(send: Callable[..., Awaitable[None]], status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _header(scope: dict[str, Any], name: bytes) -> str:
    wanted = name.lower()
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name.lower() == wanted:
            return raw_value.decode("utf-8", errors="strict")
    return ""


class AuthorityBoundary:
    """Fail closed before the application sees an authority-bearing request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))

        # GitHub webhook verification remains inside serve.py, where the exact
        # request body is checked with HMAC-SHA256.  The outer boundary ensures
        # that verification can never degrade to optional merely because the
        # secret was omitted at deployment time.
        if path.startswith(GITHUB_WEBHOOK_PREFIX) and not os.environ.get("GITHUB_WEBHOOK_SECRET", ""):
            await _json_response(
                send,
                503,
                {
                    "error": "WEBHOOK_AUTHORITY_UNAVAILABLE",
                    "detail": "GITHUB_WEBHOOK_SECRET is not configured",
                },
            )
            return

        if any(path.startswith(prefix) for prefix in GATED_PREFIXES):
            platform_key = os.environ.get("PLATFORM_API_KEY", "")
            if not platform_key:
                await _json_response(
                    send,
                    503,
                    {
                        "error": "AUTHORITY_UNAVAILABLE",
                        "detail": "PLATFORM_API_KEY is not configured",
                    },
                )
                return

            provided = _header(scope, b"x-api-key")
            if not provided or not hmac.compare_digest(provided, platform_key):
                await _json_response(send, 401, {"error": "UNAUTHORIZED"})
                return

        await self.app(scope, receive, send)
