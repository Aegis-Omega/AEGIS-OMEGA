"""Cross-runtime authoritative receipt provenance.

This module implements the Python half of the T2 -> T3 receipt boundary.  Its
wire contracts are the repository schemas
``cross-runtime-receipt-envelope.v1.schema.json`` and
``receipt-trust-registry.v1.schema.json``.  All integrity bytes are produced by
``canonical_envelope.canon``; no alternate serializer is used.

Time is an explicit, caller-supplied observation represented as a canonical
decimal string.  The module never reads a wall clock.
"""
from __future__ import annotations

import copy
import json
import math
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:  # Direct test execution places this directory on sys.path.
    from .canonical_envelope import canon, sha256_hex
except ImportError:  # pragma: no cover - exercised by direct script execution
    from canonical_envelope import canon, sha256_hex


SCHEMA_VERSION = "1.0.0"
ZERO_HASH = "0" * 64
ED25519 = "Ed25519"

RECEIPT_SIGNATURE_DOMAIN = "AEGIS_CROSS_RUNTIME_RECEIPT_SIGNATURE_V1"
RECEIPT_ID_DOMAIN = "AEGIS_CROSS_RUNTIME_RECEIPT_ID_V1"
REGISTRY_SIGNATURE_DOMAIN = "AEGIS_RECEIPT_TRUST_REGISTRY_SIGNATURE_V1"
REGISTRY_ROOT_DOMAIN = "AEGIS_RECEIPT_TRUST_REGISTRY_ROOT_V1"

RECEIPT_KINDS = (
    "LEASE_ISSUED",
    "LEASE_ISSUANCE_DENIED",
    "LEASE_RENEWED",
    "LEASE_RENEWAL_DENIED",
    "LEASE_EXPIRED",
    "LEASE_REVOKED",
    "MUTATION_ADMITTED",
    "MUTATION_DENIED",
    "MUTATION_COMPLETED",
    "MUTATION_CANCELLED",
    "MUTATION_FAILED",
)
LEASE_KINDS = frozenset(kind for kind in RECEIPT_KINDS if kind.startswith("LEASE_"))
MUTATION_KINDS = frozenset(kind for kind in RECEIPT_KINDS if kind.startswith("MUTATION_"))
AUTHORITY_LEVELS = frozenset(("D0", "D1", "D2", "D3", "D4"))
EXPECTED_OUTCOME = {
    "LEASE_ISSUED": "ADMITTED",
    "LEASE_ISSUANCE_DENIED": "DENIED",
    "LEASE_RENEWED": "ADMITTED",
    "LEASE_RENEWAL_DENIED": "DENIED",
    "LEASE_EXPIRED": "EXPIRED",
    "LEASE_REVOKED": "REVOKED",
    "MUTATION_ADMITTED": "ADMITTED",
    "MUTATION_DENIED": "DENIED",
    "MUTATION_COMPLETED": "COMPLETED",
    "MUTATION_CANCELLED": "CANCELLED",
    "MUTATION_FAILED": "FAILED",
}
DENIAL_KINDS = frozenset((
    "LEASE_ISSUANCE_DENIED", "LEASE_RENEWAL_DENIED", "LEASE_EXPIRED", "LEASE_REVOKED",
    "MUTATION_DENIED", "MUTATION_CANCELLED", "MUTATION_FAILED",
))

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")
DECIMAL_RE = re.compile(r"^(0|[1-9][0-9]*)$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$")

ENVELOPE_KEYS = frozenset(("schema_version", "receipt_kind", "receipt_body", "proof", "receipt_id"))
RECEIPT_BODY_KEYS = frozenset((
    "receipt_sequence",
    "actor_identity_root",
    "session_identity_root",
    "workspace_identity_root",
    "holon_identity_root",
    "authority_domain",
    "authority_level",
    "authority_receipt_hash",
    "lease_id",
    "lease_generation",
    "fencing_token",
    "lease_authorization_receipt_hash",
    "parent_receipt_hash",
    "observed_state_root",
    "expected_state_root",
    "action_digest",
    "before_state_root",
    "after_state_root",
    "result_digest",
    "timestamp_ms",
    "expires_at_ms",
    "nonce",
    "outcome",
    "denial_codes",
))
RECEIPT_PROOF_KEYS = frozenset((
    "algorithm", "signer_key_id", "verifier_identity_root",
    "trust_registry_version", "trust_registry_root", "signature",
))
REGISTRY_KEYS = frozenset(("schema_version", "registry_body", "proof", "registry_root"))
REGISTRY_BODY_KEYS = frozenset((
    "registry_version", "previous_registry_root", "issued_at_ms", "valid_from_ms",
    "expires_at_ms", "operator_key_id", "keys",
))
REGISTRY_PROOF_KEYS = frozenset(("algorithm", "signature"))
REGISTRY_ENTRY_KEYS = frozenset((
    "key_id", "public_key", "verifier_identity_root", "valid_from_ms",
    "expires_at_ms", "status", "authority_domains", "receipt_kinds",
))


