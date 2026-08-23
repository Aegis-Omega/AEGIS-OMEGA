"""Cryptographic verifier for AEGIS authorization-time operator evidence.

This module does not define a new authorization decision type. It verifies a
narrow profile composed from two existing AEGIS contracts:

* merged Scale OS Signed Control-Plane Event V1 for the JCS + Ed25519 envelope;
* PR #268 serialized DECISION_RECEIPT_V1 semantics for the decision source.

The inherited Scale OS envelope verifies a signature under a public key carried
inside the envelope. That establishes key possession, not operator trust. This
verifier therefore requires an external trust policy that binds signer key id,
Ed25519 public key, operator actor identity and operator executor identity.

The resulting AuthorizationTimeEvidenceReceipt is evidence-only. It does not
perform AEGIS admission, execute an action, or prove an external effect.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from harness.sdk.sovereign_execution import canonical_hash

SCHEMA_VERSION = "1.0.0"
AUTHORIZATION_TIME_EVIDENCE_VERIFIED = "AUTHORIZATION_TIME_EVIDENCE_VERIFIED"
RECEIPT_KIND = "AEGIS_AUTHORIZATION_TIME_EVIDENCE_RECEIPT_V1"
TRUST_POLICY_KIND = "AEGIS_AUTHORIZATION_TIME_TRUST_POLICY_V1"
RECEIPT_DOMAIN = "AEGIS_AUTHORIZATION_TIME_EVIDENCE_RECEIPT_V1"
DECISION_RECEIPT_KIND = "DECISION_RECEIPT_V1"
DECISION_RECEIPT_DOMAIN = "AEGIS_DECISION_RECEIPT_V1"
PERMIT = "PERMIT"
APPROVAL_GRANTED = "APPROVAL_GRANTED"
APPROVAL_PROFILE = "AEGIS_AUTHORIZATION_APPROVAL_V1"
APPROVED = "APPROVED"
SCALE_OS_SOURCE_DOMAIN = "AEGIS_SCALE_OS_SOURCE_OBJECT_V1"
SCALE_OS_PAYLOAD_DOMAIN = "AEGIS_SCALE_OS_EVENT_PAYLOAD_V1"
SCALE_OS_UNSIGNED_EVENT_DOMAIN = "AEGIS_SCALE_OS_EVENT_ENVELOPE_V1"
SCALE_OS_SIGNED_EVENT_DOMAIN = "AEGIS_SCALE_OS_SIGNED_EVENT_V1"
ALLOWED_ACTION_CLASSES = frozenset(("D3", "D4"))
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ED25519_PUBLIC_RE = re.compile(r"^[0-9a-f]{64}$")
ED25519_SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+\-]{0,255}$")
EVENT_KEYS = frozenset((
    "schema_version", "event_id", "event_type", "aggregate_id", "sequence",
    "previous_event_hash", "idempotency_key", "correlation_id", "causation_id",
    "emitted_at", "identities", "signer_key_id", "signer_public_key",
    "source_object_hash", "payload_hash", "signature",
))
IDENTITIES_KEYS = frozenset(("request", "approval", "execution", "verification"))
ROLE_IDENTITY_KEYS = frozenset(("actor_id", "session_id", "executor_id"))
DECISION_KEYS = frozenset(("receipt_kind", "transition_id", "decision_outcome", "policy_decision_root"))
PAYLOAD_KEYS = frozenset((
    "profile", "state", "approval_reference", "authority_domain", "action_class",
    "valid_through_generation", "decision_receipt_root",
))
TRUST_KEY_KEYS = frozenset(("key_id", "public_key_hex", "actor_id", "executor_id"))


class AuthorizationTimeEvidenceError(ValueError):
    """Fail-closed authorization-time verification error."""


def _string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise AuthorizationTimeEvidenceError(code)
    return value


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise AuthorizationTimeEvidenceError(code)
    return value


def _integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuthorizationTimeEvidenceError(code)
    return value


def _jcs(value: Any, code: str) -> bytes:
    try:
        return rfc8785.dumps(value)
    except Exception as exc:
        raise AuthorizationTimeEvidenceError(code) from exc


def _jcs_hash(value: Any, code: str) -> str:
    return hashlib.sha256(_jcs(value, code)).hexdigest()


def _parse_epoch(value: Any) -> int:
    if not isinstance(value, str) or not value:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_EMITTED_AT_INVALID")
    try:
        if value.endswith("Z"):
            parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        else:
            parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError("timestamp must be UTC")
        return int(parsed.timestamp())
    except Exception as exc:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_EMITTED_AT_INVALID") from exc


def _strict_mapping(value: Any, keys: frozenset[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or frozenset(value.keys()) != keys:
        raise AuthorizationTimeEvidenceError(code)
    return value


@dataclass(frozen=True)
class TrustedOperatorKey:
    key_id: str
    public_key_hex: str
    actor_id: str
    executor_id: str


@dataclass(frozen=True)
class AuthorizationTimeTrustPolicy:
    schema_version: str
    policy_id: str
    trusted_operator_keys: tuple[TrustedOperatorKey, ...]
    max_event_age_seconds: int
    max_future_skew_seconds: int
    allowed_action_classes: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuthorizationTimeTrustPolicy":
        if not isinstance(value, Mapping):
            raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRUST_POLICY_NOT_OBJECT")
        if value.get("schema_version") != SCHEMA_VERSION:
            raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRUST_POLICY_SCHEMA_UNSUPPORTED")
        policy_id = _string(value.get("policy_id"), "AUTHZ_TIME_TRUST_POLICY_ID_INVALID")
        raw_keys = value.get("trusted_operator_keys")
        if not isinstance(raw_keys, list) or not raw_keys:
            raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRUSTED_KEYS_INVALID")
        trusted: list[TrustedOperatorKey] = []
        seen_ids: set[str] = set()
        seen_public: set[str] = set()
        for raw in raw_keys:
            if not isinstance(raw, Mapping) or frozenset(raw.keys()) != TRUST_KEY_KEYS:
                raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRUSTED_KEYS_INVALID")
            key_id = _string(raw.get("key_id"), "AUTHZ_TIME_TRUSTED_KEYS_INVALID")
            public_key_hex = raw.get("public_key_hex")
            actor_id = _string(raw.get("actor_id"), "AUTHZ_TIME_TRUSTED_KEYS_INVALID")
            executor_id = _string(raw.get("executor_id"), "AUTHZ_TIME_TRUSTED_KEYS_INVALID")
            if not isinstance(public_key_hex, str) or not ED25519_PUBLIC_RE.fullmatch(public_key_hex):
                raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRUSTED_KEYS_INVALID")
            if key_id in seen_ids or public_key_hex in seen_public:
                raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRUSTED_KEYS_INVALID")
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            except Exception as exc:
                raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRUSTED_KEYS_INVALID") from exc
            seen_ids.add(key_id)
            seen_public.add(public_key_hex)
            trusted.append(TrustedOperatorKey(key_id, public_key_hex, actor_id, executor_id))

        max_age = _integer(value.get("max_event_age_seconds"), "AUTHZ_TIME_MAX_EVENT_AGE_INVALID")
        max_future = _integer(value.get("max_future_skew_seconds"), "AUTHZ_TIME_MAX_FUTURE_SKEW_INVALID")
        if max_age <= 0 or max_future < 0 or max_future > 300:
            raise AuthorizationTimeEvidenceError("AUTHZ_TIME_FRESHNESS_POLICY_INVALID")
        raw_classes = value.get("allowed_action_classes")
        if not isinstance(raw_classes, list) or not raw_classes:
            raise AuthorizationTimeEvidenceError("AUTHZ_TIME_ALLOWED_ACTION_CLASSES_INVALID")
        if any(not isinstance(item, str) or item not in ALLOWED_ACTION_CLASSES for item in raw_classes):
            raise AuthorizationTimeEvidenceError("AUTHZ_TIME_ALLOWED_ACTION_CLASSES_INVALID")
        if len(set(raw_classes)) != len(raw_classes):
            raise AuthorizationTimeEvidenceError("AUTHZ_TIME_ALLOWED_ACTION_CLASSES_INVALID")
        return cls(
            schema_version=SCHEMA_VERSION,
            policy_id=policy_id,
            trusted_operator_keys=tuple(trusted),
            max_event_age_seconds=max_age,
            max_future_skew_seconds=max_future,
            allowed_action_classes=tuple(raw_classes),
        )

    @property
    def root(self) -> str:
        return canonical_hash(
            TRUST_POLICY_KIND,
            {
                "schema_version": self.schema_version,
                "policy_id": self.policy_id,
                "trusted_operator_keys": [asdict(item) for item in self.trusted_operator_keys],
                "max_event_age_seconds": self.max_event_age_seconds,
                "max_future_skew_seconds": self.max_future_skew_seconds,
                "allowed_action_classes": list(self.allowed_action_classes),
            },
        )


@dataclass(frozen=True)
class AuthorizationTimeEvidenceReceipt:
    schema_version: str
    receipt_kind: str
    outcome: str
    authorization_time_verified: bool
    transition_id: str
    policy_decision_root: str
    decision_receipt_root: str
    approval_reference: str
    authority_domain: str
    action_class: str
    valid_through_generation: int
    approval_actor_id: str
    approval_session_id: str
    approval_executor_id: str
    signer_key_id: str
    signer_public_key_sha256: str
    source_object_sha256: str
    payload_sha256: str
    signed_event_sha256: str
    event_emitted_at_epoch: int
    verification_time_epoch: int
    trust_policy_root: str
    authority_granted: bool
    receipt_root: str


def _select_trusted_key(policy: AuthorizationTimeTrustPolicy, event: Mapping[str, Any]) -> TrustedOperatorKey:
    key_id = _string(event.get("signer_key_id"), "AUTHZ_TIME_SIGNER_KEY_UNTRUSTED")
    presented = event.get("signer_public_key")
    if not isinstance(presented, str) or not ED25519_PUBLIC_RE.fullmatch(presented):
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_SIGNER_KEY_UNTRUSTED")
    matches = [item for item in policy.trusted_operator_keys if item.key_id == key_id]
    if len(matches) != 1 or matches[0].public_key_hex != presented:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_SIGNER_KEY_UNTRUSTED")
    return matches[0]


def _verify_event_shape(event: Mapping[str, Any], *, expected_transition_id: str, expected_approval_reference: str) -> None:
    _strict_mapping(event, EVENT_KEYS, "AUTHZ_TIME_EVENT_INVALID")
    if event.get("schema_version") != SCHEMA_VERSION:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_EVENT_SCHEMA_UNSUPPORTED")
    if event.get("event_type") != APPROVAL_GRANTED:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_EVENT_TYPE_INVALID")
    if event.get("aggregate_id") != expected_approval_reference:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_APPROVAL_REFERENCE_MISMATCH")
    if event.get("correlation_id") != expected_transition_id:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRANSITION_MISMATCH")
    for field in ("event_id", "aggregate_id", "sequence", "idempotency_key", "correlation_id", "signer_key_id"):
        _string(event.get(field), "AUTHZ_TIME_EVENT_INVALID")
    previous = event.get("previous_event_hash")
    if previous is not None:
        _hash(previous, "AUTHZ_TIME_EVENT_INVALID")
    causation = event.get("causation_id")
    if causation is not None:
        _string(causation, "AUTHZ_TIME_EVENT_INVALID")
    _hash(event.get("source_object_hash"), "AUTHZ_TIME_EVENT_INVALID")
    _hash(event.get("payload_hash"), "AUTHZ_TIME_EVENT_INVALID")
    signature = event.get("signature")
    if not isinstance(signature, str) or not ED25519_SIGNATURE_RE.fullmatch(signature):
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_SIGNATURE_INVALID")


def _approval_identity(event: Mapping[str, Any], trusted: TrustedOperatorKey) -> Mapping[str, Any]:
    identities = _strict_mapping(event.get("identities"), IDENTITIES_KEYS, "AUTHZ_TIME_IDENTITIES_INVALID")
    request = _strict_mapping(identities.get("request"), ROLE_IDENTITY_KEYS, "AUTHZ_TIME_IDENTITIES_INVALID")
    approval = _strict_mapping(identities.get("approval"), ROLE_IDENTITY_KEYS, "AUTHZ_TIME_IDENTITIES_INVALID")
    if identities.get("execution") is not None or identities.get("verification") is not None:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_IDENTITIES_INVALID")
    for role in (request, approval):
        for field in ROLE_IDENTITY_KEYS:
            _string(role.get(field), "AUTHZ_TIME_IDENTITIES_INVALID")
    if request == approval:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_IDENTITIES_INVALID")
    if approval.get("actor_id") != trusted.actor_id or approval.get("executor_id") != trusted.executor_id:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_OPERATOR_IDENTITY_MISMATCH")
    return approval


def _verify_decision_receipt(
    source: Mapping[str, Any],
    *,
    expected_transition_id: str,
    expected_policy_decision_root: str,
) -> str:
    _strict_mapping(source, DECISION_KEYS, "AUTHZ_TIME_DECISION_RECEIPT_INVALID")
    if source.get("receipt_kind") != DECISION_RECEIPT_KIND or source.get("decision_outcome") != PERMIT:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_DECISION_RECEIPT_INVALID")
    transition_id = _hash(source.get("transition_id"), "AUTHZ_TIME_DECISION_RECEIPT_INVALID")
    policy_root = _hash(source.get("policy_decision_root"), "AUTHZ_TIME_DECISION_RECEIPT_INVALID")
    if transition_id != expected_transition_id:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRANSITION_MISMATCH")
    if policy_root != expected_policy_decision_root:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_POLICY_DECISION_MISMATCH")
    return canonical_hash(DECISION_RECEIPT_DOMAIN, dict(source))


def verify_authorization_time_evidence(
    *,
    signed_event: Mapping[str, Any],
    source_object: Mapping[str, Any],
    payload: Mapping[str, Any],
    trust_policy: AuthorizationTimeTrustPolicy,
    expected_transition_id: str,
    expected_policy_decision_root: str,
    expected_approval_reference: str,
    expected_authority_domain: str,
    expected_action_class: str,
    current_generation: int,
    verification_time_epoch: int,
) -> AuthorizationTimeEvidenceReceipt:
    if not isinstance(trust_policy, AuthorizationTimeTrustPolicy):
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_TRUST_POLICY_INVALID")
    if not isinstance(signed_event, Mapping):
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_EVENT_INVALID")
    if not isinstance(source_object, Mapping):
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_DECISION_RECEIPT_INVALID")
    if not isinstance(payload, Mapping):
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_PAYLOAD_INVALID")

    transition_id = _hash(expected_transition_id, "AUTHZ_TIME_EXPECTED_TRANSITION_INVALID")
    policy_decision_root = _hash(expected_policy_decision_root, "AUTHZ_TIME_EXPECTED_POLICY_DECISION_INVALID")
    approval_reference = _string(expected_approval_reference, "AUTHZ_TIME_EXPECTED_APPROVAL_REFERENCE_INVALID")
    authority_domain = _string(expected_authority_domain, "AUTHZ_TIME_EXPECTED_AUTHORITY_DOMAIN_INVALID")
    action_class = _string(expected_action_class, "AUTHZ_TIME_EXPECTED_ACTION_CLASS_INVALID")
    if action_class not in trust_policy.allowed_action_classes:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_ACTION_CLASS_NOT_ALLOWED")
    generation = _integer(current_generation, "AUTHZ_TIME_CURRENT_GENERATION_INVALID")
    now = _integer(verification_time_epoch, "AUTHZ_TIME_VERIFICATION_TIME_INVALID")
    if generation < 0 or now < 0:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_VERIFIER_INPUT_INVALID")

    event = dict(signed_event)
    _verify_event_shape(event, expected_transition_id=transition_id, expected_approval_reference=approval_reference)
    trusted = _select_trusted_key(trust_policy, event)
    approval_identity = _approval_identity(event, trusted)

    expected_source_hash = _jcs_hash(
        {"domain": SCALE_OS_SOURCE_DOMAIN, "source_object": dict(source_object)},
        "AUTHZ_TIME_SOURCE_CANONICALIZATION_FAILED",
    )
    if event.get("source_object_hash") != expected_source_hash:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_SOURCE_HASH_MISMATCH")
    expected_payload_hash = _jcs_hash(
        {"domain": SCALE_OS_PAYLOAD_DOMAIN, "payload": dict(payload)},
        "AUTHZ_TIME_PAYLOAD_CANONICALIZATION_FAILED",
    )
    if event.get("payload_hash") != expected_payload_hash:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_PAYLOAD_HASH_MISMATCH")

    signature_hex = event["signature"]
    unsigned = dict(event)
    del unsigned["signature"]
    signing_input = _jcs(
        {"domain": SCALE_OS_UNSIGNED_EVENT_DOMAIN, "envelope": unsigned},
        "AUTHZ_TIME_EVENT_CANONICALIZATION_FAILED",
    )
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted.public_key_hex))
        key.verify(bytes.fromhex(signature_hex), signing_input)
    except InvalidSignature as exc:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_SIGNATURE_INVALID") from exc
    except AuthorizationTimeEvidenceError:
        raise
    except Exception as exc:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_SIGNATURE_INVALID") from exc

    decision_receipt_root = _verify_decision_receipt(
        source_object,
        expected_transition_id=transition_id,
        expected_policy_decision_root=policy_decision_root,
    )

    _strict_mapping(payload, PAYLOAD_KEYS, "AUTHZ_TIME_PAYLOAD_INVALID")
    if payload.get("profile") != APPROVAL_PROFILE or payload.get("state") != APPROVED:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_PAYLOAD_INVALID")
    if payload.get("decision_receipt_root") != decision_receipt_root:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_DECISION_ROOT_MISMATCH")
    if payload.get("approval_reference") != approval_reference:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_APPROVAL_REFERENCE_MISMATCH")
    if payload.get("authority_domain") != authority_domain:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_AUTHORITY_DOMAIN_MISMATCH")
    if payload.get("action_class") != action_class:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_ACTION_CLASS_MISMATCH")
    valid_through = _integer(payload.get("valid_through_generation"), "AUTHZ_TIME_VALID_THROUGH_GENERATION_INVALID")
    if valid_through < generation:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_APPROVAL_EXPIRED")

    event_epoch = _parse_epoch(event.get("emitted_at"))
    if event_epoch > now + trust_policy.max_future_skew_seconds:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_EVENT_FROM_FUTURE")
    if now - event_epoch > trust_policy.max_event_age_seconds:
        raise AuthorizationTimeEvidenceError("AUTHZ_TIME_EVENT_STALE")

    signed_event_sha256 = _jcs_hash(
        {"domain": SCALE_OS_SIGNED_EVENT_DOMAIN, "envelope": event},
        "AUTHZ_TIME_EVENT_CANONICALIZATION_FAILED",
    )
    trust_policy_root = trust_policy.root
    body = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "outcome": AUTHORIZATION_TIME_EVIDENCE_VERIFIED,
        "authorization_time_verified": True,
        "transition_id": transition_id,
        "policy_decision_root": policy_decision_root,
        "decision_receipt_root": decision_receipt_root,
        "approval_reference": approval_reference,
        "authority_domain": authority_domain,
        "action_class": action_class,
        "valid_through_generation": valid_through,
        "approval_actor_id": approval_identity["actor_id"],
        "approval_session_id": approval_identity["session_id"],
        "approval_executor_id": approval_identity["executor_id"],
        "signer_key_id": trusted.key_id,
        "signer_public_key_sha256": hashlib.sha256(bytes.fromhex(trusted.public_key_hex)).hexdigest(),
        "source_object_sha256": hashlib.sha256(_jcs(dict(source_object), "AUTHZ_TIME_SOURCE_CANONICALIZATION_FAILED")).hexdigest(),
        "payload_sha256": hashlib.sha256(_jcs(dict(payload), "AUTHZ_TIME_PAYLOAD_CANONICALIZATION_FAILED")).hexdigest(),
        "signed_event_sha256": signed_event_sha256,
        "event_emitted_at_epoch": event_epoch,
        "verification_time_epoch": now,
        "trust_policy_root": trust_policy_root,
        "authority_granted": False,
    }
    receipt_root = canonical_hash(RECEIPT_DOMAIN, body)
    return AuthorizationTimeEvidenceReceipt(**body, receipt_root=receipt_root)
