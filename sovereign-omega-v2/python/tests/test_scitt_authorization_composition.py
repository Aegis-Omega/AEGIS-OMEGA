#!/usr/bin/env python3
"""Composition falsifiers for SCITT registration -> transaction-time EAT."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.attested_runtime import AttestedRuntimeTrustPolicy  # noqa: E402
from harness.sdk.eat_attestation_crypto import AEGIS_EAT_JWT_PROFILE, EATJWTTrustPolicy  # noqa: E402
from harness.sdk.principal_binding import DPOP_CERT_BOUND, MTLS_CERT_BOUND  # noqa: E402
from harness.sdk.runtime_pop_crypto import (  # noqa: E402
    CRYPTO_RECEIPT_KIND,
    CRYPTO_SCHEMA_VERSION,
    CRYPTO_VERIFIER_IDENTITY,
    RuntimePoPCryptoReceipt,
)
from harness.sdk.scitt_authorization import SCITTAuthorizationTrustPolicy  # noqa: E402
from harness.sdk.scitt_authorization_authority import (  # noqa: E402
    SCITTAuthorizationCompositionError,
    verify_scitt_authorization_for_current_runtime,
)

NOW = 1_787_500_000
RUNTIME = "spiffe://aegis.example/runtime/gateway-7"
HOLDER_JKT = "holder-jkt-current"
MEASUREMENT = "2" * 64
SCOPE_ROOT = "3" * 64


def pop_receipt(*, mode=DPOP_CERT_BOUND, dpop_jkt=HOLDER_JKT, verified=True, when=NOW):
    return RuntimePoPCryptoReceipt(
        schema_version=CRYPTO_SCHEMA_VERSION,
        receipt_kind=CRYPTO_RECEIPT_KIND,
        cryptographic_verified=verified,
        verifier_identity=CRYPTO_VERIFIER_IDENTITY,
        runtime_principal=RUNTIME,
        binding_mode=mode,
        verification_time_epoch=when,
        certificate_thumbprint_s256="NONE",
        dpop_jkt=dpop_jkt,
        access_token_sha256="4" * 64,
        dpop_proof_sha256="5" * 64,
        request_method="POST",
        request_uri="https://calendar.example.test/v1/events",
        proof_root="6" * 64,
    )


def eat_policy():
    return EATJWTTrustPolicy.from_mapping({
        "schema_version": "1.0.0",
        "policy_id": "eat-composition-test",
        "expected_profile": AEGIS_EAT_JWT_PROFILE,
        "expected_issuer": "https://attester.example.test",
        "expected_audience": "aegis-runtime-verifier",
        "attestation_jwks": {"keys": [{
            "kty": "EC", "crv": "P-256", "kid": "ak-1", "alg": "ES256", "use": "sig",
            "x": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "y": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE",
        }]},
        "allowed_algs": ["ES256"],
        "required_key_attributes": {"extractable": False},
        "measured_component_name": "aegis-runtime",
        "measurement_algorithm": "sha-256",
        "endorsed_measurement_digest": MEASUREMENT,
        "max_token_age_seconds": 300,
    })


def attested_policy():
    return AttestedRuntimeTrustPolicy.from_mapping({
        "schema_version": "1.0.0",
        "policy_id": "attested-composition-test",
        "required_action_classes": ["D4"],
        "allowed_attestation_profiles": ["EAT_KEY_BOUND"],
        "allowed_verifier_identities": ["aegis:eat-jwt-attestation-crypto-v1"],
        "endorsed_measurements": [{
            "measurement_kind": "sha256:rfc10013-measured-component",
            "measurement_digest": MEASUREMENT,
        }],
        "authorization_scope_root": SCOPE_ROOT,
        "max_evidence_age_seconds": 300,
    })


def scitt_policy():
    # Keys are structurally valid; crypto is mocked in these composition tests.
    return SCITTAuthorizationTrustPolicy.from_mapping({
        "schema_version": "1.0.0",
        "policy_id": "scitt-composition-test",
        "authorization_issuer": "auth.example",
        "authorization_subject": "scope.example",
        "authorization_issuer_jwks": {"keys": [{
            "kty": "EC", "crv": "P-256", "kid": "auth-1", "alg": "ES256", "use": "sig",
            "x": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "y": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE",
        }]},
        "expected_content_type": "application/aegis-authorization+cbor",
        "transparency_service_issuer": "ts.example",
        "transparency_service_subject": "registry.example",
        "transparency_service_jwks": {"keys": [{
            "kty": "EC", "crv": "P-256", "kid": "ts-1", "alg": "ES256", "use": "sig",
            "x": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "y": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE",
        }]},
        "allowed_cose_algs": [-7],
        "required_vds": 1,
    })


def verified_registration_fixture(*, authority=False):
    return SimpleNamespace(
        receipt_root="a" * 64,
        authority_granted=authority,
        registration_verified=True,
        holder_jkt=HOLDER_JKT,
        measurement_digest=MEASUREMENT,
        scope_root=SCOPE_ROOT,
        verification_time_epoch=NOW,
    )


class SCITTAuthorizationCompositionTests(TestCase):
    def test_01_current_holder_measurement_scope_and_time_are_derived_not_caller_selected(self):
        captured = {}
        sentinel = verified_registration_fixture()

        def verifier(**kwargs):
            captured.update(kwargs)
            return sentinel

        with patch(
            "harness.sdk.scitt_authorization_authority.verify_scitt_authorization_registration",
            side_effect=verifier,
        ):
            result = verify_scitt_authorization_for_current_runtime(
                signed_statement=b"statement",
                receipt=b"receipt",
                scitt_trust_policy=scitt_policy(),
                runtime_pop_crypto_receipt=pop_receipt(),
                eat_trust_policy=eat_policy(),
                attested_runtime_trust_policy=attested_policy(),
                verification_time_epoch=NOW,
            )
        self.assertIs(result, sentinel)
        self.assertEqual(captured["expected_holder_jkt"], HOLDER_JKT)
        self.assertEqual(captured["expected_measurement_digest"], MEASUREMENT)
        self.assertEqual(captured["expected_scope_root"], SCOPE_ROOT)
        self.assertEqual(captured["verification_time_epoch"], NOW)

    def test_02_pure_mtls_or_missing_holder_key_cannot_seed_scitt_eat_profile(self):
        with self.assertRaisesRegex(SCITTAuthorizationCompositionError, "SCITT_DPOP_HOLDER_KEY_REQUIRED"):
            verify_scitt_authorization_for_current_runtime(
                signed_statement=b"statement", receipt=b"receipt",
                scitt_trust_policy=scitt_policy(),
                runtime_pop_crypto_receipt=pop_receipt(mode=MTLS_CERT_BOUND, dpop_jkt="NONE"),
                eat_trust_policy=eat_policy(),
                attested_runtime_trust_policy=attested_policy(),
                verification_time_epoch=NOW,
            )

    def test_03_unverified_runtime_pop_or_time_mismatch_fails_closed(self):
        with self.assertRaisesRegex(SCITTAuthorizationCompositionError, "SCITT_RUNTIME_POP_CRYPTO_RECEIPT_INVALID"):
            verify_scitt_authorization_for_current_runtime(
                signed_statement=b"statement", receipt=b"receipt",
                scitt_trust_policy=scitt_policy(), runtime_pop_crypto_receipt=pop_receipt(verified=False),
                eat_trust_policy=eat_policy(), attested_runtime_trust_policy=attested_policy(),
                verification_time_epoch=NOW,
            )
        with self.assertRaisesRegex(SCITTAuthorizationCompositionError, "SCITT_RUNTIME_POP_TIME_MISMATCH"):
            verify_scitt_authorization_for_current_runtime(
                signed_statement=b"statement", receipt=b"receipt",
                scitt_trust_policy=scitt_policy(), runtime_pop_crypto_receipt=pop_receipt(when=NOW - 1),
                eat_trust_policy=eat_policy(), attested_runtime_trust_policy=attested_policy(),
                verification_time_epoch=NOW,
            )

    def test_04_scitt_registration_receipt_never_becomes_authority(self):
        sentinel = verified_registration_fixture(authority=True)
        with patch(
            "harness.sdk.scitt_authorization_authority.verify_scitt_authorization_registration",
            return_value=sentinel,
        ):
            with self.assertRaisesRegex(SCITTAuthorizationCompositionError, "SCITT_REGISTRATION_RECEIPT_AUTHORITY_FORBIDDEN"):
                verify_scitt_authorization_for_current_runtime(
                    signed_statement=b"statement", receipt=b"receipt",
                    scitt_trust_policy=scitt_policy(), runtime_pop_crypto_receipt=pop_receipt(),
                    eat_trust_policy=eat_policy(), attested_runtime_trust_policy=attested_policy(),
                    verification_time_epoch=NOW,
                )

    def test_05_authority_entrypoints_derive_root_from_scitt_and_forbid_free_root_bypass(self):
        env_source = (REPO_ROOT / "harness/sdk/authority_client.py").read_text(encoding="utf-8")
        cli_source = (REPO_ROOT / "scripts/automaton3-authority.py").read_text(encoding="utf-8")
        for source in (env_source, cli_source):
            self.assertIn("verify_scitt_authorization_for_current_runtime", source)
            self.assertIn("RAW_AUTHORIZATION_RECEIPT_ROOT_FORBIDDEN_WITH_SCITT", source)
            self.assertIn("scitt_registration_receipt.receipt_root", source)
            self.assertIn("runtime_scitt_authorization_receipt_root", source)
        self.assertIn("AEGIS_SCITT_AUTHORIZATION_STATEMENT_PATH", env_source)
        self.assertIn("AEGIS_SCITT_AUTHORIZATION_RECEIPT_PATH", env_source)
        self.assertIn("AEGIS_SCITT_TRUST_POLICY_PATH", env_source)
        self.assertIn('parser.add_argument("--scitt-authorization-statement"', cli_source)
        self.assertIn('parser.add_argument("--scitt-authorization-receipt"', cli_source)
        self.assertIn('parser.add_argument("--scitt-trust-policy"', cli_source)
        self.assertNotIn('request_payload.get("scitt_trust_policy")', cli_source)


if __name__ == "__main__":
    main()
