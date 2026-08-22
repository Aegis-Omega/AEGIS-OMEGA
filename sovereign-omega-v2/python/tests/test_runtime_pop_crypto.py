#!/usr/bin/env python3
"""Cryptographic RuntimePoP falsifiers.

These tests intentionally distinguish structural binding evidence from cryptographic
proof. They exercise RFC 8705 certificate-bound access-token binding, RFC 9449
DPoP request proofs, and SPIFFE X.509-SVID validation. Passing these tests does
not itself grant AEGIS authority.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase, main

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.principal_binding import (  # noqa: E402
    DPOP_CERT_BOUND,
    MTLS_CERT_BOUND,
    MTLS_DPOP_CERT_BOUND,
    VERIFIED,
)
from harness.sdk.runtime_pop_crypto import (  # noqa: E402
    CRYPTO_VERIFIER_IDENTITY,
    CryptoVerificationError,
    InMemoryReplayStore,
    b64url_encode,
    jwk_thumbprint,
    verify_runtime_pop_evidence,
)

NOW = 1_787_500_000
RUNTIME = "spiffe://aegis.example/runtime/gateway-7"
ISSUER = "https://issuer.example.test"
AUDIENCE = "https://calendar.example.test"
REQUEST_METHOD = "POST"
REQUEST_URI = "https://calendar.example.test/v1/events?trace=ignored#fragment"
EXPECTED_HTU = "https://calendar.example.test/v1/events"


def _json_b64(value: dict) -> str:
    return b64url_encode(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _jwt(header: dict, payload: dict, private_key) -> str:
    signing_input = f"{_json_b64(header)}.{_json_b64(payload)}".encode("ascii")
    alg = header["alg"]
    if alg == "RS256":
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    elif alg == "ES256":
        der = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = __import__("cryptography.hazmat.primitives.asymmetric.utils", fromlist=["decode_dss_signature"]).decode_dss_signature(der)
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    else:  # pragma: no cover - test helper only
        raise AssertionError(alg)
    return f"{signing_input.decode('ascii')}.{b64url_encode(signature)}"


def _rsa_jwk(public_key, *, kid: str) -> dict:
    numbers = public_key.public_numbers()
    width = (numbers.n.bit_length() + 7) // 8
    return {
        "kty": "RSA",
        "kid": kid,
        "alg": "RS256",
        "use": "sig",
        "n": b64url_encode(numbers.n.to_bytes(width, "big")),
        "e": b64url_encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }


def _ec_jwk(public_key) -> dict:
    numbers = public_key.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": b64url_encode(numbers.x.to_bytes(32, "big")),
        "y": b64url_encode(numbers.y.to_bytes(32, "big")),
    }


def _cert_material(*, runtime: str = RUNTIME, uri_sans: tuple[str, ...] | None = None, leaf_ca: bool = False):
    root_key = ec.generate_private_key(ec.SECP256R1())
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AEGIS test root")])
    now = datetime.fromtimestamp(NOW, tz=timezone.utc)
    root = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(root_key, hashes.SHA256())
    )

    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AEGIS runtime")])
    sans = uri_sans if uri_sans is not None else (runtime,)
    leaf = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(root_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(v) for v in sans]), critical=False)
        .add_extension(x509.BasicConstraints(ca=leaf_ca, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=leaf_ca,
                crl_sign=leaf_ca,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(root_key, hashes.SHA256())
    )
    return root, root_key, leaf, leaf_key


def _pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def _der_b64(cert: x509.Certificate) -> str:
    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")


def _cert_thumbprint(cert: x509.Certificate) -> str:
    return b64url_encode(hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).digest())


def _token(*, issuer_key, issuer_jwk: dict, cnf: dict, exp: int = NOW + 300, audience: str = AUDIENCE) -> str:
    return _jwt(
        {"typ": "at+jwt", "alg": "RS256", "kid": issuer_jwk["kid"]},
        {"iss": ISSUER, "sub": "runtime-subject", "aud": audience, "iat": NOW - 5, "exp": exp, "cnf": cnf},
        issuer_key,
    )


def _dpop(*, dpop_key, dpop_jwk: dict, access_token: str, jti: str = "jti-0000000000000001", htm: str = REQUEST_METHOD, htu: str = EXPECTED_HTU, iat: int = NOW, nonce: str | None = None, ath: str | None = None) -> str:
    claims = {
        "jti": jti,
        "htm": htm,
        "htu": htu,
        "iat": iat,
        "ath": ath if ath is not None else b64url_encode(hashlib.sha256(access_token.encode("ascii")).digest()),
    }
    if nonce is not None:
        claims["nonce"] = nonce
    return _jwt({"typ": "dpop+jwt", "alg": "ES256", "jwk": dpop_jwk}, claims, dpop_key)


def _base_evidence(*, mode: str, access_token: str, issuer_jwk: dict) -> dict:
    return {
        "schema_version": "1.0.0",
        "binding_mode": mode,
        "runtime_principal": RUNTIME,
        "now_epoch": NOW,
        "request_method": REQUEST_METHOD,
        "request_uri": REQUEST_URI,
        "expected_issuer": ISSUER,
        "expected_audience": AUDIENCE,
        "issuer_jwks": {"keys": [issuer_jwk]},
        "access_token": access_token,
    }


class RuntimePoPCryptoTests(TestCase):
    def setUp(self) -> None:
        self.issuer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.issuer_jwk = _rsa_jwk(self.issuer_key.public_key(), kid="issuer-key-1")
        self.root, self.root_key, self.leaf, self.leaf_key = _cert_material()
        self.dpop_key = ec.generate_private_key(ec.SECP256R1())
        self.dpop_jwk = _ec_jwk(self.dpop_key.public_key())

    def _mtls_evidence(self, *, leaf: x509.Certificate | None = None, root: x509.Certificate | None = None, token: str | None = None) -> dict:
        leaf = leaf or self.leaf
        root = root or self.root
        token = token or _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"x5t#S256": _cert_thumbprint(leaf)})
        value = _base_evidence(mode=MTLS_CERT_BOUND, access_token=token, issuer_jwk=self.issuer_jwk)
        value.update({
            "tls_peer_certificate_der_b64": _der_b64(leaf),
            "x509_intermediates_pem": [],
            "x509_trust_roots_pem": [_pem(root)],
        })
        return value

    def _dpop_evidence(self, *, token: str | None = None, proof: str | None = None, nonce: str | None = None) -> dict:
        token = token or _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"jkt": jwk_thumbprint(self.dpop_jwk)})
        proof = proof or _dpop(dpop_key=self.dpop_key, dpop_jwk=self.dpop_jwk, access_token=token, nonce=nonce)
        value = _base_evidence(mode=DPOP_CERT_BOUND, access_token=token, issuer_jwk=self.issuer_jwk)
        value["dpop_proof"] = proof
        if nonce is not None:
            value["expected_nonce"] = nonce
        return value

    def test_01_valid_mtls_spiffe_and_rfc8705_binding_produces_crypto_receipt(self):
        receipt = verify_runtime_pop_evidence(self._mtls_evidence())
        self.assertTrue(receipt.cryptographic_verified)
        self.assertEqual(receipt.runtime_principal, RUNTIME)
        self.assertEqual(receipt.binding_mode, MTLS_CERT_BOUND)
        self.assertEqual(receipt.verifier_identity, CRYPTO_VERIFIER_IDENTITY)
        structural = receipt.to_runtime_pop_verification(generation=9)
        self.assertEqual(structural.verification_state, VERIFIED)
        self.assertEqual(structural.proof_root, receipt.proof_root)
        self.assertFalse(hasattr(receipt, "access_token"))

    def test_02_spiffe_subject_mismatch_fails_closed(self):
        _, _, wrong_leaf, _ = _cert_material(runtime="spiffe://aegis.example/runtime/other")
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"x5t#S256": _cert_thumbprint(wrong_leaf)})
        evidence = self._mtls_evidence(leaf=wrong_leaf, token=token)
        with self.assertRaisesRegex(CryptoVerificationError, "SPIFFE_ID_MISMATCH"):
            verify_runtime_pop_evidence(evidence)

    def test_03_multiple_uri_sans_are_rejected(self):
        _, _, leaf, _ = _cert_material(uri_sans=(RUNTIME, "spiffe://aegis.example/runtime/alias"))
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"x5t#S256": _cert_thumbprint(leaf)})
        with self.assertRaisesRegex(CryptoVerificationError, "SPIFFE_URI_SAN_COUNT_INVALID"):
            verify_runtime_pop_evidence(self._mtls_evidence(leaf=leaf, token=token))

    def test_04_ca_certificate_cannot_authenticate_as_runtime_leaf(self):
        _, _, leaf, _ = _cert_material(leaf_ca=True)
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"x5t#S256": _cert_thumbprint(leaf)})
        with self.assertRaises(CryptoVerificationError):
            verify_runtime_pop_evidence(self._mtls_evidence(leaf=leaf, token=token))

    def test_05_untrusted_x509_path_is_rejected(self):
        other_root, _, _, _ = _cert_material(runtime="spiffe://aegis.example/runtime/unused")
        evidence = self._mtls_evidence(root=other_root)
        with self.assertRaisesRegex(CryptoVerificationError, "X509_PATH_INVALID"):
            verify_runtime_pop_evidence(evidence)

    def test_06_rfc8705_certificate_thumbprint_must_match_live_peer_cert(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"x5t#S256": "wrong"})
        with self.assertRaisesRegex(CryptoVerificationError, "MTLS_TOKEN_CERT_BINDING_MISMATCH"):
            verify_runtime_pop_evidence(self._mtls_evidence(token=token))

    def test_07_access_token_signature_is_verified_not_parsed_only(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"x5t#S256": _cert_thumbprint(self.leaf)})
        header, payload, signature = token.split(".")
        tampered = f"{header}.{_json_b64({'iss': ISSUER, 'sub': 'attacker', 'aud': AUDIENCE, 'iat': NOW - 5, 'exp': NOW + 300, 'cnf': {'x5t#S256': _cert_thumbprint(self.leaf)}})}.{signature}"
        with self.assertRaisesRegex(CryptoVerificationError, "ACCESS_TOKEN_SIGNATURE_INVALID"):
            verify_runtime_pop_evidence(self._mtls_evidence(token=tampered))

    def test_08_valid_dpop_signature_request_binding_token_hash_and_jkt_pass(self):
        replay = InMemoryReplayStore()
        receipt = verify_runtime_pop_evidence(self._dpop_evidence(), replay_store=replay)
        self.assertTrue(receipt.cryptographic_verified)
        self.assertEqual(receipt.binding_mode, DPOP_CERT_BOUND)
        self.assertEqual(receipt.dpop_jkt, jwk_thumbprint(self.dpop_jwk))

    def test_09_dpop_bad_signature_is_rejected(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"jkt": jwk_thumbprint(self.dpop_jwk)})
        other_key = ec.generate_private_key(ec.SECP256R1())
        proof = _dpop(dpop_key=other_key, dpop_jwk=self.dpop_jwk, access_token=token)
        with self.assertRaisesRegex(CryptoVerificationError, "DPOP_SIGNATURE_INVALID"):
            verify_runtime_pop_evidence(self._dpop_evidence(token=token, proof=proof), replay_store=InMemoryReplayStore())

    def test_10_dpop_http_method_and_target_are_exact(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"jkt": jwk_thumbprint(self.dpop_jwk)})
        wrong_method = _dpop(dpop_key=self.dpop_key, dpop_jwk=self.dpop_jwk, access_token=token, htm="GET")
        with self.assertRaisesRegex(CryptoVerificationError, "DPOP_HTM_MISMATCH"):
            verify_runtime_pop_evidence(self._dpop_evidence(token=token, proof=wrong_method), replay_store=InMemoryReplayStore())
        wrong_uri = _dpop(dpop_key=self.dpop_key, dpop_jwk=self.dpop_jwk, access_token=token, htu="https://calendar.example.test/v1/other")
        with self.assertRaisesRegex(CryptoVerificationError, "DPOP_HTU_MISMATCH"):
            verify_runtime_pop_evidence(self._dpop_evidence(token=token, proof=wrong_uri), replay_store=InMemoryReplayStore())

    def test_11_stale_dpop_iat_is_rejected(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"jkt": jwk_thumbprint(self.dpop_jwk)})
        proof = _dpop(dpop_key=self.dpop_key, dpop_jwk=self.dpop_jwk, access_token=token, iat=NOW - 301)
        with self.assertRaisesRegex(CryptoVerificationError, "DPOP_IAT_STALE"):
            verify_runtime_pop_evidence(self._dpop_evidence(token=token, proof=proof), replay_store=InMemoryReplayStore())

    def test_12_dpop_ath_must_bind_the_presented_access_token(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"jkt": jwk_thumbprint(self.dpop_jwk)})
        proof = _dpop(dpop_key=self.dpop_key, dpop_jwk=self.dpop_jwk, access_token=token, ath="wrong")
        with self.assertRaisesRegex(CryptoVerificationError, "DPOP_ATH_MISMATCH"):
            verify_runtime_pop_evidence(self._dpop_evidence(token=token, proof=proof), replay_store=InMemoryReplayStore())

    def test_13_dpop_jti_is_single_use_within_replay_window(self):
        replay = InMemoryReplayStore()
        evidence = self._dpop_evidence()
        verify_runtime_pop_evidence(evidence, replay_store=replay)
        with self.assertRaisesRegex(CryptoVerificationError, "DPOP_REPLAY_DETECTED"):
            verify_runtime_pop_evidence(evidence, replay_store=replay)

    def test_14_server_nonce_is_enforced_when_required(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"jkt": jwk_thumbprint(self.dpop_jwk)})
        proof = _dpop(dpop_key=self.dpop_key, dpop_jwk=self.dpop_jwk, access_token=token, nonce="old-nonce")
        evidence = self._dpop_evidence(token=token, proof=proof)
        evidence["expected_nonce"] = "new-nonce"
        with self.assertRaisesRegex(CryptoVerificationError, "DPOP_NONCE_MISMATCH"):
            verify_runtime_pop_evidence(evidence, replay_store=InMemoryReplayStore())

    def test_15_access_token_dpop_key_thumbprint_is_enforced(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"jkt": "wrong"})
        proof = _dpop(dpop_key=self.dpop_key, dpop_jwk=self.dpop_jwk, access_token=token)
        with self.assertRaisesRegex(CryptoVerificationError, "DPOP_TOKEN_KEY_BINDING_MISMATCH"):
            verify_runtime_pop_evidence(self._dpop_evidence(token=token, proof=proof), replay_store=InMemoryReplayStore())

    def test_16_combined_mode_requires_and_verifies_both_bindings(self):
        token = _token(
            issuer_key=self.issuer_key,
            issuer_jwk=self.issuer_jwk,
            cnf={"x5t#S256": _cert_thumbprint(self.leaf), "jkt": jwk_thumbprint(self.dpop_jwk)},
        )
        proof = _dpop(dpop_key=self.dpop_key, dpop_jwk=self.dpop_jwk, access_token=token)
        evidence = _base_evidence(mode=MTLS_DPOP_CERT_BOUND, access_token=token, issuer_jwk=self.issuer_jwk)
        evidence.update({
            "tls_peer_certificate_der_b64": _der_b64(self.leaf),
            "x509_intermediates_pem": [],
            "x509_trust_roots_pem": [_pem(self.root)],
            "dpop_proof": proof,
        })
        receipt = verify_runtime_pop_evidence(evidence, replay_store=InMemoryReplayStore())
        self.assertEqual(receipt.binding_mode, MTLS_DPOP_CERT_BOUND)
        self.assertTrue(receipt.certificate_thumbprint_s256)
        self.assertTrue(receipt.dpop_jkt)

    def test_17_bearer_or_unknown_mode_never_enters_crypto_verified_state(self):
        token = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={})
        evidence = _base_evidence(mode="BEARER_ONLY", access_token=token, issuer_jwk=self.issuer_jwk)
        with self.assertRaisesRegex(CryptoVerificationError, "CRYPTO_POP_MODE_REQUIRED"):
            verify_runtime_pop_evidence(evidence)

    def test_18_expired_or_wrong_audience_access_token_fails_closed(self):
        expired = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"x5t#S256": _cert_thumbprint(self.leaf)}, exp=NOW - 1)
        with self.assertRaisesRegex(CryptoVerificationError, "ACCESS_TOKEN_EXPIRED"):
            verify_runtime_pop_evidence(self._mtls_evidence(token=expired))
        wrong_aud = _token(issuer_key=self.issuer_key, issuer_jwk=self.issuer_jwk, cnf={"x5t#S256": _cert_thumbprint(self.leaf)}, audience="https://other.example.test")
        with self.assertRaisesRegex(CryptoVerificationError, "ACCESS_TOKEN_AUDIENCE_MISMATCH"):
            verify_runtime_pop_evidence(self._mtls_evidence(token=wrong_aud))


if __name__ == "__main__":
    main()
