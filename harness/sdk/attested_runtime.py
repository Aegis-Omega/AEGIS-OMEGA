"""Provider-neutral attested-runtime binding for consequential execution.

This module encodes a narrow security boundary motivated by remote-attestation
and transparency designs, including the work-in-progress
``draft-hawkins-scitt-attested-agent-payment-01``:

    Key possession != approved software identity
    Authorization receipt != execution verification receipt

It deliberately does *not* parse or cryptographically verify EAT, COSE, SCITT,
TPM, TEE, or vendor attestation formats. ``verification_state=VERIFIED`` means
an upstream attestation verifier produced evidence under a separately governed
trust policy. This module checks exact subject/key/scope/measurement/freshness
bindings and emits a new execution-specific evidence receipt. It never grants
AEGIS authority.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from harness.sdk.principal_binding import VERIFIED, canonical_hash

SCHEMA_VERSION = "1.0.0"
EAT_KEY_BOUND = "EAT_KEY_BOUND"
ATTESTED_RUNTIME_VERIFIED = "ATTESTED_RUNTIME_VERIFIED"
RECEIPT_KIND = "AEGIS_EXECUTION_ATTESTATION_VERIFICATION_RECEIPT_V1"
TRUST_POLICY_KIND = "AEGIS_ATTESTED_RUNTIME_TRUST_POLICY_V1"
RECEIPT_DOMAIN = "AEGIS_EXECUTION_ATTESTATION_VERIFICATION_RECEIPT_V1"
KNOWN_ACTION_CLASSES = frozenset(("D0", "D1", "D2", "D3", "D4"))
KNOWN_ATTESTATION_PROFILES = frozenset((EAT_KEY_BOUND,))
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AttestedRuntimeError(ValueError):
    """Fail-closed attested-runtime validation error with stable codes."""


def _string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AttestedRuntimeError(code)
    return value


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise AttestedRuntimeError(code)
    return value


def _int(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AttestedRuntimeError(code)
    return value


def _string_tuple(value: Any, code: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise AttestedRuntimeError(code)
    items = tuple(value)
    if not allow_empty and not items:
        raise AttestedRuntimeError(code)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise AttestedRuntimeError(code)
    if len(items) != len(set(items)):
        raise AttestedRuntimeError(code)
    return items


@dataclass(frozen=True)
class EndorsedMeasurement:
    measurement_kind: str
    measurement_digest: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EndorsedMeasurement":
        if not isinstance(value, Mapping):
            raise AttestedRuntimeError("ENDORSED_MEASUREMENT_INVALID")
        return cls(
            measurement_kind=_string(value.get("measurement_kind"), "ENDORSED_MEASUREMENT_KIND_MISSING"),
            measurement_digest=_hash(value.get("measurement_digest"), "ENDORSED_MEASUREMENT_DIGEST_INVALID"),
        )


@dataclass(frozen=True)
class AttestedRuntimeTrustPolicy:
    schema_version: str
    policy_id: str
    required_action_classes: tuple[str, ...]
    allowed_attestation_profiles: tuple[str, ...]
    allowed_verifier_identities: tuple[str, ...]
    endorsed_measurements: tuple[EndorsedMeasurement, ...]
    authorization_scope_root: str
    max_evidence_age_seconds: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AttestedRuntimeTrustPolicy":
        if not isinstance(value, Mapping):
            raise AttestedRuntimeError("ATTESTED_RUNTIME_TRUST_POLICY_NOT_OBJECT")
        if value.get("schema_version") != SCHEMA_VERSION:
            raise AttestedRuntimeError("ATTESTED_RUNTIME_TRUST_POLICY_SCHEMA_UNSUPPORTED")

        required = _string_tuple(
            value.get("required_action_classes", ()),
            "ATTESTED_RUNTIME_REQUIRED_ACTION_CLASSES_INVALID",
            allow_empty=True,
        )
        if any(item not in KNOWN_ACTION_CLASSES for item in required):
            raise AttestedRuntimeError("ATTESTED_RUNTIME_ACTION_CLASS_UNKNOWN")

        profiles = _string_tuple(
            value.get("allowed_attestation_profiles"),
            "ATTESTED_RUNTIME_PROFILES_INVALID",
        )
        if any(item not in KNOWN_ATTESTATION_PROFILES for item in profiles):
            raise AttestedRuntimeError("ATTESTED_RUNTIME_PROFILE_UNSUPPORTED")

        verifiers = _string_tuple(
            value.get("allowed_verifier_identities"),
            "ATTESTED_RUNTIME_VERIFIERS_INVALID",
        )

        raw_measurements = value.get("endorsed_measurements")
        if not isinstance(raw_measurements, list) or not raw_measurements:
            raise AttestedRuntimeError("ENDORSED_MEASUREMENTS_INVALID")
        measurements = tuple(EndorsedMeasurement.from_mapping(item) for item in raw_measurements)
        if len({(item.measurement_kind, item.measurement_digest) for item in measurements}) != len(measurements):
            raise AttestedRuntimeError("ENDORSED_MEASUREMENTS_DUPLICATE")

        max_age = _int(value.get("max_evidence_age_seconds"), "ATTESTATION_MAX_AGE_INVALID")
        if max_age <= 0:
            raise AttestedRuntimeError("ATTESTATION_MAX_AGE_INVALID")

        return cls(
            schema_version=SCHEMA_VERSION,
            policy_id=_string(value.get("policy_id"), "ATTESTED_RUNTIME_POLICY_ID_MISSING"),
            required_action_classes=required,
            allowed_attestation_profiles=profiles,
            allowed_verifier_identities=verifiers,
            endorsed_measurements=measurements,
            authorization_scope_root=_hash(value.get("authorization_scope_root"), "AUTHORIZATION_SCOPE_ROOT_INVALID"),
            max_evidence_age_seconds=max_age,
        )

    @property
    def root(self) -> str:
        return canonical_hash(
            TRUST_POLICY_KIND,
            {
                "schema_version": self.schema_version,
                "policy_id": self.policy_id,
                "required_action_classes": list(self.required_action_classes),
                "allowed_attestation_profiles": list(self.allowed_attestation_profiles),
                "allowed_verifier_identities": list(self.allowed_verifier_identities),
                "endorsed_measurements": [
                    {
                        "measurement_kind": item.measurement_kind,
                        "measurement_digest": item.measurement_digest,
                    }
                    for item in self.endorsed_measurements
                ],
                "authorization_scope_root": self.authorization_scope_root,
                "max_evidence_age_seconds": self.max_evidence_age_seconds,
            },
        )


@dataclass(frozen=True)
class ExecutionAttestationVerificationReceipt:
    schema_version: str
    receipt_kind: str
    outcome: str
    runtime_principal: str
    attestation_profile: str
    verifier_identity: str
    measurement_kind: str
    measurement_digest: str
    key_pop_proof_root: str
    authorization_scope_root: str
    authorization_receipt_root: str
    attestation_evidence_root: str
    trust_policy_root: str
    session_identity: str
    action_digest: str
    target_digest: str
    verification_time_epoch: int
    authority_granted: bool
    receipt_root: str


def verify_attested_runtime_for_execution(
    *,
    action_class: str,
    runtime_principal: str,
    key_pop_proof_root: str,
    attestation_evidence: Mapping[str, Any],
    trust_policy: AttestedRuntimeTrustPolicy,
    session_identity: str,
    action_digest: str,
    target_digest: str,
    now_epoch: int,
) -> ExecutionAttestationVerificationReceipt | None:
    """Verify attested-runtime bindings for one concrete execution attempt.

    Returns ``None`` when the deployment policy does not require this assurance
    profile for ``action_class``. A successful receipt is evidence-only and is
    intentionally distinct from the authorization-time receipt it references.
    """
    if not isinstance(trust_policy, AttestedRuntimeTrustPolicy):
        raise AttestedRuntimeError("ATTESTED_RUNTIME_TRUST_POLICY_INVALID")
    if action_class not in KNOWN_ACTION_CLASSES:
        raise AttestedRuntimeError("ATTESTED_RUNTIME_ACTION_CLASS_UNKNOWN")
    if action_class not in trust_policy.required_action_classes:
        return None

    if not isinstance(attestation_evidence, Mapping) or not attestation_evidence:
        raise AttestedRuntimeError("ATTESTED_RUNTIME_EVIDENCE_REQUIRED")
    if attestation_evidence.get("schema_version") != SCHEMA_VERSION:
        raise AttestedRuntimeError("ATTESTED_RUNTIME_EVIDENCE_SCHEMA_UNSUPPORTED")

    expected_runtime = _string(runtime_principal, "ATTESTED_RUNTIME_EXPECTED_PRINCIPAL_MISSING")
    if attestation_evidence.get("runtime_principal") != expected_runtime:
        raise AttestedRuntimeError("ATTESTED_RUNTIME_PRINCIPAL_MISMATCH")

    profile = _string(attestation_evidence.get("attestation_profile"), "ATTESTATION_PROFILE_MISSING")
    if profile not in trust_policy.allowed_attestation_profiles:
        raise AttestedRuntimeError("ATTESTATION_PROFILE_NOT_ALLOWED")

    verifier = _string(attestation_evidence.get("verifier_identity"), "ATTESTATION_VERIFIER_MISSING")
    if verifier not in trust_policy.allowed_verifier_identities:
        raise AttestedRuntimeError("ATTESTATION_VERIFIER_NOT_ALLOWED")
    if attestation_evidence.get("verification_state") != VERIFIED:
        raise AttestedRuntimeError("ATTESTATION_NOT_VERIFIED")

    measurement_kind = _string(attestation_evidence.get("measurement_kind"), "RUNTIME_MEASUREMENT_KIND_MISSING")
    measurement_digest = _hash(attestation_evidence.get("measurement_digest"), "RUNTIME_MEASUREMENT_DIGEST_INVALID")
    endorsed = {
        (item.measurement_kind, item.measurement_digest)
        for item in trust_policy.endorsed_measurements
    }
    if (measurement_kind, measurement_digest) not in endorsed:
        raise AttestedRuntimeError("RUNTIME_MEASUREMENT_NOT_ENDORSED")

    current_key_root = _hash(key_pop_proof_root, "KEY_POP_PROOF_ROOT_INVALID")
    if _hash(attestation_evidence.get("key_binding_root"), "ATTESTED_KEY_BINDING_ROOT_INVALID") != current_key_root:
        raise AttestedRuntimeError("ATTESTED_KEY_POP_BINDING_MISMATCH")

    evidence_scope = _hash(attestation_evidence.get("authorization_scope_root"), "AUTHORIZATION_SCOPE_ROOT_INVALID")
    if evidence_scope != trust_policy.authorization_scope_root:
        raise AttestedRuntimeError("AUTHORIZATION_SCOPE_MISMATCH")

    authorization_receipt_root = _hash(
        attestation_evidence.get("authorization_receipt_root"),
        "AUTHORIZATION_RECEIPT_ROOT_INVALID",
    )
    attestation_evidence_root = _hash(
        attestation_evidence.get("attestation_evidence_root"),
        "ATTESTATION_EVIDENCE_ROOT_INVALID",
    )

    verified_at = _int(now_epoch, "ATTESTATION_VERIFICATION_TIME_INVALID")
    if verified_at < 0:
        raise AttestedRuntimeError("ATTESTATION_VERIFICATION_TIME_INVALID")
    issued_at = _int(attestation_evidence.get("issued_at_epoch"), "ATTESTATION_ISSUED_AT_INVALID")
    expires_at = _int(attestation_evidence.get("expires_at_epoch"), "ATTESTATION_EXPIRES_AT_INVALID")
    if issued_at > verified_at:
        raise AttestedRuntimeError("ATTESTATION_EVIDENCE_FROM_FUTURE")
    if expires_at <= verified_at:
        raise AttestedRuntimeError("ATTESTATION_EVIDENCE_EXPIRED")
    if expires_at < issued_at:
        raise AttestedRuntimeError("ATTESTATION_EVIDENCE_INTERVAL_INVALID")
    if verified_at - issued_at > trust_policy.max_evidence_age_seconds:
        raise AttestedRuntimeError("ATTESTATION_EVIDENCE_STALE")

    session = _string(session_identity, "ATTESTATION_SESSION_IDENTITY_MISSING")
    action = _hash(action_digest, "ATTESTATION_ACTION_DIGEST_INVALID")
    target = _hash(target_digest, "ATTESTATION_TARGET_DIGEST_INVALID")
    trust_policy_root = trust_policy.root

    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "outcome": ATTESTED_RUNTIME_VERIFIED,
        "runtime_principal": expected_runtime,
        "attestation_profile": profile,
        "verifier_identity": verifier,
        "measurement_kind": measurement_kind,
        "measurement_digest": measurement_digest,
        "key_pop_proof_root": current_key_root,
        "authorization_scope_root": evidence_scope,
        "authorization_receipt_root": authorization_receipt_root,
        "attestation_evidence_root": attestation_evidence_root,
        "trust_policy_root": trust_policy_root,
        "session_identity": session,
        "action_digest": action,
        "target_digest": target,
        "verification_time_epoch": verified_at,
        "authority_granted": False,
    }
    receipt_root = canonical_hash(RECEIPT_DOMAIN, unsigned)
    return ExecutionAttestationVerificationReceipt(**unsigned, receipt_root=receipt_root)
