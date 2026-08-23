#!/usr/bin/env python3
"""Falsifiers for SCITT authorization registration evidence.

The first AEGIS SCITT profile is deliberately narrow and strong:
- authorization is an issuer-signed COSE_Sign1 statement with deterministic
  CBOR payload and empty unprotected header at registration;
- the Receipt is a COSE_Sign1 RFC9162_SHA256 inclusion receipt;
- both authorization issuer and Transparency Service keys/identities come from
  external trust policy;
- inclusion proof is recomputed over the exact Signed Statement bytes;
- the resulting registration receipt remains evidence-only and distinct from
  transaction-time EAT and execution verification receipts.
"""
from __future__ import annotations

import base64
import hashlib
import io
import sys
from pathlib import Path
from unittest import TestCase, main

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.scitt_authorization import (  # noqa: E402
    SCITT_AUTHORIZATION_REGISTRATION_VERIFIED,
    SCITTAuthorizationError,
    SCITTAuthorizationTrustPolicy,
    verify_scitt_authorization_registration,
)
from harness.sdk.runtime_pop_crypto import jwk_thumbprint  # noqa: E402

NOW = 1_787_500_000
SCOPE_ROOT = "1" * 64
MEASUREMENT = "2" * 64
AUTH_TIME_EVIDENCE_ROOT = "3" * 64
AUTH_ISSUER = "aegis.authorization.example"
AUTH_SUBJECT = "aegis.scope.calendar-write"
TS_ISSUER = "transparency.aegis.example"
TS_SUBJECT = "aegis.authorization-registry"
CONTENT_TYPE = "application/aegis-authorization+cbor"

AUTH_KEY = ec.generate_private_key(ec.SECP256R1())
TS_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())
HOLDER_KEY = ec.generate_private_key(ec.SECP256R1())


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def public_jwk(key, *, kid: str) -> dict:
    n = key.public_key().public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": b64u(n.x.to_bytes(32, "big")),
        "y": b64u(n.y.to_bytes(32, "big")),
        "kid": kid,
        "alg": "ES256",
        "use": "sig",
    }


AUTH_JWK = public_jwk(AUTH_KEY, kid="auth-1")
TS_JWK = public_jwk(TS_KEY, kid="ts-1")
HOLDER_JWK = public_jwk(HOLDER_KEY, kid="holder-1")
HOLDER_JKT = jwk_thumbprint(HOLDER_JWK)


