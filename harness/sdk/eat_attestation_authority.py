"""Compose cryptographic EAT evidence into execution-specific attested-runtime evidence.

This layer closes the bypass where a caller could otherwise present structural
``verification_state=VERIFIED`` evidence beside a cryptographically verified
EAT path. When this EAT profile is selected, structural attestation evidence is
derived from the EAT crypto receipt and the current RuntimePoP result.

The composition remains evidence-only. It grants no AEGIS authority.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any

from harness.sdk.attested_runtime import (
    EAT_KEY_BOUND,
    AttestedRuntimeTrustPolicy,
    ExecutionAttestationVerificationReceipt,
    verify_attested_runtime_for_execution,
)
from harness.sdk.eat_attestation_crypto import (
    EATAttestationCryptoReceipt,
    EATJWTTrustPolicy,
    verify_eat_jwt_attestation,
)
from harness.sdk.principal_binding import DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND, VERIFIED
from harness.sdk.runtime_pop_crypto import (
    CRYPTO_RECEIPT_KIND,
    CRYPTO_SCHEMA_VERSION,
    CRYPTO_VERIFIER_IDENTITY,
    RuntimePoPCryptoReceipt,
)

EAT_ATTESTATION_VERIFIER_IDENTITY = "aegis:eat-jwt-attestation-crypto-v1"
EAT_RFC10013_MEASUREMENT_KIND = "sha256:rfc10013-measured-component"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DPOP_CAPABLE_MODES = frozenset((DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND))


class EATAttestationCompositionError(ValueError):
    """Fail-closed composition error with stable denial code text."""


def _hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EATAttestationCompositionError(code)
    return value


def _string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EATAttestationCompositionError(code)
    return value


def _integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EATAttestationCompositionError(code)
    return value


def _jwt_claims_after_crypto_verification(raw_token: str) -> dict[str, Any]:
    """Decode claims only after the same raw token passed signature verification."""
    token = _string(raw_token, "EAT_JWT_INVALID")
    parts = token.split(".")
    if len(parts) != 3:
        raise EATAttestationCompositionError("EAT_JWT_INVALID")
    try:
        padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception as exc:
        raise EATAttestationCompositionError("EAT_JWT_INVALID") from exc
    if not isinstance(claims, dict):
        raise EATAttestationCompositionError("EAT_JWT_INVALID")
    return claims


def _validate_runtime_pop_receipt(
    receipt: RuntimePoPCryptoReceipt,
    *,
    runtime_principal: str,
    verification_time_epoch: int,
) -> str:
    if not isinstance(receipt, RuntimePoPCryptoReceipt):
        raise EATAttestationCompositionError("EAT_RUNTIME_POP_CRYPTO_RECEIPT_INVALID")
    if (
        receipt.schema_version != CRYPTO_SCHEMA_VERSION
        or receipt.receipt_kind != CRYPTO_RECEIPT_KIND
        or not receipt.cryptographic_verified
        or receipt.verifier_identity != CRYPTO_VERIFIER_IDENTITY
    ):
        raise EATAttestationCompositionError("EAT_RUNTIME_POP_CRYPTO_RECEIPT_INVALID")
    expected_runtime = _string(runtime_principal, "EAT_RUNTIME_PRINCIPAL_MISSING")
    if receipt.runtime_principal != expected_runtime:
        raise EATAttestationCompositionError("EAT_RUNTIME_PRINCIPAL_MISMATCH")
    if receipt.binding_mode not in DPOP_CAPABLE_MODES or receipt.dpop_jkt == "NONE":
        raise EATAttestationCompositionError("EAT_DPOP_HOLDER_KEY_REQUIRED")
    if receipt.verification_time_epoch != verification_time_epoch:
        raise EATAttestationCompositionError("EAT_RUNTIME_POP_TIME_MISMATCH")
    return _string(receipt.dpop_jkt, "EAT_DPOP_HOLDER_KEY_REQUIRED")


def verify_eat_bound_attested_runtime_for_execution(
    *,
    action_class: str,
    runtime_principal: str,
    runtime_pop_crypto_receipt: RuntimePoPCryptoReceipt,
    trust_bound_key_pop_root: str,
    raw_eat_token: str,
    eat_trust_policy: EATJWTTrustPolicy,
    attested_runtime_trust_policy: AttestedRuntimeTrustPolicy,
    expected_nonce: str,
    authorization_receipt_root: str,
    session_identity: str,
    action_digest: str,
    target_digest: str,
    verification_time_epoch: int,
) -> tuple[EATAttestationCryptoReceipt | None, ExecutionAttestationVerificationReceipt | None]:
    """Verify EAT and derive structural attestation for one execution attempt.

    For action classes not requiring attested runtime under the structural
    deployment policy, returns ``(None, None)`` without creating fake evidence.
    """
    if not isinstance(attested_runtime_trust_policy, AttestedRuntimeTrustPolicy):
        raise EATAttestationCompositionError("EAT_ATTESTED_RUNTIME_TRUST_POLICY_INVALID")
    if action_class not in attested_runtime_trust_policy.required_action_classes:
        return None, None
    if not isinstance(eat_trust_policy, EATJWTTrustPolicy):
        raise EATAttestationCompositionError("EAT_TRUST_POLICY_INVALID")

    now = _integer(verification_time_epoch, "EAT_VERIFICATION_TIME_INVALID")
    if now < 0:
        raise EATAttestationCompositionError("EAT_VERIFICATION_TIME_INVALID")
    holder_jkt = _validate_runtime_pop_receipt(
        runtime_pop_crypto_receipt,
        runtime_principal=runtime_principal,
        verification_time_epoch=now,
    )
    key_pop_root = _hash(trust_bound_key_pop_root, "EAT_TRUST_BOUND_KEY_POP_ROOT_INVALID")
    authorization_root = _hash(authorization_receipt_root, "AUTHORIZATION_RECEIPT_ROOT_INVALID")

    eat_receipt = verify_eat_jwt_attestation(
        raw_token=raw_eat_token,
        trust_policy=eat_trust_policy,
        expected_subject_jkt=holder_jkt,
        expected_nonce=expected_nonce,
        verification_time_epoch=now,
    )
    if eat_receipt.authority_granted:
        raise EATAttestationCompositionError("EAT_CRYPTO_RECEIPT_AUTHORITY_FORBIDDEN")
    if eat_receipt.subject_jkt != holder_jkt:
        raise EATAttestationCompositionError("EAT_SUBJECT_KEY_MISMATCH")
    if eat_receipt.verification_time_epoch != now:
        raise EATAttestationCompositionError("EAT_CRYPTO_RECEIPT_TIME_MISMATCH")

    # The raw token was just signature-verified above. Decode the exact same
    # token only to preserve authenticated iat/exp in the derived structural
    # evidence consumed by the generic attested-runtime verifier.
    claims = _jwt_claims_after_crypto_verification(raw_eat_token)
    issued_at = _integer(claims.get("iat"), "EAT_IAT_INVALID")
    expires_at = _integer(claims.get("exp"), "EAT_EXP_INVALID")

    derived_evidence = {
        "schema_version": "1.0.0",
        "runtime_principal": runtime_principal,
        "attestation_profile": EAT_KEY_BOUND,
        "verifier_identity": EAT_ATTESTATION_VERIFIER_IDENTITY,
        "verification_state": VERIFIED,
        "measurement_kind": EAT_RFC10013_MEASUREMENT_KIND,
        "measurement_digest": eat_receipt.measurement_digest,
        "key_binding_root": key_pop_root,
        "authorization_scope_root": attested_runtime_trust_policy.authorization_scope_root,
        "authorization_receipt_root": authorization_root,
        "attestation_evidence_root": eat_receipt.receipt_root,
        "issued_at_epoch": issued_at,
        "expires_at_epoch": expires_at,
    }

    execution_receipt = verify_attested_runtime_for_execution(
        action_class=action_class,
        runtime_principal=runtime_principal,
        key_pop_proof_root=key_pop_root,
        attestation_evidence=derived_evidence,
        trust_policy=attested_runtime_trust_policy,
        session_identity=session_identity,
        action_digest=action_digest,
        target_digest=target_digest,
        now_epoch=now,
    )
    if execution_receipt is None:
        raise EATAttestationCompositionError("EAT_EXECUTION_ATTESTATION_REQUIRED")
    if execution_receipt.authority_granted:
        raise EATAttestationCompositionError("EAT_EXECUTION_RECEIPT_AUTHORITY_FORBIDDEN")
    return eat_receipt, execution_receipt
