"""AEGIS Ω Google Cloud KMS Ed25519 envelope-signing source contract v1.

This module is intentionally transport-injected and does not provision keys,
credentials, IAM, or network authority. It binds an existing Phase-1
ExecutionEnvelope hash to an explicitly supplied verified client principal.

Google Cloud KMS EC_SIGN_ED25519 is PureEdDSA and signs raw data. Accordingly
this module sends the domain-separated canonical statement through the REST
`data` field, never the digest field.

Live KMS use remains a separate evidence step.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Mapping

try:
    from .canonical_envelope import canon
except ImportError:  # pragma: no cover - direct module execution/import
    from canonical_envelope import canon

SCHEMA_VERSION = "1.0.0"
SIGNATURE_DOMAIN = "AEGIS_EXECUTION_ENVELOPE_SIGNATURE_V1"
SIGNATURE_SCHEME = "GCP_KMS_EC_SIGN_ED25519_V1"
ALGORITHM = "EC_SIGN_ED25519"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
KEY_VERSION_RE = re.compile(
    r"^projects/[^/]+/locations/[^/]+/keyRings/[^/]+/"
    r"cryptoKeys/[^/]+/cryptoKeyVersions/[1-9][0-9]*$"
)
BODY_FIELDS = (
    "canon_version",
    "seq",
    "prev_hash",
    "request_digest",
    "response_digest",
    "model_id",
    "epistemic_tier",
    "provider",
)
ENVELOPE_FIELDS = frozenset((*BODY_FIELDS, "envelope_hash", "signature"))

KmsTransport = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


class EnvelopeSigningError(ValueError):
    pass


def _safe_identity_string(name: str, value: Any, *, max_bytes: int = 512) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise EnvelopeSigningError(f"{name}:INVALID_STRING")
    if unicodedata.normalize("NFC", value) != value:
        raise EnvelopeSigningError(f"{name}:NON_CANONICAL_UNICODE")
    if any(unicodedata.category(ch).startswith("C") for ch in value):
        raise EnvelopeSigningError(f"{name}:CONTROL_CHARACTER")
    if len(value.encode("utf-8")) > max_bytes:
        raise EnvelopeSigningError(f"{name}:TOO_LONG")
    return value


def _sha256(name: str, value: Any) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise EnvelopeSigningError(f"{name}:INVALID_SHA256")
    return value


@dataclass(frozen=True)
class ClientPrincipal:
    """Trusted caller identity supplied by the authentication boundary."""

    kind: str
    issuer: str
    subject: str

    def validate(self) -> None:
        _safe_identity_string("client_principal.kind", self.kind, max_bytes=64)
        _safe_identity_string("client_principal.issuer", self.issuer)
        _safe_identity_string("client_principal.subject", self.subject)

    def as_dict(self) -> dict[str, str]:
        self.validate()
        return {
            "issuer": self.issuer,
            "kind": self.kind,
            "subject": self.subject,
        }


def crc32c(data: bytes) -> int:
    """CRC-32C / Castagnoli, dependency-free.

    Known vector: crc32c(b"123456789") == 0xe3069283.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("crc32c requires bytes")
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def signature_statement(
    envelope_hash: str,
    client_principal: ClientPrincipal,
) -> dict[str, Any]:
    _sha256("envelope_hash", envelope_hash)
    return {
        "client_principal": client_principal.as_dict(),
        "domain": SIGNATURE_DOMAIN,
        "envelope_hash": envelope_hash,
        "schema_version": SCHEMA_VERSION,
    }


def signature_statement_bytes(
    envelope_hash: str,
    client_principal: ClientPrincipal,
) -> bytes:
    return canon(signature_statement(envelope_hash, client_principal))


def asymmetric_sign_endpoint(key_version_name: str) -> str:
    if not isinstance(key_version_name, str) or KEY_VERSION_RE.fullmatch(key_version_name) is None:
        raise EnvelopeSigningError("KMS_KEY_VERSION_NAME_INVALID")
    return f"https://cloudkms.googleapis.com/v1/{key_version_name}:asymmetricSign"


def _parse_crc32c(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise EnvelopeSigningError(f"{name}:INVALID")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value, 10)
    else:
        raise EnvelopeSigningError(f"{name}:INVALID")
    if parsed < 0 or parsed > 0xFFFFFFFF:
        raise EnvelopeSigningError(f"{name}:OUT_OF_RANGE")
    return parsed


