#!/usr/bin/env python3
"""Falsifiers for cryptographically verified authorization-time approval evidence.

This profile reuses two existing AEGIS contracts rather than inventing a new
authorization decision type:

* Scale OS Signed Control-Plane Event V1 provides the Ed25519 signed envelope;
* PR #268 DECISION_RECEIPT_V1 semantics provide the serialized decision object.

The verifier must externally trust-bind the Scale OS signer. A valid signature
under a self-presented key is never sufficient.
"""
from __future__ import annotations

import copy
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, main

import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.authorization_time_evidence import (  # noqa: E402
    AUTHORIZATION_TIME_EVIDENCE_VERIFIED,
    AuthorizationTimeEvidenceError,
    AuthorizationTimeTrustPolicy,
    verify_authorization_time_evidence,
)
from harness.sdk.sovereign_execution import canonical_hash  # noqa: E402

NOW = 1_787_500_000
TRANSITION_ID = "1" * 64
POLICY_DECISION_ROOT = "2" * 64
APPROVAL_REFERENCE = "approval-001"
AUTHORITY_DOMAIN = "github-repository"
ACTION_CLASS = "D4"
CURRENT_GENERATION = 4
VALID_THROUGH_GENERATION = 7
OPERATOR_ACTOR = "operator-primary"
OPERATOR_EXECUTOR = "operator-device-1"
OPERATOR_SESSION = "operator-session-1"
REQUEST_ACTOR = "request-agent"
REQUEST_EXECUTOR = "request-runner"
REQUEST_SESSION = "request-session-1"
KEY_ID = "operator-key-1"

OPERATOR_PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
OTHER_PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes(range(33, 65)))


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


OPERATOR_PUBLIC = public_hex(OPERATOR_PRIVATE)
OTHER_PUBLIC = public_hex(OTHER_PRIVATE)


def sha256_jcs(value) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def decision_receipt(*, transition_id=TRANSITION_ID, policy_root=POLICY_DECISION_ROOT, outcome="PERMIT", kind="DECISION_RECEIPT_V1") -> dict:
    return {
        "receipt_kind": kind,
        "transition_id": transition_id,
        "decision_outcome": outcome,
        "policy_decision_root": policy_root,
    }


def decision_root(value: dict) -> str:
    return canonical_hash("AEGIS_DECISION_RECEIPT_V1", value)


def approval_payload(*, decision=None, approval_reference=APPROVAL_REFERENCE, authority_domain=AUTHORITY_DOMAIN, action_class=ACTION_CLASS, valid_through_generation=VALID_THROUGH_GENERATION) -> dict:
    dec = decision_receipt() if decision is None else decision
    return {
        "profile": "AEGIS_AUTHORIZATION_APPROVAL_V1",
        "state": "APPROVED",
        "approval_reference": approval_reference,
        "authority_domain": authority_domain,
        "action_class": action_class,
        "valid_through_generation": valid_through_generation,
        "decision_receipt_root": decision_root(dec),
    }


def emitted_at(epoch=NOW - 5) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_event(*, signing_key=OPERATOR_PRIVATE, presented_public=OPERATOR_PUBLIC, signer_key_id=KEY_ID, event_type="APPROVAL_GRANTED", decision=None, payload=None, approval_actor=OPERATOR_ACTOR, approval_executor=OPERATOR_EXECUTOR, event_epoch=NOW - 5):
    source = decision_receipt() if decision is None else decision
    body = approval_payload(decision=source) if payload is None else payload
    draft = {
        "schema_version": "1.0.0",
        "event_id": "event-approval-001",
        "event_type": event_type,
        "aggregate_id": APPROVAL_REFERENCE,
        "sequence": "3",
        "previous_event_hash": "a" * 64,
        "idempotency_key": "approval-001:APPROVAL_GRANTED:3",
        "correlation_id": TRANSITION_ID,
        "causation_id": "event-approval-requested-001",
        "emitted_at": emitted_at(event_epoch),
        "identities": {
            "request": {
                "actor_id": REQUEST_ACTOR,
                "session_id": REQUEST_SESSION,
                "executor_id": REQUEST_EXECUTOR,
            },
            "approval": {
                "actor_id": approval_actor,
                "session_id": OPERATOR_SESSION,
                "executor_id": approval_executor,
            },
            "execution": None,
            "verification": None,
        },
        "signer_key_id": signer_key_id,
        "signer_public_key": presented_public,
        "source_object_hash": sha256_jcs({"domain": "AEGIS_SCALE_OS_SOURCE_OBJECT_V1", "source_object": source}),
        "payload_hash": sha256_jcs({"domain": "AEGIS_SCALE_OS_EVENT_PAYLOAD_V1", "payload": body}),
    }
    signature = signing_key.sign(rfc8785.dumps({"domain": "AEGIS_SCALE_OS_EVENT_ENVELOPE_V1", "envelope": draft})).hex()
    return {**draft, "signature": signature}, source, body


