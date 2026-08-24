#!/usr/bin/env python3
"""Falsifiers for binding authorization-time evidence to recomputed PR #268 τ."""
from __future__ import annotations

import hashlib
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main

import rfc8785

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TEST_ROOT))

from harness.sdk.authorization_transition_bridge import (  # noqa: E402
    AuthorizationTransitionBridgeError,
    verify_current_transition_authorization,
)
from harness.sdk.transition_receipts import (  # noqa: E402
    DECISION_RECEIPT_KIND,
    PERMIT,
    build_transition_identity,
    decision_receipt_from_policy,
)
from test_authorization_time_evidence import (  # noqa: E402
    ACTION_CLASS,
    APPROVAL_REFERENCE,
    AUTHORITY_DOMAIN,
    CURRENT_GENERATION,
    KEY_ID,
    NOW,
    OPERATOR_ACTOR,
    OPERATOR_EXECUTOR,
    OPERATOR_PRIVATE,
    OPERATOR_PUBLIC,
    OPERATOR_SESSION,
    REQUEST_ACTOR,
    REQUEST_EXECUTOR,
    REQUEST_SESSION,
    approval_payload,
    emitted_at,
    policy,
)

SOURCE_COMMIT = "a" * 40
PRE_STATE = "b" * 64
IDENTITY_ROOT = "c" * 64
WORKSPACE_BINDING = "d" * 64
APPROVAL_SIGNATURE_ROOT = "e" * 64
REGISTRY_ROOT = "f" * 64
ACTION_DIGEST = "0" * 64
POLICY_DECISION_ROOT = "2" * 64
REQUESTED_CAPABILITY = "repo.write"
NONCE = "nonce-001"
FENCE_TOKEN = "fence-001"


def approval(**overrides) -> dict:
    value = {
        "reference": APPROVAL_REFERENCE,
        "authority_domain": AUTHORITY_DOMAIN,
        "action_class": ACTION_CLASS,
        "source_commit": SOURCE_COMMIT,
        "workspace_binding": WORKSPACE_BINDING,
        "valid_through_generation": 7,
        "signature_root": APPROVAL_SIGNATURE_ROOT,
        "state": "APPROVED",
    }
    value.update(overrides)
    return value


def policy_decision(outcome="ADMITTED", root=POLICY_DECISION_ROOT):
    return SimpleNamespace(outcome=outcome, decision_root=root)


def transition_for(**overrides):
    args = {
        "source_commit": SOURCE_COMMIT,
        "pre_state_commitment": PRE_STATE,
        "identity_root": IDENTITY_ROOT,
        "approval": approval(),
        "requested_capability": REQUESTED_CAPABILITY,
        "registry_root": REGISTRY_ROOT,
        "action_digest": ACTION_DIGEST,
        "deterministic_nonce": NONCE,
        "fence_token": FENCE_TOKEN,
    }
    args.update(overrides)
    return build_transition_identity(**args)


def signed_current_event(*, transition=None, decision=None, source_override=None):
    transition = transition_for() if transition is None else transition
    decision = policy_decision() if decision is None else decision
    receipt = decision_receipt_from_policy(transition=transition, decision=decision)
    source = asdict(receipt) if source_override is None else source_override
    payload = approval_payload(decision=source)
    draft = {
        "schema_version": "1.0.0",
        "event_id": "event-approval-current-001",
        "event_type": "APPROVAL_GRANTED",
        "aggregate_id": APPROVAL_REFERENCE,
        "sequence": "3",
        "previous_event_hash": "a" * 64,
        "idempotency_key": "approval-001:APPROVAL_GRANTED:current",
        "correlation_id": source["transition_id"],
        "causation_id": "event-approval-requested-current",
        "emitted_at": emitted_at(NOW - 5),
        "identities": {
            "request": {
                "actor_id": REQUEST_ACTOR,
                "session_id": REQUEST_SESSION,
                "executor_id": REQUEST_EXECUTOR,
            },
            "approval": {
                "actor_id": OPERATOR_ACTOR,
                "session_id": OPERATOR_SESSION,
                "executor_id": OPERATOR_EXECUTOR,
            },
            "execution": None,
            "verification": None,
        },
        "signer_key_id": KEY_ID,
        "signer_public_key": OPERATOR_PUBLIC,
        "source_object_hash": hashlib.sha256(rfc8785.dumps({
            "domain": "AEGIS_SCALE_OS_SOURCE_OBJECT_V1", "source_object": source,
        })).hexdigest(),
        "payload_hash": hashlib.sha256(rfc8785.dumps({
            "domain": "AEGIS_SCALE_OS_EVENT_PAYLOAD_V1", "payload": payload,
        })).hexdigest(),
    }
    draft["signature"] = OPERATOR_PRIVATE.sign(rfc8785.dumps({
        "domain": "AEGIS_SCALE_OS_EVENT_ENVELOPE_V1", "envelope": draft,
    })).hex()
    return draft, source, payload, transition, receipt