def _validate_phase1_envelope(envelope: Mapping[str, Any]) -> str:
    if not isinstance(envelope, Mapping):
        raise EnvelopeSigningError("ENVELOPE_MUST_BE_OBJECT")
    if frozenset(envelope) != ENVELOPE_FIELDS:
        raise EnvelopeSigningError("ENVELOPE_FIELD_SET_MISMATCH")
    if envelope.get("signature") is not None:
        raise EnvelopeSigningError("ENVELOPE_ALREADY_SIGNED")
    if envelope.get("canon_version") != "JCS-1":
        raise EnvelopeSigningError("CANON_VERSION_UNSUPPORTED")
    seq = envelope.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise EnvelopeSigningError("SEQUENCE_INVALID")
    for field in ("prev_hash", "request_digest", "response_digest", "envelope_hash"):
        _sha256(field, envelope.get(field))
    for field in ("model_id", "epistemic_tier", "provider"):
        _safe_identity_string(field, envelope.get(field))
    body = {key: envelope[key] for key in BODY_FIELDS}
    recomputed = hashlib.sha256(canon(body)).hexdigest()
    if recomputed != envelope["envelope_hash"]:
        raise EnvelopeSigningError("ENVELOPE_HASH_MISMATCH")
    return envelope["envelope_hash"]


class GoogleCloudKmsEd25519Signer:
    """Fail-closed EC_SIGN_ED25519 source contract.

    `transport` receives (endpoint, JSON request body) and must return the
    decoded JSON response from Cloud KMS asymmetricSign.
    """

    def __init__(
        self,
        *,
        key_version_name: str,
        transport: KmsTransport,
        algorithm: str = ALGORITHM,
    ) -> None:
        self.key_version_name = key_version_name
        self.endpoint = asymmetric_sign_endpoint(key_version_name)
        if algorithm != ALGORITHM:
            raise EnvelopeSigningError("KMS_ALGORITHM_UNSUPPORTED")
        if not callable(transport):
            raise EnvelopeSigningError("KMS_TRANSPORT_INVALID")
        self.algorithm = algorithm
        self._transport = transport

    def sign(
        self,
        envelope_hash: str,
        client_principal: ClientPrincipal,
    ) -> dict[str, Any]:
        statement = signature_statement_bytes(envelope_hash, client_principal)
        statement_crc32c = crc32c(statement)
        request = {
            "data": base64.b64encode(statement).decode("ascii"),
            "dataCrc32c": str(statement_crc32c),
        }

        try:
            response = self._transport(self.endpoint, copy.deepcopy(request))
        except EnvelopeSigningError:
            raise
        except Exception as exc:
            # No hidden retry: callers decide whether a provider transport error
            # is safe to retry under their own idempotency/operation policy.
            raise EnvelopeSigningError("KMS_SIGN_UNAVAILABLE") from exc

        if not isinstance(response, Mapping):
            raise EnvelopeSigningError("KMS_RESPONSE_INVALID")
        if response.get("name") != self.key_version_name:
            raise EnvelopeSigningError("KMS_KEY_VERSION_MISMATCH")
        if response.get("verifiedDataCrc32c") is not True:
            raise EnvelopeSigningError("KMS_DATA_CRC32C_NOT_VERIFIED")

        encoded_signature = response.get("signature")
        if not isinstance(encoded_signature, str) or not encoded_signature:
            raise EnvelopeSigningError("KMS_SIGNATURE_MISSING")
        try:
            signature = base64.b64decode(encoded_signature, validate=True)
        except Exception as exc:
            raise EnvelopeSigningError("KMS_SIGNATURE_BASE64_INVALID") from exc
        if len(signature) != 64:
            raise EnvelopeSigningError("KMS_ED25519_SIGNATURE_LENGTH_INVALID")

        returned_crc32c = _parse_crc32c(
            "signatureCrc32c", response.get("signatureCrc32c")
        )
        computed_signature_crc32c = crc32c(signature)
        if returned_crc32c != computed_signature_crc32c:
            raise EnvelopeSigningError("KMS_SIGNATURE_CRC32C_MISMATCH")

        protection_level = response.get("protectionLevel")
        if not isinstance(protection_level, str) or not protection_level:
            raise EnvelopeSigningError("KMS_PROTECTION_LEVEL_MISSING")

        principal = client_principal.as_dict()
        return {
            "algorithm": self.algorithm,
            "client_principal": principal,
            "key_version": self.key_version_name,
            "protection_level": protection_level,
            "scheme": SIGNATURE_SCHEME,
            "schema_version": SCHEMA_VERSION,
            "signature_b64": encoded_signature,
            "signature_crc32c": returned_crc32c,
            "statement_crc32c": statement_crc32c,
            "statement_sha256": hashlib.sha256(statement).hexdigest(),
            "verified_data_crc32c": True,
        }


def attach_kms_signature(
    envelope: Mapping[str, Any],
    *,
    client_principal: ClientPrincipal,
    signer: GoogleCloudKmsEd25519Signer,
) -> dict[str, Any]:
    """Return a signed copy; never mutates the input envelope."""
    envelope_hash = _validate_phase1_envelope(envelope)
    record = signer.sign(envelope_hash, client_principal)
    signed = copy.deepcopy(dict(envelope))
    signed["signature"] = record
    return signed
