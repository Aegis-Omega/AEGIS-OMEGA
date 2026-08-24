"""Compose SCITT authorization registration with current RuntimePoP/EAT policy state.

The caller does not choose the holder key, authorized measurement, authorization
scope, or verifier time. Those values are derived from already selected verifier
state and deployment trust policy, then supplied to the SCITT verifier.

The returned SCITT receipt remains evidence-only and may only become an input to
transaction-time EAT/execution verification.
"""
from __future__ import annotations

from typing import Any

from harness.sdk.attested_runtime import AttestedRuntimeTrustPolicy
from harness.sdk.eat_attestation_crypto import EATJWTTrustPolicy
from harness.sdk.principal_binding import DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND
from harness.sdk.runtime_pop_crypto import (
    CRYPTO_RECEIPT_KIND,
    CRYPTO_SCHEMA_VERSION,
    CRYPTO_VERIFIER_IDENTITY,
    RuntimePoPCryptoReceipt,
)
from harness.sdk.scitt_authorization import (
    SCITTAuthorizationRegistrationReceipt,
    SCITTAuthorizationTrustPolicy,
    verify_scitt_authorization_registration,
)

DPOP_CAPABLE_MODES = frozenset((DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND))


class SCITTAuthorizationCompositionError(ValueError):
    """Fail-closed composition error with stable denial code text."""


def _integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SCITTAuthorizationCompositionError(code)
    return value


def _validate_runtime_pop(
    receipt: RuntimePoPCryptoReceipt,
    *,
    verification_time_epoch: int,
) -> str:
    if not isinstance(receipt, RuntimePoPCryptoReceipt):
        raise SCITTAuthorizationCompositionError("SCITT_RUNTIME_POP_CRYPTO_RECEIPT_INVALID")
    if (
        receipt.schema_version != CRYPTO_SCHEMA_VERSION
        or receipt.receipt_kind != CRYPTO_RECEIPT_KIND
        or not receipt.cryptographic_verified
        or receipt.verifier_identity != CRYPTO_VERIFIER_IDENTITY
    ):
        raise SCITTAuthorizationCompositionError("SCITT_RUNTIME_POP_CRYPTO_RECEIPT_INVALID")
    if receipt.binding_mode not in DPOP_CAPABLE_MODES or not isinstance(receipt.dpop_jkt, str) or receipt.dpop_jkt in ("", "NONE"):
        raise SCITTAuthorizationCompositionError("SCITT_DPOP_HOLDER_KEY_REQUIRED")
    if receipt.verification_time_epoch != verification_time_epoch:
        raise SCITTAuthorizationCompositionError("SCITT_RUNTIME_POP_TIME_MISMATCH")
    return receipt.dpop_jkt


def verify_scitt_authorization_for_current_runtime(
    *,
    signed_statement: bytes,
    receipt: bytes,
    scitt_trust_policy: SCITTAuthorizationTrustPolicy,
    runtime_pop_crypto_receipt: RuntimePoPCryptoReceipt,
    eat_trust_policy: EATJWTTrustPolicy,
    attested_runtime_trust_policy: AttestedRuntimeTrustPolicy,
    verification_time_epoch: int,
) -> SCITTAuthorizationRegistrationReceipt:
    """Verify registration against current holder, measurement and scope state."""
    now = _integer(verification_time_epoch, "SCITT_VERIFICATION_TIME_INVALID")
    if not isinstance(scitt_trust_policy, SCITTAuthorizationTrustPolicy):
        raise SCITTAuthorizationCompositionError("SCITT_TRUST_POLICY_INVALID")
    if not isinstance(eat_trust_policy, EATJWTTrustPolicy):
        raise SCITTAuthorizationCompositionError("SCITT_EAT_TRUST_POLICY_INVALID")
    if not isinstance(attested_runtime_trust_policy, AttestedRuntimeTrustPolicy):
        raise SCITTAuthorizationCompositionError("SCITT_ATTESTED_RUNTIME_TRUST_POLICY_INVALID")

    holder_jkt = _validate_runtime_pop(
        runtime_pop_crypto_receipt,
        verification_time_epoch=now,
    )
    result = verify_scitt_authorization_registration(
        signed_statement=signed_statement,
        receipt=receipt,
        trust_policy=scitt_trust_policy,
        expected_scope_root=attested_runtime_trust_policy.authorization_scope_root,
        expected_holder_jkt=holder_jkt,
        expected_measurement_digest=eat_trust_policy.endorsed_measurement_digest,
        verification_time_epoch=now,
    )
    if result.authority_granted:
        raise SCITTAuthorizationCompositionError("SCITT_REGISTRATION_RECEIPT_AUTHORITY_FORBIDDEN")
    if not result.registration_verified:
        raise SCITTAuthorizationCompositionError("SCITT_REGISTRATION_NOT_VERIFIED")
    if result.holder_jkt != holder_jkt:
        raise SCITTAuthorizationCompositionError("SCITT_REGISTRATION_HOLDER_MISMATCH")
    if result.measurement_digest != eat_trust_policy.endorsed_measurement_digest:
        raise SCITTAuthorizationCompositionError("SCITT_REGISTRATION_MEASUREMENT_MISMATCH")
    if result.scope_root != attested_runtime_trust_policy.authorization_scope_root:
        raise SCITTAuthorizationCompositionError("SCITT_REGISTRATION_SCOPE_MISMATCH")
    if result.verification_time_epoch != now:
        raise SCITTAuthorizationCompositionError("SCITT_REGISTRATION_TIME_MISMATCH")
    return result
