#!/usr/bin/env python3
"""Deterministic primitives for AEGIS cognitive recovery admission.

This module is intentionally non-mutating. In this slice it provides only
canonical serialization and content-addressed request identity. It grants no
repository, cloud, deployment, billing, or mathematical authority.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

REQUEST_DOMAIN = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_REQUEST_V1"
RECEIPT_DOMAIN = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1"


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes and reject non-finite numbers."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return lowercase hexadecimal SHA-256 for exact bytes."""
    return hashlib.sha256(data).hexdigest()


def request_digest(request: dict[str, Any]) -> str:
    """Hash a recovery request while excluding only its self-referential id."""
    body = {key: value for key, value in request.items() if key != "request_id"}
    envelope = {"domain": REQUEST_DOMAIN, "request": body}
    return sha256_hex(canonical_bytes(envelope))
