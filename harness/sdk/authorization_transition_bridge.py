"""Bind trusted authorization-time evidence to the exact recomputed PR #268 transition.

This module deliberately introduces no new decision-receipt semantics. It uses
the Git-identical PR #268 TransitionIdentity / DecisionReceipt implementation
already imported into this branch, recomputes the current transition from
verifier-owned authority inputs, requires the signed source object to equal the
resulting DecisionReceipt exactly, and only then verifies the trusted operator
approval event.

The returned object is composition evidence. It does not itself grant AEGIS
authority, execute an action, or prove an external effect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from harness.sdk.authorization_time_evidence import (
    AuthorizationTimeEvidenceReceipt,
    AuthorizationTimeTrustPolicy,
    verify_authorization_time_evidence,
)
from harness.sdk.transition_receipts import (
    PERMIT,
    DecisionReceipt,
    TransitionIdentity,
    build_transition_identity,
    decision_receipt_from_policy,
)


class AuthorizationTransitionBridgeError(ValueError):
    """Fail-closed current-transition authorization composition error."""


@dataclass(frozen=True)
class CurrentTransitionAuthorization:
    transition: TransitionIdentity
    decision_receipt: DecisionReceipt
    authorization_evidence: AuthorizationTimeEvidenceReceipt


def verify_current_transition_authorization(
    *,
    signed_event: Mapping[str, Any],
    source_object: Mapping[str, Any],
    payload: Mapping[str, Any],
    authorization_time_trust_policy: AuthorizationTimeTrustPolicy,
    policy_decision: Any,
    expected_approval_reference: str,
    expected_authority_domain: str,
    expected_action_class: str,
    current_generation: int,
    verification_time_epoch: int,
    source_commit: str,
    pre_state_commitment: str,
    identity_root: str,
    approval: Any | None,
    requested_capability: str,
    registry_root: str,
    action_digest: str,
    deterministic_nonce: str,
    fence_token: str | None = None,
) -> CurrentTransitionAuthorization:
    """Verify one trusted operator approval against the current recomputed τ.

    The signed source object must be byte-semantically equivalent to the exact
    current DecisionReceipt. An old otherwise-valid approval therefore cannot
    survive drift in action, identity, pre-state, delegation, capability,
    registry, nonce, fence, or the policy decision root.
    """
    try:
        transition = build_transition_identity(
            source_commit=source_commit,
            pre_state_commitment=pre_state_commitment,
            identity_root=identity_root,
            approval=approval,
            requested_capability=requested_capability,
            registry_root=registry_root,
            action_digest=action_digest,
            deterministic_nonce=deterministic_nonce,
            fence_token=fence_token,
        )
        decision_receipt = decision_receipt_from_policy(
            transition=transition,
            decision=policy_decision,
        )
    except Exception as exc:
        raise AuthorizationTransitionBridgeError("AUTHZ_TRANSITION_RECOMPUTE_INVALID") from exc

    if decision_receipt.decision_outcome != PERMIT:
        raise AuthorizationTransitionBridgeError("AUTHZ_TRANSITION_DECISION_NOT_PERMIT")

    if not isinstance(source_object, Mapping) or dict(source_object) != asdict(decision_receipt):
        raise AuthorizationTransitionBridgeError("AUTHZ_TRANSITION_SOURCE_MISMATCH")

    authorization_evidence = verify_authorization_time_evidence(
        signed_event=signed_event,
        source_object=source_object,
        payload=payload,
        trust_policy=authorization_time_trust_policy,
        expected_transition_id=transition.root,
        expected_policy_decision_root=decision_receipt.policy_decision_root,
        expected_approval_reference=expected_approval_reference,
        expected_authority_domain=expected_authority_domain,
        expected_action_class=expected_action_class,
        current_generation=current_generation,
        verification_time_epoch=verification_time_epoch,
    )

    if (
        authorization_evidence.transition_id != transition.root
        or authorization_evidence.policy_decision_root != decision_receipt.policy_decision_root
        or authorization_evidence.decision_receipt_root != decision_receipt.root
        or authorization_evidence.authority_granted
    ):
        raise AuthorizationTransitionBridgeError("AUTHZ_TRANSITION_POSTCONDITION_FAILED")

    return CurrentTransitionAuthorization(
        transition=transition,
        decision_receipt=decision_receipt,
        authorization_evidence=authorization_evidence,
    )
