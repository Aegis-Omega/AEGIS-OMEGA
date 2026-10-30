#!/usr/bin/env python3
"""AEGIS / Nebius Token Factory read-only authentication and model preflight.

This probe *only* performs GET /v1/models. It never performs inference,
creates a cloud resource, changes provider availability, or prints credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_BASE_URL = "https://api.tokenfactory.us-north1.nebius.com/v1/"
DEFAULT_MODEL = "MiniMaxAI/MiniMax-M3.1-Flash"
APPROVED_HOSTS = frozenset({
    "api.tokenfactory.us-north1.nebius.com",
    "api.tokenfactory.nebius.com",
})


class NoCredentialRedirects(HTTPRedirectHandler):
    """Never forward provider credentials to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def models_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in APPROVED_HOSTS
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query or parsed.fragment
        or parsed.path.rstrip("/") not in ("", "/v1")
    ):
        raise ValueError("Nebius endpoint must be an approved HTTPS Token Factory /v1 URL")
    return f"https://{parsed.hostname}/v1/models"


def probe(*, token: str, model: str, base_url: str = DEFAULT_BASE_URL,
          opener=None, timeout: float = 12.0) -> dict:
    """Make at most one non-billable model-list GET; return a sanitized receipt."""
    receipt = {
        "schema": "aegis.nebius.preflight.v1",
        "provider": "nebius-token-factory",
        "model": model,
        "status": "UNKNOWN",
        "authenticated": False,
        "model_available": False,
        "paid_inference_calls": 0,
        "authority_effect": "NONE",
    }
    if not token.strip():
        receipt["status"] = "CREDENTIAL_MISSING"
        return receipt
    if not model or len(model) > 256 or any(c.isspace() for c in model):
        receipt["status"] = "INVALID_MODEL_ID"
        return receipt
    try:
        url = models_url(base_url)
    except ValueError:
        receipt["status"] = "INVALID_ENDPOINT"
        return receipt

    req = Request(url, method="GET", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        # urllib's default redirect handler forwards Authorization; do not use it.
        # Injected openers are reserved for unit tests, not production execution.
        safe_open = opener if opener is not None else build_opener(NoCredentialRedirects()).open
        with safe_open(req, timeout=timeout) as response:
            # Bounded response; never persist or echo arbitrary provider content.
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                receipt["status"] = "RESPONSE_TOO_LARGE"
                return receipt
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                receipt["status"] = "RESPONSE_INVALID"
                return receipt
            model_ids = {
                row.get("id") for row in data["data"]
                if isinstance(row, dict) and isinstance(row.get("id"), str)
            }
            receipt["authenticated"] = True
            receipt["model_available"] = model in model_ids
            receipt["status"] = "MODEL_AVAILABLE" if receipt["model_available"] else "MODEL_NOT_LISTED"
            return receipt
    except HTTPError as exc:
        receipt["status"] = (
            "REDIRECT_BLOCKED" if exc.code in (301, 302, 303, 307, 308)
            else {401: "AUTH_REJECTED", 403: "AUTH_FORBIDDEN", 429: "RATE_LIMITED"}.get(
                exc.code, "UPSTREAM_HTTP_ERROR"
            )
        )
        receipt["http_status"] = exc.code
        return receipt
    except (URLError, TimeoutError, OSError):
        receipt["status"] = "NETWORK_UNKNOWN"
        return receipt
    except (ValueError, TypeError, AttributeError):
        receipt["status"] = "RESPONSE_INVALID"
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Nebius Token Factory preflight (GET /models only)")
    parser.add_argument("--model", default=os.environ.get("NEBIUS_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL))
    args = parser.parse_args()
    key = os.environ.get("NEBIUS_API_KEY") or os.environ.get("NEBIUS_API_TOKEN") or ""
    receipt = probe(token=key, model=args.model, base_url=args.base_url)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "MODEL_AVAILABLE" else 2


if __name__ == "__main__":
    sys.exit(main())
