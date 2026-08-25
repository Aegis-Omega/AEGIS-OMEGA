"""AEGIS Ω — non-authoritative live ingestion into immutable registry snapshots."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

import cross_domain_collision as cdc
import research_invariants as ri


Transport = Callable[[str, float], bytes]


@dataclass(frozen=True)
class IngestionOutcomeV1:
    status: str
    snapshot: cdc.RegistrySnapshotV1 | None
    error_class: str | None = None
    error_message: str | None = None


def canonicalize_external_result(value: Any) -> Any:
    """Validate that a parsed external result is supported by canonical hashing."""
    ri.canonical_bytes(value)
    return value


def _default_transport(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def fetch_json_snapshot(
    *,
    registry_id: str,
    registry_version_or_release: str,
    query_key: str,
    query_key_type: str,
    result_kind: str,
    url: str,
    source_observed_at: str,
    producer_id: str,
    transport: Transport = _default_transport,
    timeout: float = 10.0,
) -> IngestionOutcomeV1:
    """
    Fetch external JSON and construct evidence only.

    This function never issues admission. Any transport, parse, or validation
    failure returns NOT_ESTABLISHED with no snapshot; absence of evidence is
    never converted into a negative registry fact.
    """
    try:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not url:
            raise ValueError("url must be non-empty")
        raw = transport(url, timeout)
        if not isinstance(raw, (bytes, bytearray)):
            raise TypeError("transport must return bytes")
        parsed = json.loads(bytes(raw).decode("utf-8"))
        canonical_result = canonicalize_external_result(parsed)
        snapshot = cdc.RegistrySnapshotV1(
            registry_id=registry_id,
            registry_version_or_release=registry_version_or_release,
            query_key=query_key,
            query_key_type=query_key_type,
            result_kind=result_kind,
            canonical_result=canonical_result,
            source_locator=url,
            source_observed_at=source_observed_at,
            ingestion_producer_id=producer_id,
        )
        return IngestionOutcomeV1(status="ESTABLISHED", snapshot=snapshot)
    except Exception as exc:
        return IngestionOutcomeV1(
            status="NOT_ESTABLISHED",
            snapshot=None,
            error_class=type(exc).__name__,
            error_message=str(exc),
        )
