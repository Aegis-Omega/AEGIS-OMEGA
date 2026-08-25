"""AEGIS Ω — non-authoritative live ingestion and immutable source capture.

Network acquisition produces evidence only.  Offline modules decide whether
captured evidence establishes a registry result.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

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
    """Fetch external JSON as non-authoritative immutable snapshot evidence."""
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


@dataclass(frozen=True)
class SourceCaptureReceiptV1:
    source_id: str
    source_contract_sha256: str
    request_identity: str
    request_subject_sha256s: tuple[str, ...]
    source_version_or_release: str
    response_status: int
    media_type: str
    raw_content_sha256: str
    raw_content_length: int
    observed_at: str
    producer_id: str
    attempt_index: int
    previous_attempt_sha256: str | None
    receipt_sha256: str


def _capture_receipt_material(receipt: SourceCaptureReceiptV1) -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_SOURCE_CAPTURE_RECEIPT_V1",
        "source_id": receipt.source_id,
        "source_contract_sha256": receipt.source_contract_sha256,
        "request_identity": receipt.request_identity,
        "request_subject_sha256s": receipt.request_subject_sha256s,
        "source_version_or_release": receipt.source_version_or_release,
        "response_status": receipt.response_status,
        "media_type": receipt.media_type,
        "raw_content_sha256": receipt.raw_content_sha256,
        "raw_content_length": receipt.raw_content_length,
        "observed_at": receipt.observed_at,
        "producer_id": receipt.producer_id,
        "attempt_index": receipt.attempt_index,
        "previous_attempt_sha256": receipt.previous_attempt_sha256,
    }


def verify_source_capture_receipt(receipt: SourceCaptureReceiptV1) -> None:
    if not isinstance(receipt, SourceCaptureReceiptV1):
        raise TypeError("expected SourceCaptureReceiptV1")
    for name, value in (
        ("source_id", receipt.source_id),
        ("request_identity", receipt.request_identity),
        ("source_version_or_release", receipt.source_version_or_release),
        ("media_type", receipt.media_type),
        ("observed_at", receipt.observed_at),
        ("producer_id", receipt.producer_id),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")
    ri._check_digest(receipt.source_contract_sha256, "source_contract_sha256")
    ri._check_digest(receipt.raw_content_sha256, "raw_content_sha256")
    ri._check_digest(receipt.receipt_sha256, "receipt_sha256")
    subjects = tuple(receipt.request_subject_sha256s)
    for digest in subjects:
        ri._check_digest(digest, "request_subject_sha256")
    if isinstance(receipt.response_status, bool) or not isinstance(receipt.response_status, int):
        raise TypeError("response_status must be an integer")
    if not 100 <= receipt.response_status <= 599:
        raise ValueError("response_status outside HTTP status range")
    if isinstance(receipt.raw_content_length, bool) or not isinstance(receipt.raw_content_length, int):
        raise TypeError("raw_content_length must be an integer")
    if receipt.raw_content_length < 0:
        raise ValueError("raw_content_length must be non-negative")
    if isinstance(receipt.attempt_index, bool) or not isinstance(receipt.attempt_index, int):
        raise TypeError("attempt_index must be an integer")
    if receipt.attempt_index < 0:
        raise ValueError("attempt_index must be non-negative")
    if receipt.attempt_index == 0:
        if receipt.previous_attempt_sha256 is not None:
            raise ValueError("initial source capture cannot bind a previous attempt")
    else:
        if receipt.previous_attempt_sha256 is None:
            raise ValueError("retry source capture requires previous attempt digest")
        ri._check_digest(receipt.previous_attempt_sha256, "previous_attempt_sha256")
    if ri.sha256_hex(_capture_receipt_material(receipt)) != receipt.receipt_sha256:
        raise ValueError("source capture receipt digest mismatch")


@dataclass(frozen=True)
class VerifiedSourceCaptureV1:
    receipt: SourceCaptureReceiptV1
    raw_content: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.raw_content, (bytes, bytearray)):
            raise TypeError("raw_content must be bytes")
        object.__setattr__(self, "raw_content", bytes(self.raw_content))


def _raw_sha256(raw_content: bytes) -> str:
    return hashlib.sha256(raw_content).hexdigest()


def capture_source_bytes(
    *,
    source_id: str,
    source_contract_sha256: str,
    request_identity: str,
    request_subject_sha256s: Sequence[str],
    source_version_or_release: str,
    response_status: int,
    media_type: str,
    raw_content: bytes,
    observed_at: str,
    producer_id: str,
    attempt_index: int,
    previous_attempt_sha256: str | None = None,
) -> VerifiedSourceCaptureV1:
    if not isinstance(raw_content, (bytes, bytearray)):
        raise TypeError("raw_content must be bytes")
    raw = bytes(raw_content)
    subjects = tuple(request_subject_sha256s)
    raw_sha = _raw_sha256(raw)
    provisional = SourceCaptureReceiptV1(
        source_id=source_id,
        source_contract_sha256=source_contract_sha256,
        request_identity=request_identity,
        request_subject_sha256s=subjects,
        source_version_or_release=source_version_or_release,
        response_status=response_status,
        media_type=media_type,
        raw_content_sha256=raw_sha,
        raw_content_length=len(raw),
        observed_at=observed_at,
        producer_id=producer_id,
        attempt_index=attempt_index,
        previous_attempt_sha256=previous_attempt_sha256,
        receipt_sha256="0" * 64,
    )
    # Validate all semantic fields before minting the final digest.  The
    # provisional digest placeholder is syntactically valid by construction.
    verify_source_capture_receipt(
        SourceCaptureReceiptV1(
            source_id=provisional.source_id,
            source_contract_sha256=provisional.source_contract_sha256,
            request_identity=provisional.request_identity,
            request_subject_sha256s=provisional.request_subject_sha256s,
            source_version_or_release=provisional.source_version_or_release,
            response_status=provisional.response_status,
            media_type=provisional.media_type,
            raw_content_sha256=provisional.raw_content_sha256,
            raw_content_length=provisional.raw_content_length,
            observed_at=provisional.observed_at,
            producer_id=provisional.producer_id,
            attempt_index=provisional.attempt_index,
            previous_attempt_sha256=provisional.previous_attempt_sha256,
            receipt_sha256=ri.sha256_hex(_capture_receipt_material(provisional)),
        )
    )
    receipt = SourceCaptureReceiptV1(
        source_id=provisional.source_id,
        source_contract_sha256=provisional.source_contract_sha256,
        request_identity=provisional.request_identity,
        request_subject_sha256s=provisional.request_subject_sha256s,
        source_version_or_release=provisional.source_version_or_release,
        response_status=provisional.response_status,
        media_type=provisional.media_type,
        raw_content_sha256=provisional.raw_content_sha256,
        raw_content_length=provisional.raw_content_length,
        observed_at=provisional.observed_at,
        producer_id=provisional.producer_id,
        attempt_index=provisional.attempt_index,
        previous_attempt_sha256=provisional.previous_attempt_sha256,
        receipt_sha256=ri.sha256_hex(_capture_receipt_material(provisional)),
    )
    bundle = VerifiedSourceCaptureV1(receipt=receipt, raw_content=raw)
    verify_source_capture(bundle)
    return bundle


def verify_source_capture(bundle: VerifiedSourceCaptureV1) -> None:
    if not isinstance(bundle, VerifiedSourceCaptureV1):
        raise TypeError("expected VerifiedSourceCaptureV1")
    verify_source_capture_receipt(bundle.receipt)
    if _raw_sha256(bundle.raw_content) != bundle.receipt.raw_content_sha256:
        raise ValueError("source capture raw-content digest mismatch")
    if len(bundle.raw_content) != bundle.receipt.raw_content_length:
        raise ValueError("source capture raw-content length mismatch")
