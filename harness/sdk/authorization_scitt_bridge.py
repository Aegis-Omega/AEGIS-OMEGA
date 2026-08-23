"""Bind verified current-transition operator authorization into SCITT registration.

This module adds no new decision or authority type. It composes two already
verified evidence objects:

1. CurrentTransitionAuthorization, whose transition identity is recomputed from
   current authority inputs and whose operator APPROVAL_GRANTED evidence is
   cryptographically verified under an external trust policy; and
2. SCITT authorization registration, whose Signed Statement and transparency
   Receipt are independently verified against current RuntimePoP/EAT/runtime
   trust state.

The only new invariant is equality of the SCITT-signed
``authorization_time_evidence_root`` and the exact current
AuthorizationTimeEvidenceReceipt root. The result remains evidence-only.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from harness.sdk.authorization_time_evidence import (
    AUTHORIZATION_TIME_EVIDENCE_VERIFIED,
    RECEIPT_DOMAIN as AUTHORIZATION_TIME_RECEIPT_DOMAIN,
    AuthorizationTimeEvidenceReceipt,
)
from harness.sdk.authorization_transition_bridge import CurrentTransitionAuthorization
from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.transition_receipts import PERMIT
from harness.sdk.scitt_authorization_authority import (
    verify_scitt_authorization_for_current_runtime,
)


class AuthorizationSCITTBridgeError(ValueError):
    """Fail-closed authorization-to-SCITT composition error."""


def _verification_time(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_VERIFICATION_TIME_INVALID")
    return value


def _validate_current_authorization(
    current: CurrentTransitionAuthorization,
    *,
    verification_time_epoch: int,
) -> AuthorizationTimeEvidenceReceipt:
    if not isinstance(current, CurrentTransitionAuthorization):
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_CURRENT_TRANSITION_INVALID")

    evidence = current.authorization_evidence
    if (
        not isinstance(evidence, AuthorizationTimeEvidenceReceipt)
        or not evidence.authorization_time_verified
        or evidence.outcome != AUTHORIZATION_TIME_EVIDENCE_VERIFIED
        or evidence.authority_granted
    ):
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_AUTHORIZATION_EVIDENCE_INVALID")

    if evidence.verification_time_epoch != verification_time_epoch:
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_VERIFICATION_TIME_MISMATCH")

    try:
        transition_root = current.transition.root
        decision_root = current.decision_receipt.root
    except Exception as exc:
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_CURRENT_TRANSITION_INVALID") from exc

    if (
        current.decision_receipt.decision_outcome != PERMIT
        or current.decision_receipt.transition_id != transition_root
        or evidence.transition_id != transition_root
        or evidence.policy_decision_root != current.decision_receipt.policy_decision_root
        or evidence.decision_receipt_root != decision_root
    ):
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_CURRENT_TRANSITION_INVALID")

    body = asdict(evidence)
    receipt_root = body.pop("receipt_root", None)
    try:
        recomputed_evidence_root = canonical_hash(
            AUTHORIZATION_TIME_RECEIPT_DOMAIN,
            body,
        )
    except Exception as exc:
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_CURRENT_TRANSITION_INVALID") from exc
    if receipt_root != recomputed_evidence_root:
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_CURRENT_TRANSITION_INVALID")

    return evidence


def verify_scitt_for_verified_current_authorization(
    *,
    signed_statement: bytes,
    receipt: bytes,
    scitt_trust_policy: Any,
    runtime_pop_crypto_receipt: Any,
    eat_trust_policy: Any,
    attested_runtime_trust_policy: Any,
    current_authorization: CurrentTransitionAuthorization,
    verification_time_epoch: int,
):
    """Verify SCITT registration against the exact current authorization evidence.

    The authorization-time evidence root is never accepted as a caller argument.
    It is taken only from the already verified CurrentTransitionAuthorization and
    compared with the value authenticated inside the SCITT Signed Statement.
    """
    now = _verification_time(verification_time_epoch)
    evidence = _validate_current_authorization(
        current_authorization,
        verification_time_epoch=now,
    )

    result = verify_scitt_authorization_for_current_runtime(
        signed_statement=signed_statement,
        receipt=receipt,
        scitt_trust_policy=scitt_trust_policy,
        runtime_pop_crypto_receipt=runtime_pop_crypto_receipt,
        eat_trust_policy=eat_trust_policy,
        attested_runtime_trust_policy=attested_runtime_trust_policy,
        verification_time_epoch=now,
    )

    if getattr(result, "authority_granted", True):
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_SCITT_AUTHORITY_FORBIDDEN")
    if not getattr(result, "registration_verified", False):
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_REGISTRATION_NOT_VERIFIED")
    if getattr(result, "verification_time_epoch", None) != now:
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_SCITT_TIME_MISMATCH")
    if getattr(result, "authorization_time_evidence_root", None) != evidence.receipt_root:
        raise AuthorizationSCITTBridgeError("AUTHZ_SCITT_EVIDENCE_ROOT_MISMATCH")

    return result
