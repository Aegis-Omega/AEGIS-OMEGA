"""Read-only Circle CCTP sandbox attestation observer for Tameion.

This module adds an actual Circle API read surface without introducing any
wallet, signer, custody, broadcast, mainnet, or payment authority.

It is evidence-only: an attestation observation does not prove that a Circle
message belongs to a Tameion settlement unless some separate caller binds the
message hash to that settlement.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    SovereignExecutionError,
    canonical_hash,
)

CIRCLE_CCTP_SANDBOX_BASE = "https://iris-api-sandbox.circle.com"
CIRCLE_CCTP_SANDBOX_HOST = "iris-api-sandbox.circle.com"
MAX_RESPONSE_BYTES = 65_536
MESSAGE_HASH_RE = re.compile(r"^0x[0-9a-f]{64}$")
ATTESTATION_RE = re.compile(r"^0x(?:[0-9a-fA-F]{2})+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_message_hash(value: str) -> str:
    if not isinstance(value, str):
        raise SovereignExecutionError("CIRCLE_MESSAGE_HASH_INVALID")
    normalized = value.lower()
    if not MESSAGE_HASH_RE.fullmatch(normalized):
        raise SovereignExecutionError("CIRCLE_MESSAGE_HASH_INVALID")
    return normalized


def _assert_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:INVALID_SHA256")


@dataclass(frozen=True)
class CircleAttestationRequest:
    schema_version: str
    message_hash: str
    endpoint: str
    method: str = "GET"
    environment: str = "SANDBOX"
    network_effect: str = "READ_ONLY"
    signer_attached: bool = False
    broadcast_allowed: bool = False
    custody_effect: str = "NONE"
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("CIRCLE_ATTESTATION_SCHEMA_UNSUPPORTED")
        message_hash = _canonical_message_hash(self.message_hash)
        if self.message_hash != message_hash:
            raise SovereignExecutionError("CIRCLE_MESSAGE_HASH_NOT_CANONICAL")
        expected = f"{CIRCLE_CCTP_SANDBOX_BASE}/v1/attestations/{message_hash}"
        if self.endpoint != expected:
            raise SovereignExecutionError("CIRCLE_ATTESTATION_ENDPOINT_INVALID")
        parts = urlsplit(self.endpoint)
        if (
            parts.scheme != "https"
            or parts.hostname != CIRCLE_CCTP_SANDBOX_HOST
            or parts.username is not None
            or parts.password is not None
            or parts.port is not None
            or parts.query
            or parts.fragment
        ):
            raise SovereignExecutionError("CIRCLE_ATTESTATION_ENDPOINT_INVALID")
        if self.method != "GET":
            raise SovereignExecutionError("CIRCLE_ATTESTATION_METHOD_NOT_READ_ONLY")
        if self.environment != "SANDBOX":
            raise SovereignExecutionError("CIRCLE_ATTESTATION_SANDBOX_ONLY")
        if self.network_effect != "READ_ONLY":
            raise SovereignExecutionError("CIRCLE_ATTESTATION_NETWORK_EFFECT_INVALID")
        if self.signer_attached:
            raise SovereignExecutionError("CIRCLE_ATTESTATION_SIGNER_FORBIDDEN")
        if self.broadcast_allowed:
            raise SovereignExecutionError("CIRCLE_ATTESTATION_BROADCAST_FORBIDDEN")
        if self.custody_effect != "NONE":
            raise SovereignExecutionError("CIRCLE_ATTESTATION_CUSTODY_FORBIDDEN")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("CIRCLE_ATTESTATION_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_CIRCLE_ATTESTATION_REQUEST_V1", asdict(self))


@dataclass(frozen=True)
class CircleAttestationObservation:
    schema_version: str
    request_root: str
    message_hash: str
    endpoint: str
    status: str
    attestation_sha256: str | None
    network_effect: str = "READ_ONLY"
    signer_attached: bool = False
    broadcast_allowed: bool = False
    custody_effect: str = "NONE"
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("CIRCLE_OBSERVATION_SCHEMA_UNSUPPORTED")
        _assert_sha256("request_root", self.request_root)
        message_hash = _canonical_message_hash(self.message_hash)
        expected = f"{CIRCLE_CCTP_SANDBOX_BASE}/v1/attestations/{message_hash}"
        if self.endpoint != expected:
            raise SovereignExecutionError("CIRCLE_OBSERVATION_ENDPOINT_INVALID")
        if self.status not in ("complete", "pending_confirmations"):
            raise SovereignExecutionError("CIRCLE_ATTESTATION_STATUS_INVALID")
        if self.status == "complete":
            if self.attestation_sha256 is None:
                raise SovereignExecutionError("CIRCLE_ATTESTATION_DIGEST_MISSING")
            _assert_sha256("attestation_sha256", self.attestation_sha256)
        elif self.attestation_sha256 is not None:
            raise SovereignExecutionError("CIRCLE_PENDING_ATTESTATION_MUST_NOT_HAVE_DIGEST")
        if self.network_effect != "READ_ONLY":
            raise SovereignExecutionError("CIRCLE_OBSERVATION_NETWORK_EFFECT_INVALID")
        if self.signer_attached:
            raise SovereignExecutionError("CIRCLE_OBSERVATION_SIGNER_FORBIDDEN")
        if self.broadcast_allowed:
            raise SovereignExecutionError("CIRCLE_OBSERVATION_BROADCAST_FORBIDDEN")
        if self.custody_effect != "NONE":
            raise SovereignExecutionError("CIRCLE_OBSERVATION_CUSTODY_FORBIDDEN")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("CIRCLE_OBSERVATION_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_CIRCLE_ATTESTATION_OBSERVATION_V1", asdict(self))


def build_circle_attestation_request(message_hash: str) -> CircleAttestationRequest:
    canonical = _canonical_message_hash(message_hash)
    request = CircleAttestationRequest(
        schema_version=SCHEMA_VERSION,
        message_hash=canonical,
        endpoint=f"{CIRCLE_CCTP_SANDBOX_BASE}/v1/attestations/{canonical}",
    )
    request.validate()
    return request


def parse_circle_attestation_response(
    request: CircleAttestationRequest,
    payload: Mapping[str, Any],
) -> CircleAttestationObservation:
    request.validate()
    if not isinstance(payload, Mapping):
        raise SovereignExecutionError("CIRCLE_ATTESTATION_RESPONSE_INVALID")

    status = payload.get("status")
    if status not in ("complete", "pending_confirmations"):
        raise SovereignExecutionError("CIRCLE_ATTESTATION_STATUS_INVALID")

    attestation_sha256: str | None = None
    if status == "complete":
        attestation = payload.get("attestation")
        if not isinstance(attestation, str) or not ATTESTATION_RE.fullmatch(attestation):
            raise SovereignExecutionError("CIRCLE_ATTESTATION_BYTES_INVALID")
        raw = bytes.fromhex(attestation[2:])
        attestation_sha256 = hashlib.sha256(raw).hexdigest()
    else:
        attestation = payload.get("attestation")
        if attestation not in (None, "PENDING"):
            raise SovereignExecutionError("CIRCLE_PENDING_ATTESTATION_INVALID")

    observation = CircleAttestationObservation(
        schema_version=SCHEMA_VERSION,
        request_root=request.root,
        message_hash=request.message_hash,
        endpoint=request.endpoint,
        status=status,
        attestation_sha256=attestation_sha256,
    )
    observation.validate()
    return observation


def fetch_circle_attestation(
    message_hash: str,
    *,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 5.0,
) -> tuple[CircleAttestationRequest, CircleAttestationObservation]:
    """Perform exactly one unauthenticated GET against Circle's sandbox API."""

    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0 or timeout > 30:
        raise SovereignExecutionError("CIRCLE_ATTESTATION_TIMEOUT_INVALID")

    evidence = build_circle_attestation_request(message_hash)
    http_request = Request(
        evidence.endpoint,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "AEGIS-Tameion-Circle-Observer/1",
        },
    )

    try:
        with opener(http_request, timeout=float(timeout)) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise SovereignExecutionError("CIRCLE_ATTESTATION_READ_FAILED") from exc

    if not isinstance(body, (bytes, bytearray)) or len(body) > MAX_RESPONSE_BYTES:
        raise SovereignExecutionError("CIRCLE_ATTESTATION_RESPONSE_OVERSIZED")
    try:
        payload = json.loads(bytes(body).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SovereignExecutionError("CIRCLE_ATTESTATION_RESPONSE_INVALID") from exc
    if not isinstance(payload, Mapping):
        raise SovereignExecutionError("CIRCLE_ATTESTATION_RESPONSE_INVALID")
    return evidence, parse_circle_attestation_response(evidence, payload)