def es256_sign(key, data: bytes) -> bytes:
    der = key.sign(data, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def cose_sign1(*, key, protected: dict, payload: bytes | None, unprotected: dict | None = None, detached_payload: bytes | None = None) -> bytes:
    protected_bstr = cbor2.dumps(protected, canonical=True)
    signing_payload = detached_payload if payload is None else payload
    if signing_payload is None:
        raise AssertionError("signing payload required")
    sig_structure = cbor2.dumps(["Signature1", protected_bstr, b"", signing_payload], canonical=True)
    signature = es256_sign(key, sig_structure)
    return cbor2.dumps(cbor2.CBORTag(18, [protected_bstr, unprotected or {}, payload, signature]), canonical=True)


def scope(*, holder_jkt=HOLDER_JKT, measurement=MEASUREMENT, expiry=NOW + 600) -> dict:
    return {
        "schema_version": "1.0.0",
        "scope_root": SCOPE_ROOT,
        "holder_jkt": holder_jkt,
        "measurement_digest": measurement,
        "authorization_time_evidence_root": AUTH_TIME_EVIDENCE_ROOT,
        "expires_at_epoch": expiry,
        "action_classes": ["D4"],
    }


def statement(*, scope_value=None, key=AUTH_KEY, unprotected=None, noncanonical_payload=False) -> bytes:
    payload_value = scope() if scope_value is None else scope_value
    if noncanonical_payload:
        # Valid CBOR map encoded in deliberately non-canonical key order.
        buf = io.BytesIO()
        enc = cbor2.CBOREncoder(buf, canonical=False)
        enc.encode(dict(reversed(list(payload_value.items()))))
        payload = buf.getvalue()
    else:
        payload = cbor2.dumps(payload_value, canonical=True)
    return cose_sign1(
        key=key,
        protected={1: -7, 3: CONTENT_TYPE, 4: b"auth-1", 15: {1: AUTH_ISSUER, 2: AUTH_SUBJECT}},
        unprotected={} if unprotected is None else unprotected,
        payload=payload,
    )


def leaf_hash(entry: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + entry).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def receipt_for(entry: bytes, *, ts_key=TS_KEY, ts_issuer=TS_ISSUER, ts_subject=TS_SUBJECT, vds=1, proof_entry=None) -> bytes:
    candidate = entry if proof_entry is None else proof_entry
    sibling = leaf_hash(b"aegis-test-sibling-entry")
    candidate_leaf = leaf_hash(candidate)
    root = node_hash(sibling, candidate_leaf)  # candidate is leaf index 1 of tree size 2
    proof = cbor2.dumps([2, 1, [sibling]], canonical=True)
    protected = {1: -7, 4: b"ts-1", 395: vds, 15: {1: ts_issuer, 2: ts_subject}}
    return cose_sign1(
        key=ts_key,
        protected=protected,
        unprotected={396: {-1: [proof]}},
        payload=None,
        detached_payload=root,
    )


def trust_policy(**overrides) -> SCITTAuthorizationTrustPolicy:
    value = {
        "schema_version": "1.0.0",
        "policy_id": "aegis-test-scitt-authz-v1",
        "authorization_issuer": AUTH_ISSUER,
        "authorization_subject": AUTH_SUBJECT,
        "authorization_issuer_jwks": {"keys": [AUTH_JWK]},
        "expected_content_type": CONTENT_TYPE,
        "transparency_service_issuer": TS_ISSUER,
        "transparency_service_subject": TS_SUBJECT,
        "transparency_service_jwks": {"keys": [TS_JWK]},
        "allowed_cose_algs": [-7],
        "required_vds": 1,
    }
    value.update(overrides)
    return SCITTAuthorizationTrustPolicy.from_mapping(value)


def verify(*, stmt=None, rcpt=None, holder=HOLDER_JKT, measurement=MEASUREMENT, scope_root=SCOPE_ROOT, policy=None, now=NOW):
    stmt = statement() if stmt is None else stmt
    rcpt = receipt_for(stmt) if rcpt is None else rcpt
    return verify_scitt_authorization_registration(
        signed_statement=stmt,
        receipt=rcpt,
        trust_policy=trust_policy() if policy is None else policy,
        expected_scope_root=scope_root,
        expected_holder_jkt=holder,
        expected_measurement_digest=measurement,
        verification_time_epoch=now,
    )


class SCITTAuthorizationReceiptTests(TestCase):
    def test_01_valid_signed_statement_inclusion_and_ts_receipt_produce_registration_receipt(self):
        result = verify()
        self.assertEqual(result.outcome, SCITT_AUTHORIZATION_REGISTRATION_VERIFIED)
        self.assertTrue(result.registration_verified)
        self.assertEqual(result.scope_root, SCOPE_ROOT)
        self.assertEqual(result.holder_jkt, HOLDER_JKT)
        self.assertEqual(result.measurement_digest, MEASUREMENT)
        self.assertEqual(result.authorization_time_evidence_root, AUTH_TIME_EVIDENCE_ROOT)
        self.assertEqual(result.tree_size, 2)
        self.assertEqual(result.leaf_index, 1)
        self.assertFalse(result.authority_granted)

    def test_02_authorization_statement_signature_is_reverified_locally(self):
        forged = statement(key=OTHER_KEY)
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_AUTHORIZATION_SIGNATURE_INVALID"):
            verify(stmt=forged, rcpt=receipt_for(forged))

    def test_03_transparency_service_receipt_requires_external_trust_anchor(self):
        stmt = statement()
        forged_receipt = receipt_for(stmt, ts_key=OTHER_KEY)
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_RECEIPT_CRYPTOGRAPHIC_VERIFICATION_FAILED"):
            verify(stmt=stmt, rcpt=forged_receipt)

    def test_04_receipt_inclusion_proof_binds_exact_signed_statement_bytes(self):
        stmt = statement()
        other = statement(scope_value={**scope(), "scope_root": "f" * 64})
        rcpt = receipt_for(stmt, proof_entry=other)
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_RECEIPT_CRYPTOGRAPHIC_VERIFICATION_FAILED"):
            verify(stmt=stmt, rcpt=rcpt)

    def test_05_transparency_service_identity_and_vds_are_exact(self):
        stmt = statement()
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_TS_ISSUER_MISMATCH"):
            verify(stmt=stmt, rcpt=receipt_for(stmt, ts_issuer="evil.example"))
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_VDS_UNSUPPORTED"):
            verify(stmt=stmt, rcpt=receipt_for(stmt, vds=99))

    def test_06_registered_statement_requires_empty_unprotected_header(self):
        stmt = statement(unprotected={394: [b"caller-receipt"]})
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_STATEMENT_UNPROTECTED_NOT_EMPTY"):
            verify(stmt=stmt, rcpt=receipt_for(stmt))

    def test_07_scope_holder_measurement_and_scope_root_are_load_bearing(self):
        stmt = statement()
        rcpt = receipt_for(stmt)
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_SCOPE_HOLDER_MISMATCH"):
            verify(stmt=stmt, rcpt=rcpt, holder="a" * 43)
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_SCOPE_MEASUREMENT_MISMATCH"):
            verify(stmt=stmt, rcpt=rcpt, measurement="e" * 64)
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_SCOPE_ROOT_MISMATCH"):
            verify(stmt=stmt, rcpt=rcpt, scope_root="d" * 64)

    def test_08_scope_expiry_is_checked_at_verifier_owned_time(self):
        stmt = statement(scope_value=scope(expiry=NOW - 1))
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_AUTHORIZATION_SCOPE_EXPIRED"):
            verify(stmt=stmt, rcpt=receipt_for(stmt))

    def test_09_authorization_scope_payload_must_use_deterministic_cbor(self):
        stmt = statement(noncanonical_payload=True)
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_AUTHORIZATION_PAYLOAD_NOT_DETERMINISTIC"):
            verify(stmt=stmt, rcpt=receipt_for(stmt))

    def test_10_receipt_never_retains_raw_statement_or_cose_receipt(self):
        stmt = statement()
        rcpt = receipt_for(stmt)
        result = verify(stmt=stmt, rcpt=rcpt)
        self.assertFalse(hasattr(result, "signed_statement"))
        self.assertFalse(hasattr(result, "receipt"))
        self.assertNotEqual(result.receipt_root, result.authorization_time_evidence_root)
        self.assertEqual(len(result.signed_statement_sha256), 64)
        self.assertEqual(len(result.cose_receipt_sha256), 64)

    def test_11_private_or_self_asserted_trust_key_material_is_forbidden(self):
        bad_key = dict(TS_JWK)
        bad_key["d"] = "attacker-private-material"
        with self.assertRaisesRegex(SCITTAuthorizationError, "SCITT_TRUST_JWKS_INVALID"):
            trust_policy(transparency_service_jwks={"keys": [bad_key]})

    def test_12_registration_receipt_is_evidence_not_execution_or_authority(self):
        result = verify()
        self.assertFalse(result.authority_granted)
        self.assertNotIn("execution", result.receipt_kind.lower())
        self.assertNotIn("effect", result.receipt_kind.lower())
        self.assertNotEqual(result.receipt_root, AUTH_TIME_EVIDENCE_ROOT)


if __name__ == "__main__":
    main()