def policy(**overrides) -> AuthorizationTimeTrustPolicy:
    value = {
        "schema_version": "1.0.0",
        "policy_id": "aegis-operator-authorization-time-v1",
        "trusted_operator_keys": [{
            "key_id": KEY_ID,
            "public_key_hex": OPERATOR_PUBLIC,
            "actor_id": OPERATOR_ACTOR,
            "executor_id": OPERATOR_EXECUTOR,
        }],
        "max_event_age_seconds": 300,
        "max_future_skew_seconds": 30,
        "allowed_action_classes": ["D3", "D4"],
    }
    value.update(overrides)
    return AuthorizationTimeTrustPolicy.from_mapping(value)


def verify(*, event=None, source=None, payload=None, trust=None, transition_id=TRANSITION_ID, policy_root=POLICY_DECISION_ROOT, approval_reference=APPROVAL_REFERENCE, authority_domain=AUTHORITY_DOMAIN, action_class=ACTION_CLASS, generation=CURRENT_GENERATION, now=NOW):
    if event is None or source is None or payload is None:
        default_event, default_source, default_payload = make_event()
        event = default_event if event is None else event
        source = default_source if source is None else source
        payload = default_payload if payload is None else payload
    return verify_authorization_time_evidence(
        signed_event=event,
        source_object=source,
        payload=payload,
        trust_policy=policy() if trust is None else trust,
        expected_transition_id=transition_id,
        expected_policy_decision_root=policy_root,
        expected_approval_reference=approval_reference,
        expected_authority_domain=authority_domain,
        expected_action_class=action_class,
        current_generation=generation,
        verification_time_epoch=now,
    )


