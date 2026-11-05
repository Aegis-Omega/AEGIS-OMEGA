"""Fail-closed, stdlib-only authentication contract for AEGIS platform routes."""
from __future__ import annotations

import hmac

GATED_ROUTES = (
    "/platform/collaborate",
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
