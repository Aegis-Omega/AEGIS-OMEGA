#!/usr/bin/env python3
"""Preregistered falsifiers for an AEGIS EAT-JWT attestation profile.

The profile is AEGIS-local. It uses RFC 9711 EAT/JWT semantics, RFC 10013
measured-component JSON, and the key-binding pattern from the work-in-progress
draft-reddy-rats-key-binding-02. It is not a claim of full conformance to that
draft and does not verify SCITT receipts.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from unittest import TestCase, main

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.eat_attestation_crypto import (  # noqa: E402
    AEGIS_EAT_JWT_PROFILE,
    EAT_ATTESTATION_CRYPTO_VERIFIED,
    EATAttestationCryptoError,
    EATJWTTrustPolicy,
    verify_eat_jwt_attestation,
)
from harness.sdk.runtime_pop_crypto import jwk_thumbprint  # noqa: E402

NOW = 1_787_500_000
NONCE = "TnJraVhEZm9xM2tIeE1UWA"
MEASUREMENT = "2" * 64
COMPONENT = "aegis-runtime"
ISSUER = "https://attester.example.test"
AUDIENCE = "aegis-runtime-verifier"

AK_PRIVATE = ec.generate_private_key(ec.SECP256R1())
SUBJECT_PRIVATE = ec.generate_private_key(ec.SECP256R1())
ATTACKER_PRIVATE = ec.generate_private_key(ec.SECP256R1())


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
        value["kid"] = kid
        value["alg"] = "ES256"
        value["use"] = "sig"
    return value


AK_JWK = public_jwk(AK_PRIVATE, kid="ak-1")
SUBJECT_JWK = public_jwk(SUBJECT_PRIVATE)
SUBJECT_JKT = jwk_thumbprint(SUBJECT_JWK)


def sign_es256(private_key, header: dict, claims: dict) -> str:
    head = b64u(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    body = b64u(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    signing_input = f"{head}.{body}".encode("ascii")
    der = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{head}.{body}.{b64u(raw)}"


def measurement_json(*, digest=MEASUREMENT, component=COMPONENT) -> str:
    return json.dumps(
        {
            "id": [component],
            "digested-measurement": ["sha-256", b64u(bytes.fromhex(digest))],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def claims(**overrides) -> dict:
    value = {
        "eat_profile": AEGIS_EAT_JWT_PROFILE,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": NOW - 10,
        "exp": NOW + 120,
        "eat_nonce": NONCE,
        "cnf": {"jwk": SUBJECT_JWK},
        "key-attributes": {
            "extractable": False,
            "never-extractable": True,
            "local": True,
        },
        "measurements": [[296, measurement_json()]],
    }
    value.update(overrides)
    return value


def token(*, payload=None, private_key=AK_PRIVATE, kid="ak-1", alg="ES256") -> str:
    return sign_es256(
        private_key,
        {"alg": alg, "kid": kid, "typ": "JWT"},
        claims() if payload is None else payload,
    )


def policy(**overrides) -> EATJWTTrustPolicy:
    value = {
        "schema_version": "1.0.0",
        "policy_id": "aegis-test-eat-jwt-v1",
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
    }
    value.update(overrides)
    return EATJWTTrustPolicy.from_mapping(value)


def verify(raw_token=None, *, expected_jkt=SUBJECT_JKT, nonce=NONCE, trust=None):
    return verify_eat_jwt_attestation(
        raw_token=token() if raw_token is None else raw_token,
        trust_policy=policy() if trust is None else trust,
        expected_subject_jkt=expected_jkt,
        expected_nonce=nonce,
        verification_time_epoch=NOW,
    )


class EATJWTAttestationCryptoTests(TestCase):
    def test_01_valid_signed_eat_binds_subject_key_measurement_and_nonce(self):
        receipt = verify()
        self.assertEqual(receipt.outcome, EAT_ATTESTATION_CRYPTO_VERIFIED)
        self.assertEqual(receipt.subject_jkt, SUBJECT_JKT)
        self.assertEqual(receipt.measurement_digest, MEASUREMENT)
        self.assertEqual(receipt.measurement_component, COMPONENT)
        self.assertFalse(receipt.authority_granted)
        self.assertEqual(len(receipt.trust_policy_root), 64)
        self.assertEqual(len(receipt.receipt_root), 64)

    def test_02_untrusted_attestation_key_signature_is_rejected(self):
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_SIGNATURE_INVALID"):
            verify(token(private_key=ATTACKER_PRIVATE))

    def test_03_verifier_nonce_is_required_and_exact(self):
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_NONCE_MISMATCH"):
            verify(nonce="different-nonce")
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_NONCE_INVALID"):
            verify(token(payload=claims(eat_nonce=[NONCE, "second"])))

    def test_04_cnf_subject_key_must_match_current_holder_key(self):
        other = public_jwk(ec.generate_private_key(ec.SECP256R1()))
        raw = token(payload=claims(cnf={"jwk": other}))
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_SUBJECT_KEY_MISMATCH"):
            verify(raw)

    def test_05_unendorsed_measured_component_is_rejected(self):
        raw = token(payload=claims(measurements=[[296, measurement_json(digest="a" * 64)]]))
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_MEASUREMENT_MISMATCH"):
            verify(raw)

    def test_06_wrong_component_or_measurement_format_is_rejected(self):
        raw = token(payload=claims(measurements=[[296, measurement_json(component="other")]]))
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_MEASURED_COMPONENT_NOT_FOUND"):
            verify(raw)
        raw = token(payload=claims(measurements=[[258, measurement_json()]]))
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_MEASURED_COMPONENT_NOT_FOUND"):
            verify(raw)

    def test_07_key_attributes_are_required_and_policy_checked(self):
        broken = claims()
        broken.pop("key-attributes")
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_KEY_ATTRIBUTES_REQUIRED"):
            verify(token(payload=broken))
        raw = token(payload=claims(**{"key-attributes": {"local": False, "never-extractable": True, "extractable": False}}))
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_KEY_ATTRIBUTE_MISMATCH"):
            verify(raw)

    def test_08_profile_issuer_audience_and_time_are_load_bearing(self):
        for replacement, code in [
            ({"eat_profile": "urn:attacker:profile"}, "EAT_PROFILE_MISMATCH"),
            ({"iss": "https://attacker.invalid"}, "EAT_ISSUER_MISMATCH"),
            ({"aud": "other"}, "EAT_AUDIENCE_MISMATCH"),
            ({"exp": NOW}, "EAT_EXPIRED"),
            ({"iat": NOW - 301}, "EAT_STALE"),
        ]:
            with self.subTest(code=code):
                with self.assertRaisesRegex(EATAttestationCryptoError, code):
                    verify(token(payload=claims(**replacement)))

    def test_09_kid_and_alg_are_selected_by_external_trust_policy(self):
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_ATTESTATION_KEY_NOT_UNIQUE"):
            verify(token(kid="unknown"))
        with self.assertRaisesRegex(EATAttestationCryptoError, "EAT_ALG_NOT_ALLOWED"):
            verify(token(alg="ES384"))

    def test_10_raw_token_is_not_retained_and_receipt_is_evidence_only(self):
        raw = token()
        receipt = verify(raw)
        rendered = repr(receipt)
        self.assertNotIn(raw, rendered)
        self.assertEqual(receipt.token_sha256, hashlib.sha256(raw.encode("ascii")).hexdigest())
        self.assertFalse(receipt.authority_granted)


if __name__ == "__main__":
    main()
