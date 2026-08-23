#!/usr/bin/env python3
"""Fail-closed startup boundary for the AEGIS agent platform.

The platform contains model/cost-incurring routes. Starting that surface without
an authentication secret is a configuration failure, not an invitation to run
unauthenticated. This guard is intentionally stdlib-only so it executes before
application imports or network clients are initialized.
"""
from __future__ import annotations

import os

_MIN_PLATFORM_KEY_LENGTH = 32
_PLACEHOLDER_KEYS = {
    "changeme",
    "change-me",
    "password",
    "secret",
    "test",
    "dev",
    "development",
    "replace-me",
    "replace_me",
}


def require_platform_api_key(env: dict[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    key = source.get("PLATFORM_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "FATAL: PLATFORM_API_KEY is required; cost-incurring routes must not start unauthenticated"
        )
    if len(key) < _MIN_PLATFORM_KEY_LENGTH:
        raise SystemExit(
            f"FATAL: PLATFORM_API_KEY must be at least {_MIN_PLATFORM_KEY_LENGTH} characters"
        )
    if key.lower() in _PLACEHOLDER_KEYS:
        raise SystemExit("FATAL: PLATFORM_API_KEY must not be a placeholder value")
    return key


def validated_port(env: dict[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    raw = source.get("PORT", "8080").strip()
    try:
        port = int(raw, 10)
    except ValueError as exc:
        raise SystemExit("FATAL: PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("FATAL: PORT must be between 1 and 65535")
    return str(port)


def main() -> None:
    require_platform_api_key()
    port = validated_port()
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "secure_serve:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ],
    )


if __name__ == "__main__":
    main()