def verify(*, event=None, source=None, payload=None, transition_args=None, decision=None):
    if event is None or source is None or payload is None:
        event0, source0, payload0, _, _ = signed_current_event()
        event = event0 if event is None else event
        source = source0 if source is None else source
        payload = payload0 if payload is None else payload
    args = {
        "source_commit": SOURCE_COMMIT,
        "pre_state_commitment": PRE_STATE,
        "identity_root": IDENTITY_ROOT,
        "approval": approval(),
        "requested_capability": REQUESTED_CAPABILITY,
        "registry_root": REGISTRY_ROOT,
        "action_digest": ACTION_DIGEST,
        "deterministic_nonce": NONCE,
        "fence_token": FENCE_TOKEN,
    }
    if transition_args:
        args.update(transition_args)
    return verify_current_transition_authorization(
        signed_event=event,
        source_object=source,
        payload=payload,
        authorization_time_trust_policy=policy(),
        policy_decision=policy_decision() if decision is None else decision,
        expected_approval_reference=APPROVAL_REFERENCE,
        expected_authority_domain=AUTHORITY_DOMAIN,
        expected_action_class=ACTION_CLASS,
        current_generation=CURRENT_GENERATION,
        verification_time_epoch=NOW,
        **args,
    )


class AuthorizationTransitionBridgeTests(TestCase):
    def test_01_operator_approval_is_bound_to_recomputed_current_transition(self):
        event, source, payload, transition, decision_receipt = signed_current_event()
        result = verify(event=event, source=source, payload=payload)
        self.assertEqual(result.transition.root, transition.root)
        self.assertEqual(result.decision_receipt.root, decision_receipt.root)
        self.assertEqual(result.decision_receipt.receipt_kind, DECISION_RECEIPT_KIND)
        self.assertEqual(result.decision_receipt.decision_outcome, PERMIT)
        self.assertEqual(result.authorization_evidence.transition_id, transition.root)
        self.assertEqual(result.authorization_evidence.decision_receipt_root, decision_receipt.root)
        self.assertFalse(result.authorization_evidence.authority_granted)

    def test_02_action_identity_or_pre_state_drift_changes_tau_and_denies_old_approval(self):
        event, source, payload, _, _ = signed_current_event()
        for changed in (
            {"action_digest": "9" * 64},
            {"identity_root": "8" * 64},
            {"pre_state_commitment": "7" * 64},
        ):
            with self.assertRaisesRegex(AuthorizationTransitionBridgeError, "AUTHZ_TRANSITION_SOURCE_MISMATCH"):
                verify(event=event, source=source, payload=payload, transition_args=changed)

    def test_03_delegation_capability_registry_fence_or_nonce_drift_denies_old_approval(self):
        event, source, payload, _, _ = signed_current_event()
        variants = (
            {"approval": approval(signature_root="6" * 64)},
            {"requested_capability": "repo.admin"},
            {"registry_root": "5" * 64},
            {"fence_token": "fence-002"},
            {"deterministic_nonce": "nonce-002"},
        )
        for changed in variants:
            with self.assertRaisesRegex(AuthorizationTransitionBridgeError, "AUTHZ_TRANSITION_SOURCE_MISMATCH"):
                verify(event=event, source=source, payload=payload, transition_args=changed)

    def test_04_non_permit_current_policy_decision_cannot_be_operator_permit_evidence(self):
        event, source, payload, _, _ = signed_current_event()
        for outcome in ("DENIED", "WAITING", "UNKNOWN"):
            with self.assertRaisesRegex(AuthorizationTransitionBridgeError, "AUTHZ_TRANSITION_DECISION_NOT_PERMIT"):
                verify(event=event, source=source, payload=payload, decision=policy_decision(outcome=outcome))

    def test_05_signed_source_must_equal_exact_recomputed_decision_receipt(self):
        transition = transition_for()
        receipt = decision_receipt_from_policy(transition=transition, decision=policy_decision())
        forged_source = {**asdict(receipt), "policy_decision_root": "4" * 64}
        event, source, payload, _, _ = signed_current_event(
            transition=transition,
            source_override=forged_source,
        )
        with self.assertRaisesRegex(AuthorizationTransitionBridgeError, "AUTHZ_TRANSITION_SOURCE_MISMATCH"):
            verify(event=event, source=source, payload=payload)

    def test_06_bridge_does_not_create_an_alternate_decision_receipt_type(self):
        result = verify()
        self.assertEqual(type(result.decision_receipt).__name__, "DecisionReceipt")
        self.assertEqual(result.decision_receipt.receipt_kind, "DECISION_RECEIPT_V1")
        self.assertFalse(hasattr(result, "replacement_decision_receipt"))


if __name__ == "__main__":
    main()