class AuthoritativeReceiptError(ValueError):
    """Fail-closed validation or state-transition error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ReceiptStoreConflict(AuthoritativeReceiptError):
    """A durable compare-and-append precondition was no longer current."""


def _fail(code: str) -> None:
    raise AuthoritativeReceiptError(code)


def assert_i_json(value: Any, label: str = "value") -> None:
    """Reject values outside the closed, cross-runtime canonical JSON set."""

    def visit(item: Any, path: str, ancestors: set[int]) -> None:
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, str):
            for char in item:
                if 0xD800 <= ord(char) <= 0xDFFF:
                    _fail(f"I_JSON_UNPAIRED_SURROGATE:{path}")
            return
        if isinstance(item, int):
            if abs(item) > 9_007_199_254_740_991:
                _fail(f"I_JSON_INTEGER_OUT_OF_RANGE:{path}")
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                _fail(f"I_JSON_NONFINITE_NUMBER:{path}")
            _fail(f"I_JSON_FLOAT_FORBIDDEN:{path}")
        if type(item) is list:
            identity = id(item)
            if identity in ancestors:
                _fail(f"I_JSON_CYCLE:{path}")
            ancestors.add(identity)
            try:
                for index, child in enumerate(item):
                    visit(child, f"{path}[{index}]", ancestors)
            finally:
                ancestors.remove(identity)
            return
        if type(item) is dict:
            identity = id(item)
            if identity in ancestors:
                _fail(f"I_JSON_CYCLE:{path}")
            ancestors.add(identity)
            try:
                for key, child in item.items():
                    if not isinstance(key, str):
                        _fail(f"I_JSON_NON_STRING_KEY:{path}")
                    visit(key, f"{path}.<key>", ancestors)
                    visit(child, f"{path}.{key}", ancestors)
            finally:
                ancestors.remove(identity)
            return
        _fail(f"I_JSON_TYPE_FORBIDDEN:{path}:{type(item).__name__}")

    visit(value, label, set())
    # Canonicalization is deliberately delegated to the existing implementation.
    canon(value)


def _object_pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"JSON_DUPLICATE_KEY:{key}")
        result[key] = value
    return result


def load_json_strict(data: bytes | str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8", errors="strict") if isinstance(data, bytes) else data
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs_no_duplicates,
            parse_float=lambda _value: _fail("I_JSON_FLOAT_FORBIDDEN:$"),
            parse_constant=lambda _value: _fail("I_JSON_NONFINITE_NUMBER:$"),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthoritativeReceiptError("JSON_MALFORMED") from exc
    assert_i_json(value)
    if type(value) is not dict:
        _fail("JSON_ROOT_NOT_OBJECT")
    return value


def _exact_keys(value: Any, expected: frozenset[str], code: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != expected:
        _fail(code)
    return value


def _hash(field: str, value: Any, *, nonzero: bool = False) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        _fail(f"{field}:INVALID_SHA256")
    if nonzero and value == ZERO_HASH:
        _fail(f"{field}:UNRESOLVED")
    return value


def _signature(field: str, value: Any) -> str:
    if not isinstance(value, str) or not SIGNATURE_RE.fullmatch(value):
        _fail(f"{field}:INVALID_ED25519_SIGNATURE")
    return value


def _decimal(field: str, value: Any) -> str:
    if not isinstance(value, str) or len(value) > 20 or not DECIMAL_RE.fullmatch(value):
        _fail(f"{field}:INVALID_DECIMAL")
    return value


def _decimal_int(field: str, value: Any) -> int:
    return int(_decimal(field, value))


def _safe_id(field: str, value: Any) -> str:
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        _fail(f"{field}:INVALID_ID")
    return value


def _nonce(value: Any) -> str:
    if not isinstance(value, str) or not NONCE_RE.fullmatch(value):
        _fail("nonce:INVALID")
    return value


def _canonical_codes(value: Any, *, required: bool) -> tuple[str, ...]:
    if type(value) is not list or len(value) > 32:
        _fail("denial_codes:INVALID")
    codes = tuple(_safe_id("denial_code", item) for item in value)
    if tuple(sorted(set(codes), key=lambda item: item.encode("utf-8"))) != codes:
        _fail("denial_codes:NONCANONICAL")
    if required and not codes:
        _fail("denial_codes:REQUIRED")
    if not required and codes:
        _fail("denial_codes:FORBIDDEN")
    return codes


def _domain_hash(domain: str, value: Any) -> str:
    assert_i_json(value)
    return sha256_hex(canon({"domain": domain, "value": value}))


def _ed25519_private_key(private_key_hex: str):
    if not isinstance(private_key_hex, str) or not HASH_RE.fullmatch(private_key_hex):
        _fail("SIGNING_PRIVATE_KEY_INVALID")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    except ImportError as exc:  # pragma: no cover - dependency is pinned in CI
        raise AuthoritativeReceiptError("SIGNATURE_PROVIDER_UNAVAILABLE") from exc
    except ValueError as exc:
        raise AuthoritativeReceiptError("SIGNING_PRIVATE_KEY_INVALID") from exc


def public_key_hex_from_private(private_key_hex: str) -> str:
    try:
        from cryptography.hazmat.primitives import serialization
        return _ed25519_private_key(private_key_hex).public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
    except ImportError as exc:  # pragma: no cover
        raise AuthoritativeReceiptError("SIGNATURE_PROVIDER_UNAVAILABLE") from exc


def _sign(private_key_hex: str, message: bytes) -> str:
    return _ed25519_private_key(private_key_hex).sign(message).hex()


def _verify(public_key_hex: str, signature_hex: str, message: bytes, code: str) -> None:
    _hash("public_key", public_key_hex)
    _signature("signature", signature_hex)
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(
            bytes.fromhex(signature_hex), message,
        )
    except ImportError as exc:  # pragma: no cover
        raise AuthoritativeReceiptError("SIGNATURE_PROVIDER_UNAVAILABLE") from exc
    except InvalidSignature as exc:
        raise AuthoritativeReceiptError(code) from exc
    except ValueError as exc:
        raise AuthoritativeReceiptError("SIGNING_PUBLIC_KEY_INVALID") from exc


def canonical_registry_signature_message(registry: Mapping[str, Any]) -> bytes:
    body = registry["registry_body"]
    proof = registry["proof"]
    return canon({
        "domain": REGISTRY_SIGNATURE_DOMAIN,
        "schema_version": registry["schema_version"],
        "registry_body": body,
        "proof": {"algorithm": proof["algorithm"]},
    })


def compute_registry_root(registry: Mapping[str, Any]) -> str:
    return sha256_hex(canon({
        "domain": REGISTRY_ROOT_DOMAIN,
        "registry": {
            "schema_version": registry["schema_version"],
            "registry_body": registry["registry_body"],
            "proof": {
                "algorithm": registry["proof"]["algorithm"],
                "signature": registry["proof"]["signature"],
            },
        },
    }))


def canonical_receipt_signature_message(envelope: Mapping[str, Any]) -> bytes:
    proof = envelope["proof"]
    return canon({
        "domain": RECEIPT_SIGNATURE_DOMAIN,
        "schema_version": envelope["schema_version"],
        "receipt_kind": envelope["receipt_kind"],
        "receipt_body": envelope["receipt_body"],
        "proof": {
            "algorithm": proof["algorithm"],
            "signer_key_id": proof["signer_key_id"],
            "verifier_identity_root": proof["verifier_identity_root"],
            "trust_registry_version": proof["trust_registry_version"],
            "trust_registry_root": proof["trust_registry_root"],
        },
    })


def compute_receipt_id(envelope: Mapping[str, Any]) -> str:
    proof = envelope["proof"]
    return sha256_hex(canon({
        "domain": RECEIPT_ID_DOMAIN,
        "envelope": {
            "schema_version": envelope["schema_version"],
            "receipt_kind": envelope["receipt_kind"],
            "receipt_body": envelope["receipt_body"],
            "proof": {
                "algorithm": proof["algorithm"],
                "signer_key_id": proof["signer_key_id"],
                "verifier_identity_root": proof["verifier_identity_root"],
                "trust_registry_version": proof["trust_registry_version"],
                "trust_registry_root": proof["trust_registry_root"],
                "signature": proof["signature"],
            },
        },
    }))


def _validate_registry_shape(registry: Any) -> None:
    assert_i_json(registry, "registry")
    registry = _exact_keys(registry, REGISTRY_KEYS, "TRUST_REGISTRY_SCHEMA_DRIFT")
    if registry["schema_version"] != SCHEMA_VERSION:
        _fail("TRUST_REGISTRY_SCHEMA_UNSUPPORTED")
    body = _exact_keys(registry["registry_body"], REGISTRY_BODY_KEYS, "TRUST_REGISTRY_BODY_SCHEMA_DRIFT")
    proof = _exact_keys(registry["proof"], REGISTRY_PROOF_KEYS, "TRUST_REGISTRY_PROOF_SCHEMA_DRIFT")
    if proof["algorithm"] != ED25519:
        _fail("TRUST_REGISTRY_ALGORITHM_UNSUPPORTED")
    _signature("registry.signature", proof["signature"])
    _hash("registry.registry_root", registry["registry_root"], nonzero=True)
    version = _decimal_int("registry.registry_version", body["registry_version"])
    _hash("registry.previous_registry_root", body["previous_registry_root"])
    issued = _decimal_int("registry.issued_at_ms", body["issued_at_ms"])
    valid_from = _decimal_int("registry.valid_from_ms", body["valid_from_ms"])
    expires = _decimal_int("registry.expires_at_ms", body["expires_at_ms"])
    _safe_id("registry.operator_key_id", body["operator_key_id"])
    if version < 1:
        _fail("TRUST_REGISTRY_VERSION_INVALID")
    if (version == 1) != (body["previous_registry_root"] == ZERO_HASH):
        _fail("TRUST_REGISTRY_GENESIS_LINK_INVALID")
    if issued > valid_from or valid_from >= expires:
        _fail("TRUST_REGISTRY_TIME_WINDOW_INVALID")
    keys = body["keys"]
    if type(keys) is not list or not (1 <= len(keys) <= 128):
        _fail("TRUST_REGISTRY_KEYS_INVALID")
    key_ids: list[str] = []
    public_keys: list[str] = []
    for index, entry_value in enumerate(keys):
        entry = _exact_keys(entry_value, REGISTRY_ENTRY_KEYS, f"TRUST_REGISTRY_KEY_SCHEMA_DRIFT:{index}")
        key_id = _safe_id("registry.key_id", entry["key_id"])
        key_ids.append(key_id)
        public_keys.append(_hash("registry.public_key", entry["public_key"]))
        _hash("registry.verifier_identity_root", entry["verifier_identity_root"], nonzero=True)
        key_from = _decimal_int("registry.key.valid_from_ms", entry["valid_from_ms"])
        key_expires = _decimal_int("registry.key.expires_at_ms", entry["expires_at_ms"])
        if key_from >= key_expires or key_from < valid_from or key_expires > expires:
            _fail("TRUST_REGISTRY_KEY_TIME_WINDOW_INVALID")
        if entry["status"] not in ("ACTIVE", "REVOKED"):
            _fail("TRUST_REGISTRY_KEY_STATUS_INVALID")
        domains = entry["authority_domains"]
        kinds = entry["receipt_kinds"]
        if type(domains) is not list or not domains:
            _fail("TRUST_REGISTRY_KEY_DOMAINS_INVALID")
        if type(kinds) is not list or not kinds:
            _fail("TRUST_REGISTRY_KEY_KINDS_INVALID")
        normalized_domains = tuple(_safe_id("registry.authority_domain", item) for item in domains)
        if tuple(sorted(set(normalized_domains), key=lambda item: item.encode("utf-8"))) != normalized_domains:
            _fail("TRUST_REGISTRY_KEY_DOMAINS_NONCANONICAL")
        normalized_kinds = tuple(kinds)
        if any(kind not in RECEIPT_KINDS for kind in normalized_kinds):
            _fail("TRUST_REGISTRY_KEY_KIND_INVALID")
        if tuple(sorted(set(normalized_kinds), key=lambda item: item.encode("utf-8"))) != normalized_kinds:
            _fail("TRUST_REGISTRY_KEY_KINDS_NONCANONICAL")
    if tuple(sorted(set(key_ids), key=lambda item: item.encode("utf-8"))) != tuple(key_ids):
        _fail("TRUST_REGISTRY_KEYS_NONCANONICAL")
    if len(set(public_keys)) != len(public_keys):
        _fail("TRUST_REGISTRY_PUBLIC_KEYS_DUPLICATE")


_VERIFIED_REGISTRY_CAPABILITY = object()


@dataclass(frozen=True)
class VerifiedTrustRegistry:
    """Tamper-evident verified registry backed only by immutable canonical bytes."""

    canonical_document: bytes
    registry_root: str
    registry_version: str
    previous_registry_root: str
    _capability: object

    @property
    def document(self) -> dict[str, Any]:
        return load_json_strict(self.canonical_document)

    @property
    def entries(self) -> Mapping[str, Mapping[str, Any]]:
        return {
            entry["key_id"]: entry
            for entry in self.document["registry_body"]["keys"]
        }


def _require_verified_registry(registry: VerifiedTrustRegistry) -> None:
    if not isinstance(registry, VerifiedTrustRegistry) or registry._capability is not _VERIFIED_REGISTRY_CAPABILITY:
        _fail("TRUST_REGISTRY_NOT_VERIFIED")
    document = registry.document
    _validate_registry_shape(document)
    if compute_registry_root(document) != registry.registry_root:
        _fail("TRUST_REGISTRY_CAPABILITY_TAMPERED")


def create_trust_registry(registry_body: Mapping[str, Any], operator_private_key_hex: str) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "registry_body": copy.deepcopy(dict(registry_body)),
        "proof": {"algorithm": ED25519, "signature": "0" * 128},
        "registry_root": "1" * 64,
    }
    # Validate the body and all exact-key constraints before signing it.
    _validate_registry_shape(draft)
    draft["proof"]["signature"] = _sign(operator_private_key_hex, canonical_registry_signature_message(draft))
    draft["registry_root"] = compute_registry_root(draft)
    _validate_registry_shape(draft)
    return draft


def verify_trust_registry(
    registry: Mapping[str, Any],
    *,
    pinned_operator_public_key_hex: str,
    expected_operator_key_id: str,
    expected_registry_root: str | None = None,
    expected_registry_version: str | None = None,
    verification_time_ms: str | None = None,
    max_clock_skew_ms: str = "0",
) -> VerifiedTrustRegistry:
    document = copy.deepcopy(dict(registry))
    _validate_registry_shape(document)
    if compute_registry_root(document) != document["registry_root"]:
        _fail("TRUST_REGISTRY_ROOT_MISMATCH")
    if expected_registry_root is not None and document["registry_root"] != _hash(
        "expected_registry_root", expected_registry_root, nonzero=True,
    ):
        _fail("TRUST_REGISTRY_NOT_EXPECTED")
    body = document["registry_body"]
    if body["operator_key_id"] != _safe_id("expected_operator_key_id", expected_operator_key_id):
        _fail("TRUST_REGISTRY_OPERATOR_KEY_ID_MISMATCH")
    if expected_registry_version is not None and body["registry_version"] != _decimal(
        "expected_registry_version", expected_registry_version,
    ):
        _fail("TRUST_REGISTRY_VERSION_NOT_EXPECTED")
    _verify(
        pinned_operator_public_key_hex,
        document["proof"]["signature"],
        canonical_registry_signature_message(document),
        "TRUST_REGISTRY_SIGNATURE_INVALID",
    )
    if verification_time_ms is not None:
        now = _decimal_int("verification_time_ms", verification_time_ms)
        skew = _decimal_int("max_clock_skew_ms", max_clock_skew_ms)
        valid_from = int(body["valid_from_ms"])
        expires = int(body["expires_at_ms"])
        if now + skew < valid_from:
            _fail("TRUST_REGISTRY_NOT_YET_VALID")
        if now - skew >= expires:
            _fail("TRUST_REGISTRY_EXPIRED")
    return VerifiedTrustRegistry(
        canonical_document=canon(document),
        registry_root=document["registry_root"],
        registry_version=body["registry_version"],
        previous_registry_root=body["previous_registry_root"],
        _capability=_VERIFIED_REGISTRY_CAPABILITY,
    )


def verify_registry_rotation(previous: VerifiedTrustRegistry, current: VerifiedTrustRegistry) -> None:
    _require_verified_registry(previous)
    _require_verified_registry(current)
    if current.previous_registry_root != previous.registry_root:
        _fail("TRUST_REGISTRY_ROTATION_PARENT_MISMATCH")
    if int(current.registry_version) != int(previous.registry_version) + 1:
        _fail("TRUST_REGISTRY_ROTATION_VERSION_INVALID")
    if int(current.document["registry_body"]["issued_at_ms"]) < int(previous.document["registry_body"]["issued_at_ms"]):
        _fail("TRUST_REGISTRY_ROTATION_TIME_REGRESSION")


def _validate_receipt_shape(envelope: Any) -> None:
    assert_i_json(envelope, "receipt")
    envelope = _exact_keys(envelope, ENVELOPE_KEYS, "RECEIPT_SCHEMA_DRIFT")
    if envelope["schema_version"] != SCHEMA_VERSION:
        _fail("RECEIPT_SCHEMA_UNSUPPORTED")
    kind = envelope["receipt_kind"]
    if kind not in RECEIPT_KINDS:
        _fail("RECEIPT_KIND_INVALID")
    body = _exact_keys(envelope["receipt_body"], RECEIPT_BODY_KEYS, "RECEIPT_BODY_SCHEMA_DRIFT")
    proof = _exact_keys(envelope["proof"], RECEIPT_PROOF_KEYS, "RECEIPT_PROOF_SCHEMA_DRIFT")
    _hash("receipt_id", envelope["receipt_id"])
    _decimal("receipt_sequence", body["receipt_sequence"])
    for field in (
        "actor_identity_root", "session_identity_root", "workspace_identity_root", "holon_identity_root", "lease_id",
    ):
        _hash(field, body[field], nonzero=True)
    for field in (
        "authority_receipt_hash", "fencing_token", "lease_authorization_receipt_hash",
        "parent_receipt_hash", "action_digest", "result_digest",
    ):
        _hash(field, body[field])
    for field in (
        "observed_state_root", "expected_state_root", "before_state_root", "after_state_root",
    ):
        _hash(field, body[field], nonzero=True)
    _hash("action_digest", body["action_digest"], nonzero=True)
    _safe_id("authority_domain", body["authority_domain"])
    if body["authority_level"] not in AUTHORITY_LEVELS:
        _fail("authority_level:INVALID")
    _decimal("lease_generation", body["lease_generation"])
    _decimal("timestamp_ms", body["timestamp_ms"])
    _decimal("expires_at_ms", body["expires_at_ms"])
    _nonce(body["nonce"])
    if body["outcome"] != EXPECTED_OUTCOME[kind]:
        _fail("RECEIPT_KIND_OUTCOME_MISMATCH")
    _canonical_codes(body["denial_codes"], required=kind in DENIAL_KINDS)
    if kind != "MUTATION_COMPLETED" and body["after_state_root"] != body["before_state_root"]:
        _fail("NON_COMPLETION_STATE_CHANGED")
    if body["before_state_root"] != body["observed_state_root"]:
        _fail("BEFORE_STATE_NOT_OBSERVED_STATE")
    if body["result_digest"] == ZERO_HASH:
        _fail("result_digest:UNRESOLVED")
    if kind in LEASE_KINDS:
        if body["authority_receipt_hash"] != ZERO_HASH or body["lease_authorization_receipt_hash"] != ZERO_HASH:
            _fail("LEASE_RECEIPT_HAS_MUTATION_AUTHORITY_HASH")
    else:
        _hash("authority_receipt_hash", body["authority_receipt_hash"], nonzero=True)
        _hash("lease_authorization_receipt_hash", body["lease_authorization_receipt_hash"], nonzero=True)
    if kind == "LEASE_ISSUANCE_DENIED":
        if body["fencing_token"] != ZERO_HASH:
            _fail("LEASE_ISSUANCE_DENIAL_HAS_FENCE")
    else:
        _hash("fencing_token", body["fencing_token"], nonzero=True)
    if proof["algorithm"] != ED25519:
        _fail("RECEIPT_ALGORITHM_UNSUPPORTED")
    _safe_id("signer_key_id", proof["signer_key_id"])
    _hash("verifier_identity_root", proof["verifier_identity_root"], nonzero=True)
    _decimal("trust_registry_version", proof["trust_registry_version"])
    _hash("trust_registry_root", proof["trust_registry_root"], nonzero=True)
    _signature("receipt.signature", proof["signature"])


def sign_receipt(
    *,
    receipt_kind: str,
    receipt_body: Mapping[str, Any],
    registry: VerifiedTrustRegistry,
    signer_key_id: str,
    signer_private_key_hex: str,
) -> dict[str, Any]:
    _require_verified_registry(registry)
    entry = registry.entries.get(signer_key_id)
    if entry is None:
        _fail("RECEIPT_SIGNER_UNKNOWN")
    envelope: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": receipt_kind,
        "receipt_body": copy.deepcopy(dict(receipt_body)),
        "proof": {
            "algorithm": ED25519,
            "signer_key_id": signer_key_id,
            "verifier_identity_root": entry["verifier_identity_root"],
            "trust_registry_version": registry.registry_version,
            "trust_registry_root": registry.registry_root,
            "signature": "0" * 128,
        },
        "receipt_id": "1" * 64,
    }
    _validate_receipt_shape(envelope)
    if public_key_hex_from_private(signer_private_key_hex) != entry["public_key"]:
        _fail("RECEIPT_SIGNING_KEY_MISMATCH")
    envelope["proof"]["signature"] = _sign(signer_private_key_hex, canonical_receipt_signature_message(envelope))
    envelope["receipt_id"] = compute_receipt_id(envelope)
    _validate_receipt_shape(envelope)
    return envelope


def verify_receipt(
    envelope: Mapping[str, Any],
    *,
    registry: VerifiedTrustRegistry,
    verification_time_ms: str | None = None,
    max_clock_skew_ms: str = "0",
) -> dict[str, Any]:
    _require_verified_registry(registry)
    document = copy.deepcopy(dict(envelope))
    _validate_receipt_shape(document)
    if compute_receipt_id(document) != document["receipt_id"]:
        _fail("RECEIPT_ID_MISMATCH")
    proof = document["proof"]
    body = document["receipt_body"]
    if proof["trust_registry_root"] != registry.registry_root or proof["trust_registry_version"] != registry.registry_version:
        _fail("RECEIPT_TRUST_REGISTRY_MISMATCH")
    entry = registry.entries.get(proof["signer_key_id"])
    if entry is None:
        _fail("RECEIPT_SIGNER_UNKNOWN")
    if entry["status"] != "ACTIVE":
        _fail("RECEIPT_SIGNER_REVOKED")
    if proof["verifier_identity_root"] != entry["verifier_identity_root"]:
        _fail("RECEIPT_VERIFIER_IDENTITY_MISMATCH")
    if body["authority_domain"] not in entry["authority_domains"]:
        _fail("RECEIPT_SIGNER_DOMAIN_UNTRUSTED")
    if document["receipt_kind"] not in entry["receipt_kinds"]:
        _fail("RECEIPT_SIGNER_KIND_UNTRUSTED")
    timestamp = int(body["timestamp_ms"])
    registry_body = registry.document["registry_body"]
    if timestamp < int(registry_body["valid_from_ms"]) or timestamp >= int(registry_body["expires_at_ms"]):
        _fail("RECEIPT_OUTSIDE_REGISTRY_WINDOW")
    if timestamp < int(entry["valid_from_ms"]) or timestamp >= int(entry["expires_at_ms"]):
        _fail("RECEIPT_OUTSIDE_SIGNER_WINDOW")
    if verification_time_ms is not None:
        now = _decimal_int("verification_time_ms", verification_time_ms)
        skew = _decimal_int("max_clock_skew_ms", max_clock_skew_ms)
        if timestamp > now + skew:
            _fail("RECEIPT_TIMESTAMP_IN_FUTURE")
    _verify(
        entry["public_key"], proof["signature"], canonical_receipt_signature_message(document),
        "RECEIPT_SIGNATURE_INVALID",
    )
    return document


class SQLiteReceiptStore:
    """Add-only content-addressed registry and receipt store with chain-head CAS."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS trust_registries (registry_root TEXT PRIMARY KEY, canonical BLOB NOT NULL)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS receipts (receipt_id TEXT PRIMARY KEY, receipt_sequence TEXT NOT NULL UNIQUE, canonical BLOB NOT NULL)"
        )
        self._lock = threading.RLock()
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            _fail("RECEIPT_STORE_CLOSED")

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def _read_pending_registry_bytes(self, registry_root: str) -> bytes | None:
        """Read a registry append inside the current transaction for fault injection."""

        row = self._connection.execute(
            "SELECT canonical FROM trust_registries WHERE registry_root = ?", (registry_root,),
        ).fetchone()
        return None if row is None else bytes(row[0])

    def persist_registry(self, registry: Mapping[str, Any]) -> str:
        document = copy.deepcopy(dict(registry))
        _validate_registry_shape(document)
        if compute_registry_root(document) != document["registry_root"]:
            _fail("TRUST_REGISTRY_ROOT_MISMATCH")
        encoded = canon(document)
        root = document["registry_root"]
        with self._lock:
            self._require_open()
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT canonical FROM trust_registries WHERE registry_root = ?", (root,),
                ).fetchone()
                if row is not None:
                    if bytes(row[0]) != encoded:
                        _fail("TRUST_REGISTRY_CONTENT_CONFLICT")
                else:
                    self._connection.execute(
                        "INSERT INTO trust_registries(registry_root, canonical) VALUES (?, ?)",
                        (root, sqlite3.Binary(encoded)),
                    )
                pending = self._read_pending_registry_bytes(root)
                if pending is None:
                    _fail("TRUST_REGISTRY_READBACK_MISMATCH")
                read_back = load_json_strict(pending)
                _validate_registry_shape(read_back)
                if pending != encoded or canon(read_back) != encoded or compute_registry_root(read_back) != root:
                    _fail("TRUST_REGISTRY_READBACK_MISMATCH")
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
        return root

    def read_registry(self, registry_root: str) -> dict[str, Any] | None:
        root = _hash("registry_root", registry_root, nonzero=True)
        with self._lock:
            self._require_open()
            row = self._connection.execute(
                "SELECT canonical FROM trust_registries WHERE registry_root = ?", (root,),
            ).fetchone()
        if row is None:
            return None
        encoded = bytes(row[0])
        document = load_json_strict(encoded)
        _validate_registry_shape(document)
        if canon(document) != encoded or compute_registry_root(document) != root:
            _fail("TRUST_REGISTRY_STORED_BYTES_INVALID")
        return document

    def _read_pending_receipt_bytes(self, receipt_id: str) -> bytes | None:
        """Read an append inside the current transaction for fault injection."""

        row = self._connection.execute(
            "SELECT canonical FROM receipts WHERE receipt_id = ?", (receipt_id,),
        ).fetchone()
        return None if row is None else bytes(row[0])

    def persist_receipt(
        self,
        envelope: Mapping[str, Any],
        *,
        registry: VerifiedTrustRegistry,
        verification_time_ms: str | None = None,
        max_clock_skew_ms: str = "0",
    ) -> str:
        # Persistence requires an authenticated registry capability. Shape-valid
        # unsigned bytes cannot enter through the public store API.
        document = verify_receipt(
            envelope,
            registry=registry,
            verification_time_ms=verification_time_ms,
            max_clock_skew_ms=max_clock_skew_ms,
        )
        receipt_id = document["receipt_id"]
        body = document["receipt_body"]
        sequence = body["receipt_sequence"]
        parent = body["parent_receipt_hash"]
        encoded = canon(document)
        with self._lock:
            self._require_open()
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                duplicate = self._connection.execute(
                    "SELECT canonical FROM receipts WHERE receipt_id = ?", (receipt_id,),
                ).fetchone()
                if duplicate is not None:
                    if bytes(duplicate[0]) != encoded:
                        _fail("RECEIPT_CONTENT_CONFLICT")
                    self._connection.execute("COMMIT")
                    return receipt_id
                head = self._connection.execute(
                    "SELECT receipt_id, receipt_sequence FROM receipts "
                    "ORDER BY length(receipt_sequence) DESC, receipt_sequence DESC LIMIT 1"
                ).fetchone()
                expected_sequence = "0" if head is None else str(int(head[1]) + 1)
                expected_parent = ZERO_HASH if head is None else str(head[0])
                if sequence != expected_sequence:
                    raise ReceiptStoreConflict("RECEIPT_STORE_SEQUENCE_STALE")
                if parent != expected_parent:
                    raise ReceiptStoreConflict("RECEIPT_STORE_PARENT_STALE")
                self._connection.execute(
                    "INSERT INTO receipts(receipt_id, receipt_sequence, canonical) VALUES (?, ?, ?)",
                    (receipt_id, sequence, sqlite3.Binary(encoded)),
                )
                pending = self._read_pending_receipt_bytes(receipt_id)
                if pending is None:
                    _fail("RECEIPT_READBACK_MISMATCH")
                read_back = load_json_strict(pending)
                _validate_receipt_shape(read_back)
                if pending != encoded or canon(read_back) != encoded or compute_receipt_id(read_back) != receipt_id:
                    _fail("RECEIPT_READBACK_MISMATCH")
                self._connection.execute("COMMIT")
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
        return receipt_id

    def read_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        root = _hash("receipt_id", receipt_id, nonzero=True)
        with self._lock:
            self._require_open()
            row = self._connection.execute(
                "SELECT canonical FROM receipts WHERE receipt_id = ?", (root,),
            ).fetchone()
        if row is None:
            return None
        encoded = bytes(row[0])
        document = load_json_strict(encoded)
        _validate_receipt_shape(document)
        if canon(document) != encoded or compute_receipt_id(document) != root:
            _fail("RECEIPT_STORED_BYTES_INVALID")
        return document

    def read_all_receipts(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            self._require_open()
            rows = self._connection.execute(
                "SELECT receipt_id, canonical FROM receipts "
                "ORDER BY length(receipt_sequence), receipt_sequence"
            ).fetchall()
        result: list[dict[str, Any]] = []
        for receipt_id, encoded_value in rows:
            encoded = bytes(encoded_value)
            document = load_json_strict(encoded)
            _validate_receipt_shape(document)
            if canon(document) != encoded or compute_receipt_id(document) != receipt_id:
                _fail("RECEIPT_STORED_BYTES_INVALID")
            result.append(document)
        return tuple(result)


@dataclass(frozen=True)
class ReceiptBindings:
    actor_identity_root: str
    session_identity_root: str
    workspace_identity_root: str
    holon_identity_root: str
    authority_domain: str
    authority_level: str

    def validate(self) -> None:
        for field in (
            "actor_identity_root", "session_identity_root", "workspace_identity_root", "holon_identity_root",
        ):
            _hash(field, getattr(self, field), nonzero=True)
        _safe_id("authority_domain", self.authority_domain)
        if self.authority_level not in AUTHORITY_LEVELS:
            _fail("authority_level:INVALID")


@dataclass
class _LeaseState:
    bindings: ReceiptBindings
    lease_id: str
    generation: int
    fencing_token: str
    expected_state_root: str
    expires_at_ms: int
    authorization_receipt_hash: str
    active: bool


@dataclass
class _MutationState:
    lease_id: str
    generation: int
    fencing_token: str
    action_digest: str
    authority_receipt_hash: str
    lease_authorization_receipt_hash: str
    before_state_root: str
    status: str


class AuthoritativeReceiptAuthority:
    """Locked state machine whose only durable transitions are signed receipts."""

    def __init__(
        self,
        *,
        store: SQLiteReceiptStore,
        current_registry: Mapping[str, Any],
        pinned_operator_public_key_hex: str,
        expected_operator_key_id: str,
        expected_registry_root: str,
        signer_key_id: str,
        signer_private_key_hex: str,
        verification_time_ms: str,
        max_clock_skew_ms: str = "0",
    ):
        self._store = store
        self._pinned_operator_public_key_hex = pinned_operator_public_key_hex
        self._expected_operator_key_id = _safe_id("expected_operator_key_id", expected_operator_key_id)
        self._verification_time_ms = _decimal("verification_time_ms", verification_time_ms)
        self._max_clock_skew_ms = _decimal("max_clock_skew_ms", max_clock_skew_ms)
        self._signer_key_id = _safe_id("signer_key_id", signer_key_id)
        self._signer_private_key_hex = signer_private_key_hex
        self._lock = threading.RLock()
        verified = verify_trust_registry(
            current_registry,
            pinned_operator_public_key_hex=pinned_operator_public_key_hex,
            expected_operator_key_id=self._expected_operator_key_id,
            expected_registry_root=expected_registry_root,
            verification_time_ms=verification_time_ms,
            max_clock_skew_ms=max_clock_skew_ms,
        )
        self._store.persist_registry(verified.document)
        self._current_registry = verified
        self._registries = self._load_registry_chain(verified)
        self._assert_signer(verified, verification_time_ms)
        self._reset_state()
        self.recover()

    def _load_registry_chain(self, current: VerifiedTrustRegistry) -> dict[str, VerifiedTrustRegistry]:
        chain = {current.registry_root: current}
        cursor = current
        while cursor.previous_registry_root != ZERO_HASH:
            document = self._store.read_registry(cursor.previous_registry_root)
            if document is None:
                _fail("TRUST_REGISTRY_ANCESTOR_MISSING")
            previous = verify_trust_registry(
                document,
                pinned_operator_public_key_hex=self._pinned_operator_public_key_hex,
                expected_operator_key_id=self._expected_operator_key_id,
                expected_registry_root=cursor.previous_registry_root,
            )
            verify_registry_rotation(previous, cursor)
            if previous.registry_root in chain:
                _fail("TRUST_REGISTRY_CHAIN_CYCLE")
            chain[previous.registry_root] = previous
            cursor = previous
        return chain

    def _assert_signer(self, registry: VerifiedTrustRegistry, at_ms: str) -> None:
        entry = registry.entries.get(self._signer_key_id)
        if entry is None or entry["status"] != "ACTIVE":
            _fail("RECEIPT_SIGNER_NOT_ACTIVE")
        if public_key_hex_from_private(self._signer_private_key_hex) != entry["public_key"]:
            _fail("RECEIPT_SIGNING_KEY_MISMATCH")
        moment = int(_decimal("signer_time_ms", at_ms))
        if moment < int(entry["valid_from_ms"]) or moment >= int(entry["expires_at_ms"]):
            _fail("RECEIPT_SIGNER_OUTSIDE_VALIDITY")

    def rotate_registry(
        self,
        registry: Mapping[str, Any],
        *,
        expected_registry_root: str,
        verification_time_ms: str,
        signer_key_id: str | None = None,
        signer_private_key_hex: str | None = None,
    ) -> None:
        with self._lock:
            if int(_decimal("verification_time_ms", verification_time_ms)) < int(self._verification_time_ms):
                _fail("OBSERVED_TIME_REGRESSION")
            verified = verify_trust_registry(
                registry,
                pinned_operator_public_key_hex=self._pinned_operator_public_key_hex,
                expected_operator_key_id=self._expected_operator_key_id,
                expected_registry_root=expected_registry_root,
                verification_time_ms=verification_time_ms,
                max_clock_skew_ms=self._max_clock_skew_ms,
            )
            verify_registry_rotation(self._current_registry, verified)
            next_key_id = self._signer_key_id if signer_key_id is None else _safe_id("signer_key_id", signer_key_id)
            next_private = self._signer_private_key_hex if signer_private_key_hex is None else signer_private_key_hex
            old_key, old_private = self._signer_key_id, self._signer_private_key_hex
            self._signer_key_id, self._signer_private_key_hex = next_key_id, next_private
            try:
                self._assert_signer(verified, verification_time_ms)
                self._store.persist_registry(verified.document)
            except BaseException:
                self._signer_key_id, self._signer_private_key_hex = old_key, old_private
                raise
            self._current_registry = verified
            self._registries[verified.registry_root] = verified
            self._verification_time_ms = verification_time_ms

    def update_observed_time(self, observed_at_ms: str) -> None:
        """Advance the explicit trusted observation time without reading a clock."""

        with self._lock:
            observed = _decimal("observed_at_ms", observed_at_ms)
            if int(observed) < int(self._verification_time_ms):
                _fail("OBSERVED_TIME_REGRESSION")
            refreshed = verify_trust_registry(
                self._current_registry.document,
                pinned_operator_public_key_hex=self._pinned_operator_public_key_hex,
                expected_operator_key_id=self._expected_operator_key_id,
                expected_registry_root=self._current_registry.registry_root,
                expected_registry_version=self._current_registry.registry_version,
                verification_time_ms=observed,
                max_clock_skew_ms=self._max_clock_skew_ms,
            )
            self._assert_signer(refreshed, observed)
            self._current_registry = refreshed
            self._registries[refreshed.registry_root] = refreshed
            self._verification_time_ms = observed

    def _reset_state(self) -> None:
        self._head = ZERO_HASH
        self._next_sequence = 0
        self._last_timestamp = -1
        self._state_roots: dict[tuple[str, str, str], str] = {}
        self._leases: dict[tuple[str, str, str], _LeaseState] = {}
        self._lease_ids: set[str] = set()
        self._generations: dict[tuple[str, str, str], int] = {}
        self._mutations: dict[tuple[str, str, str, str, str, str], _MutationState] = {}
        self._consumed_actions: set[tuple[str, str, str, str, str, str]] = set()
        self._nonces: set[str] = set()
        self._last_receipt_registry_version: int | None = None
        self._last_receipt_registry_root: str | None = None

    @property
    def head_receipt_id(self) -> str:
        with self._lock:
            return self._head

    @staticmethod
    def _scope(bindings: ReceiptBindings) -> tuple[str, str, str]:
        bindings.validate()
        return (bindings.workspace_identity_root, bindings.holon_identity_root, bindings.authority_domain)

    @staticmethod
    def _action_key(bindings: ReceiptBindings, action_digest: str) -> tuple[str, str, str, str, str, str]:
        return (
            bindings.actor_identity_root,
            bindings.session_identity_root,
            bindings.workspace_identity_root,
            bindings.holon_identity_root,
            bindings.authority_domain,
            action_digest,
        )

    def canonical_state_root(self, bindings: ReceiptBindings) -> str | None:
        with self._lock:
            return self._state_roots.get(self._scope(bindings))

    def current_lease(self, bindings: ReceiptBindings) -> Mapping[str, Any] | None:
        with self._lock:
            lease = self._leases.get(self._scope(bindings))
            if lease is None or not lease.active or int(self._verification_time_ms) >= lease.expires_at_ms:
                return None
            return {
                "lease_id": lease.lease_id,
                "lease_generation": str(lease.generation),
                "fencing_token": lease.fencing_token,
                "expected_state_root": lease.expected_state_root,
                "expires_at_ms": str(lease.expires_at_ms),
            }

    def recover(self) -> None:
        with self._lock:
            self._reset_state()
            for envelope in self._store.read_all_receipts():
                registry_root = envelope["proof"]["trust_registry_root"]
                registry = self._registries.get(registry_root)
                if registry is None:
                    _fail("RECEIPT_TRUST_REGISTRY_UNRESOLVED")
                verified = verify_receipt(
                    envelope,
                    registry=registry,
                    verification_time_ms=self._verification_time_ms,
                    max_clock_skew_ms=self._max_clock_skew_ms,
                )
                self._apply_verified_receipt(verified)

    def _bindings_from_body(self, body: Mapping[str, Any]) -> ReceiptBindings:
        return ReceiptBindings(
            actor_identity_root=body["actor_identity_root"],
            session_identity_root=body["session_identity_root"],
            workspace_identity_root=body["workspace_identity_root"],
            holon_identity_root=body["holon_identity_root"],
            authority_domain=body["authority_domain"],
            authority_level=body["authority_level"],
        )

    @staticmethod
    def _same_bindings(left: ReceiptBindings, right: ReceiptBindings) -> bool:
        return left == right

    def _registry_descends_from(self, candidate_root: str, ancestor_root: str) -> bool:
        cursor = self._registries.get(candidate_root)
        visited: set[str] = set()
        while cursor is not None and cursor.registry_root not in visited:
            if cursor.registry_root == ancestor_root:
                return True
            visited.add(cursor.registry_root)
            if cursor.previous_registry_root == ZERO_HASH:
                return False
            cursor = self._registries.get(cursor.previous_registry_root)
        return False

    def _apply_verified_receipt(self, envelope: Mapping[str, Any]) -> None:
        kind = envelope["receipt_kind"]
        body = envelope["receipt_body"]
        proof = envelope["proof"]
        sequence = int(body["receipt_sequence"])
        timestamp = int(body["timestamp_ms"])
        if sequence != self._next_sequence:
            _fail("RECEIPT_CHAIN_SEQUENCE_BREAK")
        if body["parent_receipt_hash"] != self._head:
            _fail("RECEIPT_CHAIN_PARENT_BREAK")
        if timestamp < self._last_timestamp:
            _fail("RECEIPT_TIMESTAMP_REGRESSION")
        if body["nonce"] in self._nonces:
            _fail("RECEIPT_NONCE_REPLAY")
        registry_version = int(proof["trust_registry_version"])
        registry_root = proof["trust_registry_root"]
        if self._last_receipt_registry_version is not None:
            if registry_version < self._last_receipt_registry_version:
                _fail("RECEIPT_TRUST_REGISTRY_DOWNGRADE")
            if registry_version == self._last_receipt_registry_version:
                if registry_root != self._last_receipt_registry_root:
                    _fail("RECEIPT_TRUST_REGISTRY_FORK")
            elif not self._registry_descends_from(registry_root, self._last_receipt_registry_root):
                _fail("RECEIPT_TRUST_REGISTRY_LINEAGE_BREAK")
        bindings = self._bindings_from_body(body)
        scope = self._scope(bindings)
        actual_state = self._state_roots.get(scope)
        state_was_uninitialized = actual_state is None
        if actual_state is None:
            if kind not in ("LEASE_ISSUED", "LEASE_ISSUANCE_DENIED"):
                _fail("CANONICAL_STATE_UNINITIALIZED")
            actual_state = body["observed_state_root"]
        if body["observed_state_root"] != actual_state or body["before_state_root"] != actual_state:
            _fail("RECEIPT_OBSERVED_STATE_STALE")
        generation = int(body["lease_generation"])
        lease = self._leases.get(scope)

        if kind == "LEASE_ISSUED":
            if lease is not None and lease.active:
                _fail("LEASE_ALREADY_ACTIVE")
            if body["lease_id"] in self._lease_ids:
                _fail("LEASE_ID_REPLAY")
            if body["expected_state_root"] != actual_state:
                _fail("LEASE_EXPECTED_STATE_STALE")
            if generation != self._generations.get(scope, 0) + 1:
                _fail("LEASE_GENERATION_STALE")
            if int(body["expires_at_ms"]) <= timestamp:
                _fail("LEASE_EXPIRY_INVALID")
            self._leases[scope] = _LeaseState(
                bindings, body["lease_id"], generation, body["fencing_token"], actual_state,
                int(body["expires_at_ms"]), envelope["receipt_id"], True,
            )
            self._state_roots[scope] = actual_state
            self._lease_ids.add(body["lease_id"])
            self._generations[scope] = generation
        elif kind == "LEASE_ISSUANCE_DENIED":
            pass
        elif kind == "LEASE_RENEWED":
            self._require_lease_receipt_binding(lease, bindings, body, current_fence=False)
            if generation != lease.generation + 1:
                _fail("LEASE_GENERATION_STALE")
            if body["expected_state_root"] != actual_state:
                _fail("LEASE_EXPECTED_STATE_STALE")
            if timestamp >= lease.expires_at_ms:
                _fail("LEASE_EXPIRED")
            if int(body["expires_at_ms"]) <= lease.expires_at_ms:
                _fail("LEASE_RENEWAL_NOT_EXTENDED")
            lease.generation = generation
            lease.fencing_token = body["fencing_token"]
            lease.expires_at_ms = int(body["expires_at_ms"])
            lease.authorization_receipt_hash = envelope["receipt_id"]
            self._generations[scope] = generation
        elif kind == "LEASE_RENEWAL_DENIED":
            pass
        elif kind in ("LEASE_EXPIRED", "LEASE_REVOKED"):
            self._require_lease_receipt_binding(lease, bindings, body)
            if body["expected_state_root"] != actual_state:
                _fail("LEASE_EXPECTED_STATE_STALE")
            if kind == "LEASE_EXPIRED" and timestamp < lease.expires_at_ms:
                _fail("LEASE_NOT_EXPIRED")
            lease.active = False
        elif kind == "MUTATION_ADMITTED":
            self._require_lease_receipt_binding(lease, bindings, body)
            if timestamp >= lease.expires_at_ms:
                _fail("LEASE_EXPIRED")
            if body["expected_state_root"] != actual_state:
                _fail("MUTATION_EXPECTED_STATE_STALE")
            action_key = self._action_key(bindings, body["action_digest"])
            if action_key in self._consumed_actions:
                _fail("MUTATION_REPLAY")
            if body["lease_authorization_receipt_hash"] != lease.authorization_receipt_hash:
                _fail("LEASE_AUTHORIZATION_RECEIPT_MISMATCH")
            self._mutations[action_key] = _MutationState(
                lease_id=lease.lease_id,
                generation=lease.generation,
                fencing_token=lease.fencing_token,
                action_digest=body["action_digest"],
                authority_receipt_hash=body["authority_receipt_hash"],
                lease_authorization_receipt_hash=body["lease_authorization_receipt_hash"],
                before_state_root=actual_state,
                status="ADMITTED",
            )
            self._consumed_actions.add(action_key)
        elif kind == "MUTATION_DENIED":
            action_key = self._action_key(bindings, body["action_digest"])
            if action_key in self._consumed_actions:
                if "MUTATION_REPLAY" not in body["denial_codes"]:
                    _fail("MUTATION_REPLAY_DENIAL_CODE_MISSING")
            else:
                self._consumed_actions.add(action_key)
        elif kind in ("MUTATION_COMPLETED", "MUTATION_CANCELLED", "MUTATION_FAILED"):
            mutation = self._mutations.get(self._action_key(bindings, body["action_digest"]))
            if mutation is None or mutation.status != "ADMITTED":
                _fail("MUTATION_ADMISSION_MISSING_OR_TERMINAL")
            self._require_lease_receipt_binding(
                lease,
                bindings,
                body,
                permit_inactive=kind in ("MUTATION_CANCELLED", "MUTATION_FAILED"),
            )
            if (
                mutation.lease_id != body["lease_id"]
                or mutation.generation != generation
                or mutation.fencing_token != body["fencing_token"]
                or mutation.authority_receipt_hash != body["authority_receipt_hash"]
                or mutation.lease_authorization_receipt_hash != body["lease_authorization_receipt_hash"]
                or mutation.before_state_root != actual_state
            ):
                _fail("MUTATION_TERMINAL_BINDING_MISMATCH")
            if kind == "MUTATION_COMPLETED" and body["expected_state_root"] != actual_state:
                _fail("MUTATION_EXPECTED_STATE_STALE")
            if kind == "MUTATION_COMPLETED" and timestamp >= lease.expires_at_ms:
                _fail("LEASE_EXPIRED")
            mutation.status = EXPECTED_OUTCOME[kind]
            if kind == "MUTATION_COMPLETED":
                self._state_roots[scope] = body["after_state_root"]
                lease.expected_state_root = body["after_state_root"]
            lease.active = False
        else:  # pragma: no cover - closed enum above
            _fail("RECEIPT_KIND_INVALID")

        if state_was_uninitialized and kind != "LEASE_ISSUED":
            self._state_roots.pop(scope, None)
        self._nonces.add(body["nonce"])
        self._head = envelope["receipt_id"]
        self._next_sequence += 1
        self._last_timestamp = timestamp
        self._last_receipt_registry_version = registry_version
        self._last_receipt_registry_root = registry_root

    def _require_lease_receipt_binding(
        self,
        lease: _LeaseState | None,
        bindings: ReceiptBindings,
        body: Mapping[str, Any],
        *,
        current_fence: bool = True,
        permit_inactive: bool = False,
    ) -> None:
        if lease is None or (not lease.active and not permit_inactive):
            _fail("LEASE_MISSING")
        if not self._same_bindings(lease.bindings, bindings):
            _fail("LEASE_IDENTITY_BINDING_MISMATCH")
        if lease.lease_id != body["lease_id"]:
            _fail("LEASE_ID_MISMATCH")
        if current_fence:
            if lease.generation != int(body["lease_generation"]):
                _fail("LEASE_GENERATION_STALE")
            if lease.fencing_token != body["fencing_token"]:
                _fail("STALE_FENCING_TOKEN")

    def _result_digest(self, kind: str, outcome: str, denial_codes: Sequence[str], nonce: str) -> str:
        return _domain_hash("AEGIS_AUTHORITATIVE_RECEIPT_RESULT_V1", {
            "receipt_kind": kind,
            "outcome": outcome,
            "denial_codes": list(denial_codes),
            "nonce": nonce,
        })

    def _body(
        self,
        *,
        kind: str,
        bindings: ReceiptBindings,
        lease_id: str,
        lease_generation: int,
        fencing_token: str,
        authority_receipt_hash: str,
        lease_authorization_receipt_hash: str,
        observed_state_root: str,
        expected_state_root: str,
        action_digest: str,
        after_state_root: str,
        timestamp_ms: str,
        expires_at_ms: str,
        nonce: str,
        denial_codes: Iterable[str],
        result_digest: str | None = None,
    ) -> dict[str, Any]:
        bindings.validate()
        codes = tuple(sorted(set(denial_codes), key=lambda item: item.encode("utf-8")))
        outcome = EXPECTED_OUTCOME[kind]
        return {
            "receipt_sequence": str(self._next_sequence),
            "actor_identity_root": bindings.actor_identity_root,
            "session_identity_root": bindings.session_identity_root,
            "workspace_identity_root": bindings.workspace_identity_root,
            "holon_identity_root": bindings.holon_identity_root,
            "authority_domain": bindings.authority_domain,
            "authority_level": bindings.authority_level,
            "authority_receipt_hash": authority_receipt_hash,
            "lease_id": lease_id,
            "lease_generation": str(lease_generation),
            "fencing_token": fencing_token,
            "lease_authorization_receipt_hash": lease_authorization_receipt_hash,
            "parent_receipt_hash": self._head,
            "observed_state_root": observed_state_root,
            "expected_state_root": expected_state_root,
            "action_digest": action_digest,
            "before_state_root": observed_state_root,
            "after_state_root": after_state_root,
            "result_digest": (
                self._result_digest(kind, outcome, codes, nonce)
                if result_digest is None
                else _hash("result_digest", result_digest, nonzero=True)
            ),
            "timestamp_ms": _decimal("timestamp_ms", timestamp_ms),
            "expires_at_ms": _decimal("expires_at_ms", expires_at_ms),
            "nonce": nonce,
            "outcome": outcome,
            "denial_codes": list(codes),
        }

    def _persist_then_apply(self, kind: str, body: Mapping[str, Any]) -> dict[str, Any]:
        envelope = sign_receipt(
            receipt_kind=kind,
            receipt_body=body,
            registry=self._current_registry,
            signer_key_id=self._signer_key_id,
            signer_private_key_hex=self._signer_private_key_hex,
        )
        verify_receipt(
            envelope,
            registry=self._current_registry,
            verification_time_ms=self._verification_time_ms,
            max_clock_skew_ms=self._max_clock_skew_ms,
        )
        snapshot = self._state_snapshot()
        try:
            self._apply_verified_receipt(envelope)
        finally:
            self._restore_state_snapshot(snapshot)
        self._store.persist_receipt(
            envelope,
            registry=self._current_registry,
            verification_time_ms=self._verification_time_ms,
            max_clock_skew_ms=self._max_clock_skew_ms,
        )
        # The store validates the pending bytes before committing. If process
        # memory fails after this point, restart replays the authenticated row.
        self._apply_verified_receipt(envelope)
        return envelope

    def _state_snapshot(self) -> tuple[Any, ...]:
        return (
            self._head,
            self._next_sequence,
            self._last_timestamp,
            copy.deepcopy(self._state_roots),
            copy.deepcopy(self._leases),
            copy.deepcopy(self._lease_ids),
            copy.deepcopy(self._generations),
            copy.deepcopy(self._mutations),
            copy.deepcopy(self._consumed_actions),
            copy.deepcopy(self._nonces),
            self._last_receipt_registry_version,
            self._last_receipt_registry_root,
        )

    def _restore_state_snapshot(self, snapshot: tuple[Any, ...]) -> None:
        (
            self._head,
            self._next_sequence,
            self._last_timestamp,
            self._state_roots,
            self._leases,
            self._lease_ids,
            self._generations,
            self._mutations,
            self._consumed_actions,
            self._nonces,
            self._last_receipt_registry_version,
            self._last_receipt_registry_root,
        ) = snapshot

    def _actual_state(self, bindings: ReceiptBindings, observed_state_root: str) -> str:
        observed = _hash("observed_state_root", observed_state_root, nonzero=True)
        return self._state_roots.get(self._scope(bindings), observed)

    def _decision_time(self, timestamp_ms: str) -> int:
        """Use explicit trusted observation time for live lease decisions.

        The receipt timestamp remains caller supplied and signed, but a
        backdated value cannot revive a lease that is expired at the
        authority's separately supplied monotonic observation time.
        """

        timestamp = int(_decimal("timestamp_ms", timestamp_ms))
        return max(timestamp, int(self._verification_time_ms))

    def issue_lease(
        self,
        *,
        bindings: ReceiptBindings,
        lease_id: str,
        observed_state_root: str,
        expected_state_root: str,
        action_digest: str,
        timestamp_ms: str,
        expires_at_ms: str,
        nonce: str,
    ) -> dict[str, Any]:
        with self._lock:
            _hash("lease_id", lease_id, nonzero=True)
            expected = _hash("expected_state_root", expected_state_root, nonzero=True)
            action = _hash("action_digest", action_digest, nonzero=True)
            _nonce(nonce)
            timestamp = int(_decimal("timestamp_ms", timestamp_ms))
            decision_time = self._decision_time(timestamp_ms)
            expires = int(_decimal("expires_at_ms", expires_at_ms))
            actual = self._actual_state(bindings, observed_state_root)
            scope = self._scope(bindings)
            reasons: list[str] = []
            if self._state_roots.get(scope) not in (None, observed_state_root):
                reasons.append("OBSERVED_STATE_STALE")
            active = self._leases.get(scope)
            if active is not None and active.active:
                reasons.append(
                    "LEASE_EXPIRED" if int(self._verification_time_ms) >= active.expires_at_ms
                    else "WRITER_ALREADY_ACTIVE"
                )
            if lease_id in self._lease_ids:
                reasons.append("LEASE_ID_REPLAY")
            if expected != actual:
                reasons.append("EXPECTED_STATE_STALE")
            if expires <= decision_time:
                reasons.append("LEASE_EXPIRY_INVALID")
            generation = self._generations.get(scope, 0) + 1
            kind = "LEASE_ISSUANCE_DENIED" if reasons else "LEASE_ISSUED"
            fence = ZERO_HASH if reasons else _domain_hash("AEGIS_AUTHORITATIVE_FENCE_V1", {
                "authority_domain": bindings.authority_domain,
                "lease_id": lease_id,
                "lease_generation": str(generation),
                "parent_receipt_hash": self._head,
                "nonce": nonce,
            })
            body = self._body(
                kind=kind, bindings=bindings, lease_id=lease_id, lease_generation=generation,
                fencing_token=fence, authority_receipt_hash=ZERO_HASH,
                lease_authorization_receipt_hash=ZERO_HASH, observed_state_root=actual,
                expected_state_root=expected, action_digest=action, after_state_root=actual,
                timestamp_ms=timestamp_ms, expires_at_ms=expires_at_ms, nonce=nonce,
                denial_codes=reasons,
            )
            return self._persist_then_apply(kind, body)

    def renew_lease(
        self,
        *,
        bindings: ReceiptBindings,
        lease_id: str,
        lease_generation: str,
        fencing_token: str,
        observed_state_root: str,
        expected_state_root: str,
        action_digest: str,
        timestamp_ms: str,
        expires_at_ms: str,
        nonce: str,
    ) -> dict[str, Any]:
        with self._lock:
            presented_generation = _decimal_int("lease_generation", lease_generation)
            _hash("fencing_token", fencing_token, nonzero=True)
            _nonce(nonce)
            actual = self._actual_state(bindings, observed_state_root)
            lease = self._leases.get(self._scope(bindings))
            timestamp = int(_decimal("timestamp_ms", timestamp_ms))
            decision_time = self._decision_time(timestamp_ms)
            new_expiry = int(_decimal("expires_at_ms", expires_at_ms))
            reasons = self._lease_reasons(
                lease, bindings, lease_id, presented_generation, fencing_token,
                expected_state_root, actual, decision_time,
            )
            if lease is not None and new_expiry <= lease.expires_at_ms:
                reasons.append("LEASE_RENEWAL_NOT_EXTENDED")
            if new_expiry <= decision_time:
                reasons.append("LEASE_EXPIRY_INVALID")
            kind = "LEASE_RENEWAL_DENIED" if reasons else "LEASE_RENEWED"
            next_generation = presented_generation if reasons else presented_generation + 1
            next_fence = fencing_token if reasons else _domain_hash("AEGIS_AUTHORITATIVE_FENCE_V1", {
                "authority_domain": bindings.authority_domain,
                "lease_id": lease_id,
                "lease_generation": str(next_generation),
                "parent_receipt_hash": self._head,
                "nonce": nonce,
            })
            body = self._body(
                kind=kind, bindings=bindings, lease_id=lease_id, lease_generation=next_generation,
                fencing_token=next_fence, authority_receipt_hash=ZERO_HASH,
                lease_authorization_receipt_hash=ZERO_HASH, observed_state_root=actual,
                expected_state_root=_hash("expected_state_root", expected_state_root, nonzero=True),
                action_digest=_hash("action_digest", action_digest, nonzero=True), after_state_root=actual,
                timestamp_ms=timestamp_ms, expires_at_ms=expires_at_ms, nonce=nonce,
                denial_codes=reasons,
            )
            return self._persist_then_apply(kind, body)

    def _lease_reasons(
        self,
        lease: _LeaseState | None,
        bindings: ReceiptBindings,
        lease_id: str,
        generation: int,
        fence: str,
        expected_state_root: str,
        actual_state_root: str,
        timestamp: int,
        *,
        permit_expired: bool = False,
        permit_inactive: bool = False,
    ) -> list[str]:
        reasons: list[str] = []
        if lease is None or (not lease.active and not permit_inactive):
            return ["LEASE_MISSING"]
        if lease.bindings != bindings:
            reasons.append("AMBIGUOUS_ACTOR_SESSION_BINDING")
        if lease.lease_id != lease_id:
            reasons.append("LEASE_ID_MISMATCH")
        if lease.generation != generation:
            reasons.append("STALE_LEASE_GENERATION")
        if lease.fencing_token != fence:
            reasons.append("STALE_FENCING_TOKEN")
        if _hash("expected_state_root", expected_state_root, nonzero=True) != actual_state_root:
            reasons.append("EXPECTED_STATE_STALE")
        if not permit_expired and timestamp >= lease.expires_at_ms:
            reasons.append("LEASE_EXPIRED")
        return reasons

    def expire_lease(
        self,
        *,
        bindings: ReceiptBindings,
        lease_id: str,
        lease_generation: str,
        fencing_token: str,
        observed_state_root: str,
        action_digest: str,
        timestamp_ms: str,
        nonce: str,
    ) -> dict[str, Any]:
        return self._close_lease(
            kind="LEASE_EXPIRED", bindings=bindings, lease_id=lease_id,
            lease_generation=lease_generation, fencing_token=fencing_token,
            observed_state_root=observed_state_root, action_digest=action_digest,
            timestamp_ms=timestamp_ms, nonce=nonce, denial_code="LEASE_EXPIRED",
        )

    def revoke_lease(
        self,
        *,
        bindings: ReceiptBindings,
        lease_id: str,
        lease_generation: str,
        fencing_token: str,
        observed_state_root: str,
        action_digest: str,
        timestamp_ms: str,
        nonce: str,
        reason: str = "OPERATOR_REVOKED",
    ) -> dict[str, Any]:
        return self._close_lease(
            kind="LEASE_REVOKED", bindings=bindings, lease_id=lease_id,
            lease_generation=lease_generation, fencing_token=fencing_token,
            observed_state_root=observed_state_root, action_digest=action_digest,
            timestamp_ms=timestamp_ms, nonce=nonce, denial_code=reason,
        )

    def _close_lease(
        self,
        *,
        kind: str,
        bindings: ReceiptBindings,
        lease_id: str,
        lease_generation: str,
        fencing_token: str,
        observed_state_root: str,
        action_digest: str,
        timestamp_ms: str,
        nonce: str,
        denial_code: str,
    ) -> dict[str, Any]:
        with self._lock:
            generation = _decimal_int("lease_generation", lease_generation)
            _hash("fencing_token", fencing_token, nonzero=True)
            _nonce(nonce)
            actual = self._actual_state(bindings, observed_state_root)
            lease = self._leases.get(self._scope(bindings))
            reasons = self._lease_reasons(
                lease, bindings, lease_id, generation, fencing_token, actual, actual,
                int(_decimal("timestamp_ms", timestamp_ms)), permit_expired=True,
            )
            if reasons:
                _fail(reasons[0])
            if kind == "LEASE_EXPIRED" and int(timestamp_ms) < lease.expires_at_ms:
                _fail("LEASE_NOT_EXPIRED")
            code = _safe_id("denial_code", denial_code)
            body = self._body(
                kind=kind, bindings=bindings, lease_id=lease_id, lease_generation=generation,
                fencing_token=fencing_token, authority_receipt_hash=ZERO_HASH,
                lease_authorization_receipt_hash=ZERO_HASH, observed_state_root=actual,
                expected_state_root=actual, action_digest=_hash("action_digest", action_digest, nonzero=True),
                after_state_root=actual, timestamp_ms=timestamp_ms,
                expires_at_ms=str(lease.expires_at_ms), nonce=nonce, denial_codes=(code,),
            )
            return self._persist_then_apply(kind, body)

    def admit_mutation(
        self,
        *,
        bindings: ReceiptBindings,
        lease_id: str,
        lease_generation: str,
        fencing_token: str,
        authority_receipt_hash: str,
        lease_authorization_receipt_hash: str,
        observed_state_root: str,
        expected_state_root: str,
        action_digest: str,
        timestamp_ms: str,
        nonce: str,
    ) -> dict[str, Any]:
        with self._lock:
            generation = _decimal_int("lease_generation", lease_generation)
            _hash("fencing_token", fencing_token, nonzero=True)
            _hash("authority_receipt_hash", authority_receipt_hash, nonzero=True)
            _hash("lease_authorization_receipt_hash", lease_authorization_receipt_hash, nonzero=True)
            action = _hash("action_digest", action_digest, nonzero=True)
            _nonce(nonce)
            actual = self._actual_state(bindings, observed_state_root)
            scope = self._scope(bindings)
            lease = self._leases.get(scope)
            timestamp = int(_decimal("timestamp_ms", timestamp_ms))
            reasons = self._lease_reasons(
                lease, bindings, lease_id, generation, fencing_token,
                expected_state_root, actual, self._decision_time(timestamp_ms),
            )
            if self._state_roots.get(scope) != observed_state_root:
                reasons.append("OBSERVED_STATE_STALE")
            if lease is not None and lease_authorization_receipt_hash != lease.authorization_receipt_hash:
                reasons.append("LEASE_AUTHORIZATION_RECEIPT_MISMATCH")
            if self._action_key(bindings, action) in self._consumed_actions:
                reasons.append("MUTATION_REPLAY")
            kind = "MUTATION_DENIED" if reasons else "MUTATION_ADMITTED"
            expiry = str(lease.expires_at_ms) if lease is not None else timestamp_ms
            body = self._body(
                kind=kind, bindings=bindings, lease_id=lease_id, lease_generation=generation,
                fencing_token=fencing_token, authority_receipt_hash=authority_receipt_hash,
                lease_authorization_receipt_hash=lease_authorization_receipt_hash,
                observed_state_root=actual, expected_state_root=_hash("expected_state_root", expected_state_root, nonzero=True),
                action_digest=action, after_state_root=actual, timestamp_ms=timestamp_ms,
                expires_at_ms=expiry, nonce=nonce, denial_codes=reasons,
            )
            return self._persist_then_apply(kind, body)

    def deny_mutation(
        self,
        *,
        bindings: ReceiptBindings,
        lease_id: str,
        lease_generation: str,
        fencing_token: str,
        authority_receipt_hash: str,
        lease_authorization_receipt_hash: str,
        observed_state_root: str,
        expected_state_root: str,
        action_digest: str,
        timestamp_ms: str,
        expires_at_ms: str,
        nonce: str,
        denial_codes: Sequence[str],
        result_digest: str,
    ) -> dict[str, Any]:
        with self._lock:
            if not denial_codes:
                _fail("denial_codes:REQUIRED")
            actual = self._actual_state(bindings, observed_state_root)
            body = self._body(
                kind="MUTATION_DENIED", bindings=bindings, lease_id=_hash("lease_id", lease_id, nonzero=True),
                lease_generation=_decimal_int("lease_generation", lease_generation),
                fencing_token=_hash("fencing_token", fencing_token, nonzero=True),
                authority_receipt_hash=_hash("authority_receipt_hash", authority_receipt_hash, nonzero=True),
                lease_authorization_receipt_hash=_hash(
                    "lease_authorization_receipt_hash", lease_authorization_receipt_hash, nonzero=True,
                ),
                observed_state_root=actual, expected_state_root=_hash("expected_state_root", expected_state_root, nonzero=True),
                action_digest=_hash("action_digest", action_digest, nonzero=True), after_state_root=actual,
                timestamp_ms=timestamp_ms, expires_at_ms=expires_at_ms, nonce=nonce,
                denial_codes=denial_codes, result_digest=result_digest,
            )
            return self._persist_then_apply("MUTATION_DENIED", body)

    def complete_mutation(self, **kwargs: Any) -> dict[str, Any]:
        after_state_root = kwargs.pop("after_state_root")
        return self._terminal_mutation("MUTATION_COMPLETED", after_state_root=after_state_root, denial_codes=(), **kwargs)

    def cancel_mutation(self, *, denial_code: str = "MUTATION_CANCELLED", **kwargs: Any) -> dict[str, Any]:
        return self._terminal_mutation("MUTATION_CANCELLED", denial_codes=(denial_code,), **kwargs)

    def fail_mutation(self, *, denial_code: str = "MUTATION_FAILED", **kwargs: Any) -> dict[str, Any]:
        return self._terminal_mutation("MUTATION_FAILED", denial_codes=(denial_code,), **kwargs)

    def _terminal_mutation(
        self,
        kind: str,
        *,
        bindings: ReceiptBindings,
        lease_id: str,
        lease_generation: str,
        fencing_token: str,
        authority_receipt_hash: str,
        lease_authorization_receipt_hash: str,
        observed_state_root: str,
        expected_state_root: str,
        action_digest: str,
        timestamp_ms: str,
        nonce: str,
        result_digest: str,
        after_state_root: str | None = None,
        denial_codes: Sequence[str],
    ) -> dict[str, Any]:
        with self._lock:
            generation = _decimal_int("lease_generation", lease_generation)
            actual = self._actual_state(bindings, observed_state_root)
            lease = self._leases.get(self._scope(bindings))
            reasons = self._lease_reasons(
                lease, bindings, lease_id, generation, fencing_token,
                expected_state_root, actual, self._decision_time(timestamp_ms),
                permit_expired=kind in ("MUTATION_CANCELLED", "MUTATION_FAILED"),
                permit_inactive=kind in ("MUTATION_CANCELLED", "MUTATION_FAILED"),
            )
            if reasons:
                _fail(reasons[0])
            action = _hash("action_digest", action_digest, nonzero=True)
            mutation = self._mutations.get(self._action_key(bindings, action))
            if mutation is None or mutation.status != "ADMITTED":
                _fail("MUTATION_ADMISSION_MISSING_OR_TERMINAL")
            if (
                mutation.lease_id != lease_id
                or mutation.generation != generation
                or mutation.fencing_token != fencing_token
                or mutation.authority_receipt_hash != authority_receipt_hash
                or mutation.lease_authorization_receipt_hash != lease_authorization_receipt_hash
            ):
                _fail("MUTATION_TERMINAL_BINDING_MISMATCH")
            after = actual if kind != "MUTATION_COMPLETED" else _hash(
                "after_state_root", after_state_root, nonzero=True,
            )
            body = self._body(
                kind=kind, bindings=bindings, lease_id=lease_id, lease_generation=generation,
                fencing_token=fencing_token,
                authority_receipt_hash=_hash("authority_receipt_hash", authority_receipt_hash, nonzero=True),
                lease_authorization_receipt_hash=_hash(
                    "lease_authorization_receipt_hash", lease_authorization_receipt_hash, nonzero=True,
                ),
                observed_state_root=actual, expected_state_root=_hash("expected_state_root", expected_state_root),
                action_digest=action, after_state_root=after,
                timestamp_ms=timestamp_ms, expires_at_ms=str(lease.expires_at_ms), nonce=nonce,
                denial_codes=denial_codes, result_digest=result_digest,
            )
            return self._persist_then_apply(kind, body)


__all__ = [
    "AuthoritativeReceiptAuthority",
    "AuthoritativeReceiptError",
    "ED25519",
    "ReceiptBindings",
    "ReceiptStoreConflict",
    "SQLiteReceiptStore",
    "VerifiedTrustRegistry",
    "ZERO_HASH",
    "assert_i_json",
    "canonical_receipt_signature_message",
    "canonical_registry_signature_message",
    "compute_receipt_id",
    "compute_registry_root",
    "create_trust_registry",
    "load_json_strict",
    "public_key_hex_from_private",
    "sign_receipt",
    "verify_receipt",
    "verify_registry_rotation",
    "verify_trust_registry",
]
