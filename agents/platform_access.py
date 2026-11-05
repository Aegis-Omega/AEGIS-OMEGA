"""Fail-closed, stdlib-only authentication contract for AEGIS platform routes."""
from __future__ import annotations

import hashlib
import hmac

GATED_ROUTES = (
    "/platform/collaborate",
    "/platform/compare",
    "/platform/stream",
    "/platform/schedule/revenue",
    "/agents/run",
    "/agents/dispatch",
    "/agents/batch",
    "/v1/messages",
    "/predict",
)


def platform_access_state(path: str, *, configured_key: str, supplied_key: str) -> str:
    """Report HTTP authentication only; never grant Automaton-3 execution authority."""
    gated = any(path == route or path.startswith(route + "/") for route in GATED_ROUTES)
    if not gated:
        return "NOT_GATED"
    if not configured_key:
        return "SERVER_UNCONFIGURED"
    if not supplied_key or not hmac.compare_digest(supplied_key, configured_key):
        return "UNAUTHORIZED"
    return "AUTHENTICATED"

def github_webhook_auth_state(*, configured_secret: str, supplied_signature: str, body: bytes) -> str:
    """Verify GitHub webhook HMAC, denying absent configuration and invalid signatures."""
    if not configured_secret:
        return "SERVER_UNCONFIGURED"
    expected = "sha256=" + hmac.new(configured_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected):
        return "UNAUTHORIZED"
    return "AUTHENTICATED"
