"""Security overlay for the existing AEGIS FastAPI application.

This module deliberately keeps the legacy route surface intact while replacing
its audit-state implementation and adding a fail-closed outer authorization
boundary for sensitive operational endpoints. Docker starts this module instead
of importing serve:app directly.
"""
from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

import serve as legacy
from audit_chain_v2 import ChainStateV2

# Replace process-local sequence authority before FastAPI lifespan executes.
legacy.state = ChainStateV2(
    legacy.REDIS_URL,
    chain_key=legacy.CHAIN_KEY,
    max_entries=legacy.MAX_CHAIN_ENTRIES,
)

app = legacy.app

# Cost-bearing routes were already gated conditionally in serve.py. This outer
# boundary makes the requirement unconditional at runtime and extends it to
# audit/metrics surfaces that expose operational evidence.
_PROTECTED_PREFIXES = tuple(legacy._GATED_PREFIXES) + (
    "/metrics",
    "/v1/audit",
    "/agents/roles",
)


def _authorized(request: Request) -> bool:
    expected = os.environ.get("PLATFORM_API_KEY", "").strip()
    provided = request.headers.get("x-api-key", "")
    if not expected or not provided:
        return False
    # compare_digest avoids value-dependent string comparison at this boundary.
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


@app.middleware("http")
async def daybreak_security_boundary(request: Request, call_next):
    path = request.url.path
    if any(path.startswith(prefix) for prefix in _PROTECTED_PREFIXES):
        if not _authorized(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    # Reject obviously oversized declared request bodies before model/tool routes
    # parse them. Chunked/no-length requests remain bounded by upstream Cloud Run
    # and application-specific token limits; this is not claimed as a full body
    # streaming limiter.
    if request.method in {"POST", "PUT", "PATCH"} and any(
        path.startswith(prefix) for prefix in legacy._GATED_PREFIXES
    ):
        raw_length = request.headers.get("content-length")
        if raw_length:
            try:
                content_length = int(raw_length)
            except ValueError:
                return JSONResponse({"error": "invalid_content_length"}, status_code=400)
            if content_length < 0 or content_length > 2_097_152:
                return JSONResponse({"error": "request_too_large"}, status_code=413)

    response = await call_next(request)
    # Operational surfaces should not be cached by intermediaries.
    if any(path.startswith(prefix) for prefix in _PROTECTED_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response
