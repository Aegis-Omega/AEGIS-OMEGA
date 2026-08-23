#!/usr/bin/env python3
"""Falsifiers for KeyPoP != approved software identity.

The external motivation is draft-hawkins-scitt-attested-agent-payment-01, a
work-in-progress Internet-Draft. These tests deliberately extract only the
generic security boundary: key possession, runtime/software attestation,
authorization-time evidence, and execution-time verification are distinct.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.attested_runtime import (  # noqa: E402
    ATTESTED_RUNTIME_VERIFIED,
    EAT_KEY_BOUND,
    AttestedRuntimeError,
    AttestedRuntimeTrustPolicy,
    ExecutionAttestationVerificationReceipt,
    verify_attested_runtime_for_execution,
)

RUNTIME = "spiffe://aegis.example/runtime/gateway-7"
KEY_POP_ROOT = "1" * 64
MEASUREMENT = "2" * 64
SCOPE_ROOT = "3" * 64
AUTHORIZATION_RECEIPT_ROOT = "4" * 64
ATTESTATION_EVIDENCE_ROOT = "5" * 64
ACTION_DIGEST = "6" * 64
TARGET_DIGEST = "7" * 64
SESSION = "session-1"
NOW = 1_787_500_000


def policy(*, required=("D4",), measurement=MEASUREMENT) -> AttestedRuntimeTrustPolicy:
    return AttestedRuntimeTrustPolicy.from_mapping({
        "schema_version": "1.0.0",
        "policy_id": "aegis-test-attested-runtime",
        "required_action_classes": list(required),
        "allowed_attestation_profiles": [EAT_KEY_BOUND],
        "allowed_verifier_identities": ["attester:test-v1"],
        "endorsed_measurements": [
            {"measurement_kind": "sha256:container-manifest", "measurement_digest": measurement}
        ],
        "authorization_scope_root": SCOPE_ROOT,
        "max_evidence_age_seconds": 300,
    })


def evidence(**overrides) -> dict:
    value = {
        "schema_version": "1.0.0",
        "runtime_principal": RUNTIME,
        "attestation_profile": EAT_KEY_BOUND,
        "verifier_identity": "attester:test-v1",
        "verification_state": "VERIFIED",
        "measurement_kind": "sha256:container-manifest",
        "measurement_digest": MEASUREMENT,
        "key_binding_root": KEY_POP_ROOT,
        "authorization_scope_root": SCOPE_ROOT,
        "authorization_receipt_root": AUTHORIZATION_RECEIPT_ROOT,
        "attestation_evidence_root": ATTESTATION_EVIDENCE_ROOT,
        "issued_at_epoch": NOW - 10,
        "expires_at_epoch": NOW + 120,
    }
    value.update(overrides)
    return value


def verify(*, action_class="D4", attestation=None, trust=None, action=ACTION_DIGEST):
    return verify_attested_runtime_for_execution(
        action_class=action_class,
        runtime_principal=RUNTIME,
        key_pop_proof_root=KEY_POP_ROOT,
        attestation_evidence=evidence() if attestation is None else attestation,
        trust_policy=policy() if trust is None else trust,
        session_identity=SESSION,
        action_digest=action,
        target_digest=TARGET_DIGEST,
        now_epoch=NOW,
    )


class AttestedRuntimeBindingTests(TestCase):
    def test_01_key_pop_alone_does_not_satisfy_required_attested_runtime(self):
        with self.assertRaisesRegex(AttestedRuntimeError, "ATTESTED_RUNTIME_EVIDENCE_REQUIRED"):
            verify(attestation={})

    def test_02_valid_attestation_produces_execution_specific_non_authority_receipt(self):
        receipt = verify()
        self.assertIsInstance(receipt, ExecutionAttestationVerificationReceipt)
        self.assertEqual(receipt.outcome, ATTESTED_RUNTIME_VERIFIED)
        self.assertFalse(receipt.authority_granted)
        self.assertEqual(receipt.key_pop_proof_root, KEY_POP_ROOT)
        self.assertEqual(receipt.measurement_digest, MEASUREMENT)
        self.assertEqual(len(receipt.trust_policy_root), 64)
        self.assertEqual(len(receipt.receipt_root), 64)

    def test_03_unendorsed_measurement_is_denied(self):
        with self.assertRaisesRegex(AttestedRuntimeError, "RUNTIME_MEASUREMENT_NOT_ENDORSED"):
            verify(attestation=evidence(measurement_digest="a" * 64))

    def test_04_runtime_principal_mismatch_is_denied(self):
        with self.assertRaisesRegex(AttestedRuntimeError, "ATTESTED_RUNTIME_PRINCIPAL_MISMATCH"):
            verify(attestation=evidence(runtime_principal="spiffe://aegis.example/runtime/other"))

    def test_05_attested_key_binding_must_match_current_key_pop(self):
        with self.assertRaisesRegex(AttestedRuntimeError, "ATTESTED_KEY_POP_BINDING_MISMATCH"):
            verify(attestation=evidence(key_binding_root="b" * 64))

    def test_06_authorization_scope_must_be_current(self):
        with self.assertRaisesRegex(AttestedRuntimeError, "AUTHORIZATION_SCOPE_MISMATCH"):
            verify(attestation=evidence(authorization_scope_root="c" * 64))

    def test_07_untrusted_attestation_verifier_is_denied(self):
        with self.assertRaisesRegex(AttestedRuntimeError, "ATTESTATION_VERIFIER_NOT_ALLOWED"):
            verify(attestation=evidence(verifier_identity="attacker:self-signed"))

    def test_08_stale_or_expired_attestation_is_denied(self):
        with self.assertRaisesRegex(AttestedRuntimeError, "ATTESTATION_EVIDENCE_STALE"):
            verify(attestation=evidence(issued_at_epoch=NOW - 301))
        with self.assertRaisesRegex(AttestedRuntimeError, "ATTESTATION_EVIDENCE_EXPIRED"):
            verify(attestation=evidence(expires_at_epoch=NOW))

    def test_09_authorization_receipt_is_not_execution_verification_receipt(self):
        receipt = verify()
        self.assertEqual(receipt.authorization_receipt_root, AUTHORIZATION_RECEIPT_ROOT)
        self.assertNotEqual(receipt.receipt_root, AUTHORIZATION_RECEIPT_ROOT)
        second = verify(action="8" * 64)
        self.assertNotEqual(receipt.receipt_root, second.receipt_root)

    def test_10_non_required_action_class_does_not_gain_fake_attestation_authority(self):
        receipt = verify(action_class="D2", attestation={})
        self.assertIsNone(receipt)

    def test_11_trust_policy_not_presented_evidence_controls_endorsed_measurement(self):
        attacker = evidence(measurement_digest="a" * 64)
        attacker["endorsed_measurements"] = [
            {"measurement_kind": "sha256:container-manifest", "measurement_digest": "a" * 64}
        ]
        with self.assertRaisesRegex(AttestedRuntimeError, "RUNTIME_MEASUREMENT_NOT_ENDORSED"):
            verify(attestation=attacker)

    def test_12_authority_entrypoints_keep_attestation_trust_outside_request_payload(self):
        env_source = (REPO_ROOT / "harness/sdk/authority_client.py").read_text(encoding="utf-8")
        cli_source = (REPO_ROOT / "scripts/automaton3-authority.py").read_text(encoding="utf-8")
        self.assertIn("AEGIS_RUNTIME_ATTESTATION_EVIDENCE_PATH", env_source)
        self.assertIn("AEGIS_RUNTIME_ATTESTATION_TRUST_POLICY_PATH", env_source)
        self.assertIn('parser.add_argument("--runtime-attestation-evidence"', cli_source)
        self.assertIn('parser.add_argument("--runtime-attestation-trust-policy"', cli_source)
        self.assertNotIn('request_payload.get("runtime_attestation_trust_policy")', cli_source)


if __name__ == "__main__":
    main()