class AuthorizationTimeEvidenceTests(TestCase):
    def test_01_trusted_operator_approval_produces_evidence_receipt(self):
        result = verify()
        self.assertEqual(result.outcome, AUTHORIZATION_TIME_EVIDENCE_VERIFIED)
        self.assertTrue(result.authorization_time_verified)
        self.assertEqual(result.transition_id, TRANSITION_ID)
        self.assertEqual(result.policy_decision_root, POLICY_DECISION_ROOT)
        self.assertEqual(result.decision_receipt_root, decision_root(decision_receipt()))
        self.assertEqual(result.approval_reference, APPROVAL_REFERENCE)
        self.assertFalse(result.authority_granted)
        self.assertEqual(len(result.receipt_root), 64)

    def test_02_self_presented_signing_key_is_not_a_trust_anchor(self):
        event, source, payload = make_event(signing_key=OTHER_PRIVATE, presented_public=OTHER_PUBLIC)
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_SIGNER_KEY_UNTRUSTED"):
            verify(event=event, source=source, payload=payload)

    def test_03_source_payload_and_signature_tampering_fail_closed(self):
        event, source, payload = make_event()
        bad_source = {**source, "policy_decision_root": "f" * 64}
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_SOURCE_HASH_MISMATCH"):
            verify(event=event, source=bad_source, payload=payload)
        bad_payload = {**payload, "authority_domain": "other-domain"}
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_PAYLOAD_HASH_MISMATCH"):
            verify(event=event, source=source, payload=bad_payload)
        bad_event = copy.deepcopy(event)
        bad_event["signature"] = ("0" if event["signature"][0] != "0" else "1") + event["signature"][1:]
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_SIGNATURE_INVALID"):
            verify(event=bad_event, source=source, payload=payload)

    def test_04_only_approval_granted_by_trusted_operator_identity_is_accepted(self):
        event, source, payload = make_event(event_type="APPROVAL_DENIED")
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_EVENT_TYPE_INVALID"):
            verify(event=event, source=source, payload=payload)
        event, source, payload = make_event(approval_actor="impostor")
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_OPERATOR_IDENTITY_MISMATCH"):
            verify(event=event, source=source, payload=payload)

    def test_05_serialized_pr268_decision_receipt_requires_nominal_permit(self):
        for bad in (
            decision_receipt(kind="EXECUTION_RECEIPT_V1"),
            decision_receipt(outcome="DENY"),
            decision_receipt(outcome="DEFER"),
        ):
            event, source, payload = make_event(decision=bad)
            with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_DECISION_RECEIPT_INVALID"):
                verify(event=event, source=source, payload=payload)

    def test_06_transition_and_policy_decision_roots_are_exact(self):
        event, source, payload = make_event()
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_TRANSITION_MISMATCH"):
            verify(event=event, source=source, payload=payload, transition_id="b" * 64)
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_POLICY_DECISION_MISMATCH"):
            verify(event=event, source=source, payload=payload, policy_root="c" * 64)

    def test_07_payload_binds_recomputed_decision_root_and_approval_scope(self):
        event, source, payload = make_event()
        bad = {**payload, "decision_receipt_root": "d" * 64}
        event_bad, _, _ = make_event(decision=source, payload=bad)
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_DECISION_ROOT_MISMATCH"):
            verify(event=event_bad, source=source, payload=bad)
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_APPROVAL_REFERENCE_MISMATCH"):
            verify(event=event, source=source, payload=payload, approval_reference="approval-other")
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_AUTHORITY_DOMAIN_MISMATCH"):
            verify(event=event, source=source, payload=payload, authority_domain="other-domain")
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_ACTION_CLASS_MISMATCH"):
            verify(event=event, source=source, payload=payload, action_class="D3")

    def test_08_generation_expiry_is_verifier_owned(self):
        event, source, payload = make_event()
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_APPROVAL_EXPIRED"):
            verify(event=event, source=source, payload=payload, generation=VALID_THROUGH_GENERATION + 1)

    def test_09_event_freshness_and_future_skew_use_verifier_time(self):
        stale_event, source, payload = make_event(event_epoch=NOW - 301)
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_EVENT_STALE"):
            verify(event=stale_event, source=source, payload=payload)
        future_event, source, payload = make_event(event_epoch=NOW + 31)
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_EVENT_FROM_FUTURE"):
            verify(event=future_event, source=source, payload=payload)

    def test_10_receipt_retains_digests_not_raw_authorization_artifacts(self):
        result = verify()
        self.assertFalse(hasattr(result, "signed_event"))
        self.assertFalse(hasattr(result, "source_object"))
        self.assertFalse(hasattr(result, "payload"))
        self.assertFalse(hasattr(result, "signature"))
        self.assertEqual(len(result.signed_event_sha256), 64)
        self.assertEqual(len(result.trust_policy_root), 64)

    def test_11_trust_policy_rejects_duplicate_or_private_key_material(self):
        key = {
            "key_id": KEY_ID,
            "public_key_hex": OPERATOR_PUBLIC,
            "actor_id": OPERATOR_ACTOR,
            "executor_id": OPERATOR_EXECUTOR,
        }
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_TRUSTED_KEYS_INVALID"):
            AuthorizationTimeTrustPolicy.from_mapping({
                "schema_version": "1.0.0",
                "policy_id": "bad",
                "trusted_operator_keys": [key, dict(key)],
                "max_event_age_seconds": 300,
                "max_future_skew_seconds": 30,
                "allowed_action_classes": ["D4"],
            })
        private = {**key, "private_key_hex": "00" * 32}
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_TRUSTED_KEYS_INVALID"):
            AuthorizationTimeTrustPolicy.from_mapping({
                "schema_version": "1.0.0",
                "policy_id": "bad-private",
                "trusted_operator_keys": [private],
                "max_event_age_seconds": 300,
                "max_future_skew_seconds": 30,
                "allowed_action_classes": ["D4"],
            })

    def test_12_event_public_key_must_equal_external_trust_key(self):
        event, source, payload = make_event(presented_public=OTHER_PUBLIC, signing_key=OTHER_PRIVATE)
        trust = policy(trusted_operator_keys=[{
            "key_id": KEY_ID,
            "public_key_hex": OPERATOR_PUBLIC,
            "actor_id": OPERATOR_ACTOR,
            "executor_id": OPERATOR_EXECUTOR,
        }])
        with self.assertRaisesRegex(AuthorizationTimeEvidenceError, "AUTHZ_TIME_SIGNER_KEY_UNTRUSTED"):
            verify(event=event, source=source, payload=payload, trust=trust)


if __name__ == "__main__":
    main()
