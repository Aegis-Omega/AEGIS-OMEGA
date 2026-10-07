"""Read-only Circle CCTP sandbox attestation observer for Tameion.

This module adds an actual Circle API read surface without introducing any
wallet, signer, custody, broadcast, mainnet, or payment authority.

It is evidence-only: an attestation observation does not prove that a Circle
message belongs to a Tameion settlement unless some separate caller binds the
message hash or source transaction to that settlement.

CCTP v1 and v2 intentionally use separate read contracts. V1 observes
/v1/attestations/{messageHash}; v2 observes
/v2/messages/{sourceDomain}?transactionHash={burnTxHash}. Neither path signs,
mints, broadcasts, or grants AEGIS authority.
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
TRANSACTION_HASH_RE = re.compile(r"^0x[0-9a-f]{64}$")
HEX_BYTES_RE = re.compile(r"^0x(?:[0-9a-fA-F]{2})+$")
ATTESTATION_RE = HEX_BYTES_RE
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_V2_MESSAGES = 16


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


def _canonical_transaction_hash(value: str) -> str:
    if not isinstance(value, str):
        raise SovereignExecutionError("CIRCLE_TRANSACTION_HASH_INVALID")
    normalized = value.lower()
    if not TRANSACTION_HASH_RE.fullmatch(normalized):
        raise SovereignExecutionError("CIRCLE_TRANSACTION_HASH_INVALID")
    return normalized


def _source_domain(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
        raise SovereignExecutionError("CIRCLE_SOURCE_DOMAIN_INVALID")
    return value


def _hex_digest(value: str, code: str) -> tuple[str, int]:
    if not isinstance(value, str) or not HEX_BYTES_RE.fullmatch(value):
        raise SovereignExecutionError(code)
    raw = bytes.fromhex(value[2:])
    return hashlib.sha256(raw).hexdigest(), len(raw)


@dataclass(frozen=True)
class CircleV2MessagesRequest:
    schema_version: str
    source_domain: int
    transaction_hash: str
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
            raise SovereignExecutionError("CIRCLE_V2_SCHEMA_UNSUPPORTED")
        domain = _source_domain(self.source_domain)
        tx_hash = _canonical_transaction_hash(self.transaction_hash)
        if self.transaction_hash != tx_hash:
            raise SovereignExecutionError("CIRCLE_V2_TRANSACTION_HASH_NOT_CANONICAL")
        expected = (
            f"{CIRCLE_CCTP_SANDBOX_BASE}/v2/messages/{domain}"
            f"?transactionHash={tx_hash}"
        )
        if self.endpoint != expected:
            raise SovereignExecutionError("CIRCLE_V2_ENDPOINT_INVALID")
        parts = urlsplit(self.endpoint)
        if (
            parts.scheme != "https"
            or parts.hostname != CIRCLE_CCTP_SANDBOX_HOST
            or parts.username is not None
            or parts.password is not None
            or parts.port is not None
            or parts.fragment
        ):
            raise SovereignExecutionError("CIRCLE_V2_ENDPOINT_INVALID")
        if self.method != "GET":
            raise SovereignExecutionError("CIRCLE_V2_METHOD_NOT_READ_ONLY")
        if self.environment != "SANDBOX":
            raise SovereignExecutionError("CIRCLE_V2_SANDBOX_ONLY")
        if self.network_effect != "READ_ONLY":
            raise SovereignExecutionError("CIRCLE_V2_NETWORK_EFFECT_INVALID")
        if self.signer_attached:
            raise SovereignExecutionError("CIRCLE_V2_SIGNER_FORBIDDEN")
        if self.broadcast_allowed:
            raise SovereignExecutionError("CIRCLE_V2_BROADCAST_FORBIDDEN")
        if self.custody_effect != "NONE":
            raise SovereignExecutionError("CIRCLE_V2_CUSTODY_FORBIDDEN")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("CIRCLE_V2_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_CIRCLE_V2_MESSAGES_REQUEST_V1", asdict(self))


@dataclass(frozen=True)
class CircleV2MessagesObservation:
    schema_version: str
    request_root: str
    source_domain: int
    transaction_hash: str
    endpoint: str
    statuses: tuple[str, ...]
    message_sha256: tuple[str | None, ...]
    attestation_sha256: tuple[str | None, ...]
    message_bytes: tuple[int | None, ...]
    attestation_bytes: tuple[int | None, ...]
    network_effect: str = "READ_ONLY"
    signer_attached: bool = False
    broadcast_allowed: bool = False
    custody_effect: str = "NONE"
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("CIRCLE_V2_OBSERVATION_SCHEMA_UNSUPPORTED")
        _assert_sha256("request_root", self.request_root)
        domain = _source_domain(self.source_domain)
        tx_hash = _canonical_transaction_hash(self.transaction_hash)
        expected = (
            f"{CIRCLE_CCTP_SANDBOX_BASE}/v2/messages/{domain}"
            f"?transactionHash={tx_hash}"
        )
        if self.endpoint != expected:
            raise SovereignExecutionError("CIRCLE_V2_OBSERVATION_ENDPOINT_INVALID")
        count = len(self.statuses)
        if not 1 <= count <= MAX_V2_MESSAGES:
            raise SovereignExecutionError("CIRCLE_V2_MESSAGE_COUNT_INVALID")
        if not all(len(values) == count for values in (
            self.message_sha256,
            self.attestation_sha256,
            self.message_bytes,
            self.attestation_bytes,
        )):
            raise SovereignExecutionError("CIRCLE_V2_OBSERVATION_LENGTH_MISMATCH")
        for index, status in enumerate(self.statuses):
            if status not in ("complete", "pending_confirmations"):
                raise SovereignExecutionError("CIRCLE_V2_STATUS_INVALID")
            message_digest = self.message_sha256[index]
            attestation_digest = self.attestation_sha256[index]
            message_length = self.message_bytes[index]
            attestation_length = self.attestation_bytes[index]
            if message_digest is not None:
                _assert_sha256("message_sha256", message_digest)
                if not isinstance(message_length, int) or isinstance(message_length, bool) or message_length <= 0:
                    raise SovereignExecutionError("CIRCLE_V2_MESSAGE_LENGTH_INVALID")
            elif message_length is not None:
                raise SovereignExecutionError("CIRCLE_V2_MESSAGE_LENGTH_WITHOUT_DIGEST")
            if status == "complete":
                if message_digest is None or attestation_digest is None:
                    raise SovereignExecutionError("CIRCLE_V2_COMPLETE_EVIDENCE_MISSING")
                _assert_sha256("attestation_sha256", attestation_digest)
                if not isinstance(attestation_length, int) or isinstance(attestation_length, bool) or attestation_length <= 0:
                    raise SovereignExecutionError("CIRCLE_V2_ATTESTATION_LENGTH_INVALID")
            elif attestation_digest is not None or attestation_length is not None:
                raise SovereignExecutionError("CIRCLE_V2_PENDING_ATTESTATION_FORBIDDEN")
        if self.network_effect != "READ_ONLY":
            raise SovereignExecutionError("CIRCLE_V2_OBSERVATION_NETWORK_EFFECT_INVALID")
        if self.signer_attached:
            raise SovereignExecutionError("CIRCLE_V2_OBSERVATION_SIGNER_FORBIDDEN")
        if self.broadcast_allowed:
            raise SovereignExecutionError("CIRCLE_V2_OBSERVATION_BROADCAST_FORBIDDEN")
        if self.custody_effect != "NONE":
            raise SovereignExecutionError("CIRCLE_V2_OBSERVATION_CUSTODY_FORBIDDEN")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("CIRCLE_V2_OBSERVATION_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_CIRCLE_V2_MESSAGES_OBSERVATION_V1", asdict(self))


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


def build_circle_v2_messages_request(
    source_domain: int,
    transaction_hash: str,
) -> CircleV2MessagesRequest:
    domain = _source_domain(source_domain)
    tx_hash = _canonical_transaction_hash(transaction_hash)
    request = CircleV2MessagesRequest(
        schema_version=SCHEMA_VERSION,
        source_domain=domain,
        transaction_hash=tx_hash,
        endpoint=(
            f"{CIRCLE_CCTP_SANDBOX_BASE}/v2/messages/{domain}"
            f"?transactionHash={tx_hash}"
        ),
    )
    request.validate()
    return request


def parse_circle_v2_messages_response(
    request: CircleV2MessagesRequest,
    payload: Mapping[str, Any],
) -> CircleV2MessagesObservation:
    request.validate()
    if not isinstance(payload, Mapping):
        raise SovereignExecutionError("CIRCLE_V2_RESPONSE_INVALID")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_V2_MESSAGES:
        raise SovereignExecutionError("CIRCLE_V2_MESSAGE_COUNT_INVALID")

    statuses: list[str] = []
    message_digests: list[str | None] = []
    attestation_digests: list[str | None] = []
    message_lengths: list[int | None] = []
    attestation_lengths: list[int | None] = []

    for item in messages:
        if not isinstance(item, Mapping):
            raise SovereignExecutionError("CIRCLE_V2_MESSAGE_INVALID")
        status = item.get("status")
        if status not in ("complete", "pending_confirmations"):
            raise SovereignExecutionError("CIRCLE_V2_STATUS_INVALID")
        statuses.append(status)

        message = item.get("message")
        if message is None:
            message_digests.append(None)
            message_lengths.append(None)
        else:
            digest, length = _hex_digest(message, "CIRCLE_V2_MESSAGE_BYTES_INVALID")
            message_digests.append(digest)
            message_lengths.append(length)

        attestation = item.get("attestation")
        if status == "complete":
            digest, length = _hex_digest(attestation, "CIRCLE_V2_ATTESTATION_BYTES_INVALID")
            attestation_digests.append(digest)
            attestation_lengths.append(length)
        else:
            if attestation not in (None, "PENDING"):
                raise SovereignExecutionError("CIRCLE_V2_PENDING_ATTESTATION_INVALID")
            attestation_digests.append(None)
            attestation_lengths.append(None)

    observation = CircleV2MessagesObservation(
        schema_version=SCHEMA_VERSION,
        request_root=request.root,
        source_domain=request.source_domain,
        transaction_hash=request.transaction_hash,
        endpoint=request.endpoint,
        statuses=tuple(statuses),
        message_sha256=tuple(message_digests),
        attestation_sha256=tuple(attestation_digests),
        message_bytes=tuple(message_lengths),
        attestation_bytes=tuple(attestation_lengths),
    )
    observation.validate()
    return observation


def fetch_circle_v2_messages(
    source_domain: int,
    transaction_hash: str,
    *,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 5.0,
) -> tuple[CircleV2MessagesRequest, CircleV2MessagesObservation]:
    """Perform exactly one unauthenticated GET against Circle's CCTP v2 sandbox API."""

    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0 or timeout > 30:
        raise SovereignExecutionError("CIRCLE_V2_TIMEOUT_INVALID")
    evidence = build_circle_v2_messages_request(source_domain, transaction_hash)
    http_request = Request(
        evidence.endpoint,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "AEGIS-Tameion-Circle-V2-Observer/1",
        },
    )
    try:
        with opener(http_request, timeout=float(timeout)) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise SovereignExecutionError("CIRCLE_V2_READ_FAILED") from exc
    if not isinstance(body, (bytes, bytearray)) or len(body) > MAX_RESPONSE_BYTES:
        raise SovereignExecutionError("CIRCLE_V2_RESPONSE_OVERSIZED")
    try:
        payload = json.loads(bytes(body).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SovereignExecutionError("CIRCLE_V2_RESPONSE_INVALID") from exc
    if not isinstance(payload, Mapping):
        raise SovereignExecutionError("CIRCLE_V2_RESPONSE_INVALID")
    return evidence, parse_circle_v2_messages_response(evidence, payload)


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
