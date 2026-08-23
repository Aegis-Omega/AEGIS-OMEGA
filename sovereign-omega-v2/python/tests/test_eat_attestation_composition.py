#!/usr/bin/env python3
"""Composition falsifiers for EAT crypto -> attested runtime -> execution receipt.

This suite is intentionally stricter than the primitive EAT verifier. A signed
EAT may only satisfy the configured EAT runtime profile when it is composed with
the current cryptographic RuntimePoP holder key and the current trust-bound
RuntimePoP root. Caller-supplied structural VERIFIED fields are not an alternate
path when EAT mode is configured.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from unittest import TestCase, main

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.attested_runtime import AttestedRuntimeTrustPolicy  # noqa: E402
from harness.sdk.eat_attestation_authority import (  # noqa: E402
    EAT_ATTESTATION_VERIFIER_IDENTITY,
    EAT_RFC10013_MEASUREMENT_KIND,
    EATAttestationCompositionError,
    verify_eat_bound_attested_runtime_for_execution,
)
from harness.sdk.eat_attestation_crypto import (  # noqa: E402
    AEGIS_EAT_JWT_PROFILE,
    EATJWTTrustPolicy,
)
from harness.sdk.principal_binding import DPOP_CERT_BOUND, MTLS_CERT_BOUND  # noqa: E402
from harness.sdk.runtime_pop_crypto import (  # noqa: E402
    CRYPTO_RECEIPT_KIND,
    CRYPTO_SCHEMA_VERSION,
    CRYPTO_VERIFIER_IDENTITY,
    RuntimePoPCryptoReceipt,
    jwk_thumbprint,
)

NOW = 1_787_500_000
NONCE = "QWVnaXNFQVROYW5jZVYx"
RUNTIME = "spiffe://aegis.example/runtime/gateway-7"
MEASUREMENT = "2" * 64
SCOPE_ROOT = "3" * 64
AUTHORIZATION_RECEIPT_ROOT = "4" * 64
TRUST_BOUND_KEY_POP_ROOT = "5" * 64
ACTION_DIGEST = "6" * 64
TARGET_DIGEST = "7" * 64
SESSION = "session-1"
COMPONENT = "aegis-runtime"
ISSUER = "https://attester.example.test"
AUDIENCE = "aegis-runtime-verifier"

AK_PRIVATE = ec.generate_private_key(ec.SECP256R1())
SUBJECT_PRIVATE = ec.generate_private_key(ec.SECP256R1())
OTHER_SUBJECT_PRIVATE = ec.generate_private_key(ec.SECP256R1())


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def public_jwk(key, *, kid=None) -> dict:
    numbers = key.public_key().public_numbers()
    value = {
        "kty": "EC",
        "crv": "P-256",
        "x": b64u(numbers.x.to_bytes(32, "big")),
        "y": b64u(numbers.y.to_bytes(32, "big")),
    }
    if kid is not None:
        value.update({"kid": kid, "alg": "ES256", "use": "sig"})
    return value


AK_JWK = public_jwk(AK_PRIVATE, kid="ak-1")
SUBJECT_JWK = public_jwk(SUBJECT_PRIVATE)
SUBJECT_JKT = jwk_thumbprint(SUBJECT_JWK)
OTHER_SUBJECT_JWK = public_jwk(OTHER_SUBJECT_PRIVATE)


def sign_es256(private_key, header: dict, claims: dict) -> str:
    head = b64u(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    body = b64u(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    signing_input = f"{head}.{body}".encode("ascii")
    der = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{head}.{body}.{b64u(signature)}"


def measurement_json() -> str:
    return json.dumps(
        {
            "id": [COMPONENT],
            "digested-measurement": ["sha-256", b64u(bytes.fromhex(MEASUREMENT))],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def eat_token(*, subject_jwk=SUBJECT_JWK, nonce=NONCE) -> str:
    claims = {
        "eat_profile": AEGIS_EAT_JWT_PROFILE,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": NOW - 10,
        "exp": NOW + 120,
        "eat_nonce": nonce,
        "cnf": {"jwk": subject_jwk},
        "key-attributes": {
            "extractable": False,
            "never-extractable": True,
            "local": True,
        },
        "measurements": [[296, measurement_json()]],
    }
    return sign_es256(AK_PRIVATE, {"alg": "ES256", "kid": "ak-1", "typ": "JWT"}, claims)


def eat_policy() -> EATJWTTrustPolicy:
    return EATJWTTrustPolicy.from_mapping({
        "schema_version": "1.0.0",
        "policy_id": "aegis-test-eat-jwt-composition",
        "expected_profile": AEGIS_EAT_JWT_PROFILE,
        "expected_issuer": ISSUER,
        "expected_audience": AUDIENCE,
        "attestation_jwks": {"keys": [AK_JWK]},
        "allowed_algs": ["ES256"],
        "required_key_attributes": {
            "extractable": False,
            "never-extractable": True,
            "local": True,
        },
        "measured_component_name": COMPONENT,
        "measurement_algorithm": "sha-256",
        "endorsed_measurement_digest": MEASUREMENT,
        "max_token_age_seconds": 300,
    })


def structural_policy(*, scope=SCOPE_ROOT) -> AttestedRuntimeTrustPolicy:
    return AttestedRuntimeTrustPolicy.from_mapping({
        "schema_version": "1.0.0",
        "policy_id": "aegis-test-eat-structural-composition",
        "required_action_classes": ["D4"],
        "allowed_attestation_profiles": ["EAT_KEY_BOUND"],
        "allowed_verifier_identities": [EAT_ATTESTATION_VERIFIER_IDENTITY],
        "endorsed_measurements": [
            {
                "measurement_kind": EAT_RFC10013_MEASUREMENT_KIND,
                "measurement_digest": MEASUREMENT,
            }
        ],
        "authorization_scope_root": scope,
        "max_evidence_age_seconds": 300,
    })


def pop_receipt(*, dpop_jkt=SUBJECT_JKT, mode=DPOP_CERT_BOUND, verified=True) -> RuntimePoPCryptoReceipt:
    return RuntimePoPCryptoReceipt(
        schema_version=CRYPTO_SCHEMA_VERSION,
        receipt_kind=CRYPTO_RECEIPT_KIND,
        cryptographic_verified=verified,
        verifier_identity=CRYPTO_VERIFIER_IDENTITY,
        runtime_principal=RUNTIME,
        binding_mode=mode,
        verification_time_epoch=NOW,
        certificate_thumbprint_s256="NONE",
        dpop_jkt=dpop_jkt,
        access_token_sha256="8" * 64,
        dpop_proof_sha256="9" * 64,
        request_method="POST",
        request_uri="https://calendar.example.test/v1/events",
        proof_root="a" * 64,
    )


def compose(*, token=None, pop=None, scope_policy=None, action_class="D4", auth_receipt=AUTHORIZATION_RECEIPT_ROOT):
    return verify_eat_bound_attested_runtime_for_execution(
        action_class=action_class,
        runtime_principal=RUNTIME,
        runtime_pop_crypto_receipt=pop_receipt() if pop is None else pop,
        trust_bound_key_pop_root=TRUST_BOUND_KEY_POP_ROOT,
        raw_eat_token=eat_token() if token is None else token,
        eat_trust_policy=eat_policy(),
        attested_runtime_trust_policy=structural_policy() if scope_policy is None else scope_policy,
        expected_nonce=NONCE,
        authorization_receipt_root=auth_receipt,
        session_identity=SESSION,
        action_digest=ACTION_DIGEST,
        target_digest=TARGET_DIGEST,
        verification_time_epoch=NOW,
    )


class EATAttestationCompositionTests(TestCase):
    def test_01_valid_eat_crypto_receipt_derives_execution_specific_structural_receipt(self):
        eat_receipt, execution_receipt = compose()
        self.assertEqual(eat_receipt.subject_jkt, SUBJECT_JKT)
        self.assertEqual(execution_receipt.attestation_evidence_root, eat_receipt.receipt_root)
        self.assertEqual(execution_receipt.key_pop_proof_root, TRUST_BOUND_KEY_POP_ROOT)
        self.assertEqual(execution_receipt.authorization_receipt_root, AUTHORIZATION_RECEIPT_ROOT)
        self.assertEqual(execution_receipt.measurement_kind, EAT_RFC10013_MEASUREMENT_KIND)
        self.assertEqual(execution_receipt.verifier_identity, EAT_ATTESTATION_VERIFIER_IDENTITY)
        self.assertFalse(eat_receipt.authority_granted)
        self.assertFalse(execution_receipt.authority_granted)

    def test_02_eat_subject_key_is_bound_to_current_runtime_dpop_holder(self):
        with self.assertRaisesRegex(Exception, "EAT_SUBJECT_KEY_MISMATCH"):
            compose(token=eat_token(subject_jwk=OTHER_SUBJECT_JWK))

    def test_03_pure_mtls_cannot_satisfy_first_eat_key_binding_profile(self):
        with self.assertRaisesRegex(EATAttestationCompositionError, "EAT_DPOP_HOLDER_KEY_REQUIRED"):
            compose(pop=pop_receipt(dpop_jkt="NONE", mode=MTLS_CERT_BOUND))

    def test_04_unverified_or_wrong_runtime_pop_receipt_cannot_seed_attestation(self):
        with self.assertRaisesRegex(EATAttestationCompositionError, "EAT_RUNTIME_POP_CRYPTO_RECEIPT_INVALID"):
            compose(pop=pop_receipt(verified=False))
        wrong = pop_receipt()
        wrong = RuntimePoPCryptoReceipt(**{**wrong.__dict__, "runtime_principal": "spiffe://aegis.example/runtime/other"})
        with self.assertRaisesRegex(EATAttestationCompositionError, "EAT_RUNTIME_PRINCIPAL_MISMATCH"):
            compose(pop=wrong)

    def test_05_verifier_time_must_match_current_runtime_pop_verification_boundary(self):
        stale = pop_receipt()
        stale = RuntimePoPCryptoReceipt(**{**stale.__dict__, "verification_time_epoch": NOW - 1})
        with self.assertRaisesRegex(EATAttestationCompositionError, "EAT_RUNTIME_POP_TIME_MISMATCH"):
            compose(pop=stale)

    def test_06_authorization_receipt_remains_distinct_and_load_bearing(self):
        _, first = compose()
        _, second = compose(auth_receipt="b" * 64)
        self.assertNotEqual(first.receipt_root, first.authorization_receipt_root)
        self.assertNotEqual(first.receipt_root, second.receipt_root)

    def test_07_non_required_action_does_not_gain_attestation_or_authority(self):
        eat_receipt, execution_receipt = compose(action_class="D2")
        self.assertIsNone(eat_receipt)
        self.assertIsNone(execution_receipt)

    def test_08_authority_entrypoints_configure_eat_outside_request_and_forbid_structural_bypass(self):
        env_source = (REPO_ROOT / "harness/sdk/authority_client.py").read_text(encoding="utf-8")
        cli_source = (REPO_ROOT / "scripts/automaton3-authority.py").read_text(encoding="utf-8")
        self.assertIn("verify_eat_bound_attested_runtime_for_execution", env_source)
        self.assertIn("AEGIS_EAT_JWT_TOKEN_PATH", env_source)
        self.assertIn("AEGIS_EAT_JWT_TRUST_POLICY_PATH", env_source)
        self.assertIn("AEGIS_EAT_EXPECTED_NONCE", env_source)
        self.assertIn("AEGIS_AUTHORIZATION_RECEIPT_ROOT", env_source)
        self.assertIn("RUNTIME_ATTESTATION_STRUCTURAL_EVIDENCE_FORBIDDEN_WITH_EAT", env_source)
        self.assertIn('parser.add_argument("--eat-jwt-token"', cli_source)
        self.assertIn('parser.add_argument("--eat-jwt-trust-policy"', cli_source)
        self.assertIn('parser.add_argument("--eat-expected-nonce"', cli_source)
        self.assertIn('parser.add_argument("--authorization-receipt-root"', cli_source)
        self.assertIn("RUNTIME_ATTESTATION_STRUCTURAL_EVIDENCE_FORBIDDEN_WITH_EAT", cli_source)
        self.assertNotIn('request_payload.get("eat_jwt_trust_policy")', cli_source)
        self.assertNotIn('request_payload.get("authorization_receipt_root")', cli_source)


if __name__ == "__main__":
    main()
