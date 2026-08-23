"""Cryptographic verifier for the AEGIS EAT-JWT key/measurement profile.

The profile is deliberately AEGIS-local. It composes stable RFC mechanisms with
one work-in-progress key-attestation pattern:

* RFC 9711: JSON/JWT EAT, ``eat_profile`` and ``eat_nonce``;
* RFC 7800: JWT ``cnf.jwk`` proof-of-possession key semantics;
* RFC 10013: measured-component JSON (content-format 296);
* draft-reddy-rats-key-binding-02: the *pattern* that an AK-signed EAT cnf key,
  key-protection attributes, and protocol-level PoP are checked together.

This module does not claim full conformance to the Internet-Draft, does not
verify SCITT receipts, and never grants AEGIS authority. Attestation verification
keys and endorsed reference measurements come only from an external trust
policy; presented EAT claims cannot self-endorse them.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from harness.sdk.principal_binding import canonical_hash
from harness.sdk.runtime_pop_crypto import jwk_thumbprint

SCHEMA_VERSION = "1.0.0"
AEGIS_EAT_JWT_PROFILE = "urn:aegis:eat-jwt-key-measurement:v1"
EAT_ATTESTATION_CRYPTO_VERIFIED = "EAT_ATTESTATION_CRYPTO_VERIFIED"
RECEIPT_KIND = "AEGIS_EAT_JWT_ATTESTATION_CRYPTO_RECEIPT_V1"
TRUST_POLICY_KIND = "AEGIS_EAT_JWT_ATTESTATION_TRUST_POLICY_V1"
RECEIPT_DOMAIN = "AEGIS_EAT_JWT_ATTESTATION_CRYPTO_RECEIPT_V1"
RFC10013_MEASURED_COMPONENT_JSON = 296
SUPPORTED_ALGS = frozenset(("ES256", "RS256"))
PRIVATE_JWK_MEMBERS = frozenset(("d", "p", "q", "dp", "dq", "qi", "oth", "k"))
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class EATAttestationCryptoError(ValueError):
    """Fail-closed EAT verifier error carrying a stable denial code."""


def _string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EATAttestationCryptoError(code)
    return value


def _integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EATAttestationCryptoError(code)
    return value


def _hex64(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EATAttestationCryptoError(code)
    return value


def _b64u_decode(value: str, code: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise EATAttestationCryptoError(code)
    try:
        padded = value + "=" * ((4 - len(value) % 4) % 4)
        return base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except Exception as exc:
        raise EATAttestationCryptoError(code) from exc


def _parse_jwt(raw_token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    token = _string(raw_token, "EAT_JWT_INVALID")
    parts = token.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise EATAttestationCryptoError("EAT_JWT_INVALID")
    try:
        header = json.loads(_b64u_decode(parts[0], "EAT_JWT_INVALID"))
        claims = json.loads(_b64u_decode(parts[1], "EAT_JWT_INVALID"))
        signature = _b64u_decode(parts[2], "EAT_JWT_INVALID")
    except EATAttestationCryptoError:
        raise
    except Exception as exc:
        raise EATAttestationCryptoError("EAT_JWT_INVALID") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise EATAttestationCryptoError("EAT_JWT_INVALID")
    return header, claims, f"{parts[0]}.{parts[1]}".encode("ascii"), signature


def _public_key_from_jwk(jwk: Mapping[str, Any]):
    if not isinstance(jwk, Mapping) or PRIVATE_JWK_MEMBERS.intersection(jwk.keys()):
        raise EATAttestationCryptoError("EAT_JWK_INVALID")
    try:
        if jwk.get("kty") == "EC":
            if jwk.get("crv") != "P-256":
                raise EATAttestationCryptoError("EAT_JWK_INVALID")
            x = _b64u_decode(_string(jwk.get("x"), "EAT_JWK_INVALID"), "EAT_JWK_INVALID")
            y = _b64u_decode(_string(jwk.get("y"), "EAT_JWK_INVALID"), "EAT_JWK_INVALID")
            if len(x) != 32 or len(y) != 32:
                raise EATAttestationCryptoError("EAT_JWK_INVALID")
            return ec.EllipticCurvePublicNumbers(
                int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
            ).public_key()
        if jwk.get("kty") == "RSA":
            n = int.from_bytes(_b64u_decode(_string(jwk.get("n"), "EAT_JWK_INVALID"), "EAT_JWK_INVALID"), "big")
            e = int.from_bytes(_b64u_decode(_string(jwk.get("e"), "EAT_JWK_INVALID"), "EAT_JWK_INVALID"), "big")
            if n <= 0 or e <= 1:
                raise EATAttestationCryptoError("EAT_JWK_INVALID")
            return rsa.RSAPublicNumbers(e=e, n=n).public_key()
    except EATAttestationCryptoError:
        raise
    except Exception as exc:
        raise EATAttestationCryptoError("EAT_JWK_INVALID") from exc
    raise EATAttestationCryptoError("EAT_JWK_INVALID")


def _verify_signature(*, alg: str, jwk: Mapping[str, Any], signing_input: bytes, signature: bytes) -> None:
    key = _public_key_from_jwk(jwk)
    try:
        if alg == "ES256":
            if not isinstance(key, ec.EllipticCurvePublicKey) or len(signature) != 64:
                raise EATAttestationCryptoError("EAT_SIGNATURE_INVALID")
            r = int.from_bytes(signature[:32], "big")
            s = int.from_bytes(signature[32:], "big")
            key.verify(encode_dss_signature(r, s), signing_input, ec.ECDSA(hashes.SHA256()))
            return
        if alg == "RS256":
            if not isinstance(key, rsa.RSAPublicKey):
                raise EATAttestationCryptoError("EAT_SIGNATURE_INVALID")
            key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
            return
    except EATAttestationCryptoError:
        raise
    except InvalidSignature as exc:
        raise EATAttestationCryptoError("EAT_SIGNATURE_INVALID") from exc
    except Exception as exc:
        raise EATAttestationCryptoError("EAT_SIGNATURE_INVALID") from exc
    raise EATAttestationCryptoError("EAT_ALG_NOT_ALLOWED")


@dataclass(frozen=True)
class EATJWTTrustPolicy:
    schema_version: str
    policy_id: str
    expected_profile: str
    expected_issuer: str
    expected_audience: str
    attestation_jwks: Mapping[str, Any]
    allowed_algs: tuple[str, ...]
    required_key_attributes: Mapping[str, Any]
    measured_component_name: str
    measurement_algorithm: str
    endorsed_measurement_digest: str
    max_token_age_seconds: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EATJWTTrustPolicy":
        if not isinstance(value, Mapping):
            raise EATAttestationCryptoError("EAT_TRUST_POLICY_NOT_OBJECT")
        if value.get("schema_version") != SCHEMA_VERSION:
            raise EATAttestationCryptoError("EAT_TRUST_POLICY_SCHEMA_UNSUPPORTED")

        raw_jwks = value.get("attestation_jwks")
        if not isinstance(raw_jwks, Mapping) or not isinstance(raw_jwks.get("keys"), list) or not raw_jwks["keys"]:
            raise EATAttestationCryptoError("EAT_ATTESTATION_JWKS_INVALID")
        keys: list[dict[str, Any]] = []
        for item in raw_jwks["keys"]:
            if not isinstance(item, Mapping) or PRIVATE_JWK_MEMBERS.intersection(item.keys()):
                raise EATAttestationCryptoError("EAT_ATTESTATION_JWKS_INVALID")
            keys.append(dict(item))

        raw_algs = value.get("allowed_algs")
        if not isinstance(raw_algs, list) or not raw_algs or any(item not in SUPPORTED_ALGS for item in raw_algs):
            raise EATAttestationCryptoError("EAT_ALLOWED_ALGS_INVALID")
        if len(raw_algs) != len(set(raw_algs)):
            raise EATAttestationCryptoError("EAT_ALLOWED_ALGS_INVALID")

        raw_attrs = value.get("required_key_attributes")
        if not isinstance(raw_attrs, Mapping) or not raw_attrs:
            raise EATAttestationCryptoError("EAT_REQUIRED_KEY_ATTRIBUTES_INVALID")
        required_attrs: dict[str, Any] = {}
        for key, expected in raw_attrs.items():
            if not isinstance(key, str) or not key or not isinstance(expected, (bool, str, int)):
                raise EATAttestationCryptoError("EAT_REQUIRED_KEY_ATTRIBUTES_INVALID")
            required_attrs[key] = expected

        algorithm = _string(value.get("measurement_algorithm"), "EAT_MEASUREMENT_ALGORITHM_INVALID")
        if algorithm != "sha-256":
            raise EATAttestationCryptoError("EAT_MEASUREMENT_ALGORITHM_UNSUPPORTED")
        max_age = _integer(value.get("max_token_age_seconds"), "EAT_MAX_TOKEN_AGE_INVALID")
        if max_age <= 0:
            raise EATAttestationCryptoError("EAT_MAX_TOKEN_AGE_INVALID")

        return cls(
            schema_version=SCHEMA_VERSION,
            policy_id=_string(value.get("policy_id"), "EAT_POLICY_ID_MISSING"),
            expected_profile=_string(value.get("expected_profile"), "EAT_EXPECTED_PROFILE_MISSING"),
            expected_issuer=_string(value.get("expected_issuer"), "EAT_EXPECTED_ISSUER_MISSING"),
            expected_audience=_string(value.get("expected_audience"), "EAT_EXPECTED_AUDIENCE_MISSING"),
            attestation_jwks={"keys": keys},
            allowed_algs=tuple(raw_algs),
            required_key_attributes=required_attrs,
            measured_component_name=_string(value.get("measured_component_name"), "EAT_MEASURED_COMPONENT_NAME_MISSING"),
            measurement_algorithm=algorithm,
            endorsed_measurement_digest=_hex64(value.get("endorsed_measurement_digest"), "EAT_ENDORSED_MEASUREMENT_INVALID"),
            max_token_age_seconds=max_age,
        )

    @property
    def root(self) -> str:
        return canonical_hash(
            TRUST_POLICY_KIND,
            {
                "schema_version": self.schema_version,
                "policy_id": self.policy_id,
                "expected_profile": self.expected_profile,
                "expected_issuer": self.expected_issuer,
                "expected_audience": self.expected_audience,
                "attestation_jwks": self.attestation_jwks,
                "allowed_algs": list(self.allowed_algs),
                "required_key_attributes": dict(self.required_key_attributes),
                "measured_component_name": self.measured_component_name,
                "measurement_algorithm": self.measurement_algorithm,
                "endorsed_measurement_digest": self.endorsed_measurement_digest,
                "max_token_age_seconds": self.max_token_age_seconds,
            },
        )


@dataclass(frozen=True)
class EATAttestationCryptoReceipt:
    schema_version: str
    receipt_kind: str
    outcome: str
    eat_profile: str
    issuer: str
    audience: str
    attestation_key_id: str
    subject_jkt: str
    key_attributes_root: str
    measurement_component: str
    measurement_algorithm: str
    measurement_digest: str
    nonce_sha256: str
    token_sha256: str
    verification_time_epoch: int
    trust_policy_root: str
    authority_granted: bool
    receipt_root: str


def _select_attestation_jwk(policy: EATJWTTrustPolicy, *, kid: str, alg: str) -> Mapping[str, Any]:
    matches = [item for item in policy.attestation_jwks["keys"] if item.get("kid") == kid]
    if len(matches) != 1:
        raise EATAttestationCryptoError("EAT_ATTESTATION_KEY_NOT_UNIQUE")
    jwk = matches[0]
    if jwk.get("alg") not in (None, alg):
        raise EATAttestationCryptoError("EAT_ATTESTATION_KEY_ALG_MISMATCH")
    if jwk.get("use") not in (None, "sig"):
        raise EATAttestationCryptoError("EAT_ATTESTATION_KEY_USE_INVALID")
    return jwk


def _audience_contains(raw: Any, expected: str) -> bool:
    if isinstance(raw, str):
        return raw == expected
    return isinstance(raw, list) and all(isinstance(item, str) for item in raw) and expected in raw


def _extract_measurement(claims: Mapping[str, Any], policy: EATJWTTrustPolicy) -> tuple[str, str, str]:
    measurements = claims.get("measurements")
    if not isinstance(measurements, list):
        raise EATAttestationCryptoError("EAT_MEASURED_COMPONENT_NOT_FOUND")
    candidates: list[tuple[str, str, str]] = []
    for entry in measurements:
        if not isinstance(entry, list) or len(entry) != 2 or entry[0] != RFC10013_MEASURED_COMPONENT_JSON or not isinstance(entry[1], str):
            continue
        try:
            component = json.loads(entry[1])
        except Exception:
            continue
        if not isinstance(component, dict):
            continue
        component_id = component.get("id")
        if not isinstance(component_id, list) or not component_id or component_id[0] != policy.measured_component_name:
            continue
        measurement = component.get("digested-measurement")
        if not isinstance(measurement, list) or len(measurement) != 2:
            raise EATAttestationCryptoError("EAT_MEASUREMENT_FORMAT_INVALID")
        alg = measurement[0]
        if alg != policy.measurement_algorithm:
            raise EATAttestationCryptoError("EAT_MEASUREMENT_ALGORITHM_MISMATCH")
        digest_bytes = _b64u_decode(measurement[1], "EAT_MEASUREMENT_DIGEST_INVALID")
        if alg == "sha-256" and len(digest_bytes) != 32:
            raise EATAttestationCryptoError("EAT_MEASUREMENT_DIGEST_INVALID")
        candidates.append((component_id[0], alg, digest_bytes.hex()))
    if not candidates:
        raise EATAttestationCryptoError("EAT_MEASURED_COMPONENT_NOT_FOUND")
    if len(candidates) != 1:
        raise EATAttestationCryptoError("EAT_MEASURED_COMPONENT_NOT_UNIQUE")
    return candidates[0]


def verify_eat_jwt_attestation(
    *,
    raw_token: str,
    trust_policy: EATJWTTrustPolicy,
    expected_subject_jkt: str,
    expected_nonce: str,
    verification_time_epoch: int,
) -> EATAttestationCryptoReceipt:
    """Verify one AEGIS EAT-JWT attestation and emit evidence-only receipt."""
    if not isinstance(trust_policy, EATJWTTrustPolicy):
        raise EATAttestationCryptoError("EAT_TRUST_POLICY_INVALID")
    subject_jkt_expected = _string(expected_subject_jkt, "EAT_EXPECTED_SUBJECT_JKT_MISSING")
    nonce_expected = _string(expected_nonce, "EAT_EXPECTED_NONCE_MISSING")
    now = _integer(verification_time_epoch, "EAT_VERIFICATION_TIME_INVALID")
    if now < 0:
        raise EATAttestationCryptoError("EAT_VERIFICATION_TIME_INVALID")

    header, claims, signing_input, signature = _parse_jwt(raw_token)
    alg = _string(header.get("alg"), "EAT_ALG_MISSING")
    if alg not in trust_policy.allowed_algs:
        raise EATAttestationCryptoError("EAT_ALG_NOT_ALLOWED")
    kid = _string(header.get("kid"), "EAT_KID_MISSING")
    attestation_jwk = _select_attestation_jwk(trust_policy, kid=kid, alg=alg)
    _verify_signature(alg=alg, jwk=attestation_jwk, signing_input=signing_input, signature=signature)

    if claims.get("eat_profile") != trust_policy.expected_profile:
        raise EATAttestationCryptoError("EAT_PROFILE_MISMATCH")
    if claims.get("iss") != trust_policy.expected_issuer:
        raise EATAttestationCryptoError("EAT_ISSUER_MISMATCH")
    if not _audience_contains(claims.get("aud"), trust_policy.expected_audience):
        raise EATAttestationCryptoError("EAT_AUDIENCE_MISMATCH")

    issued_at = _integer(claims.get("iat"), "EAT_IAT_INVALID")
    expires_at = _integer(claims.get("exp"), "EAT_EXP_INVALID")
    if issued_at > now:
        raise EATAttestationCryptoError("EAT_IAT_IN_FUTURE")
    if expires_at <= now:
        raise EATAttestationCryptoError("EAT_EXPIRED")
    if expires_at < issued_at:
        raise EATAttestationCryptoError("EAT_TIME_INTERVAL_INVALID")
    if now - issued_at > trust_policy.max_token_age_seconds:
        raise EATAttestationCryptoError("EAT_STALE")

    nonce = claims.get("eat_nonce")
    # This AEGIS profile intentionally narrows RFC 9711 to exactly one JSON
    # nonce string for transaction-time verification.
    if not isinstance(nonce, str) or not nonce:
        raise EATAttestationCryptoError("EAT_NONCE_INVALID")
    if nonce != nonce_expected:
        raise EATAttestationCryptoError("EAT_NONCE_MISMATCH")

    cnf = claims.get("cnf")
    if not isinstance(cnf, Mapping) or not isinstance(cnf.get("jwk"), Mapping):
        raise EATAttestationCryptoError("EAT_CNF_JWK_REQUIRED")
    try:
        subject_jkt = jwk_thumbprint(cnf["jwk"])
    except Exception as exc:
        raise EATAttestationCryptoError("EAT_CNF_JWK_INVALID") from exc
    if subject_jkt != subject_jkt_expected:
        raise EATAttestationCryptoError("EAT_SUBJECT_KEY_MISMATCH")

    key_attributes = claims.get("key-attributes")
    if not isinstance(key_attributes, Mapping) or not key_attributes:
        raise EATAttestationCryptoError("EAT_KEY_ATTRIBUTES_REQUIRED")
    for key, expected in trust_policy.required_key_attributes.items():
        if key_attributes.get(key) != expected:
            raise EATAttestationCryptoError("EAT_KEY_ATTRIBUTE_MISMATCH")

    component, measurement_alg, measurement_digest = _extract_measurement(claims, trust_policy)
    if measurement_digest != trust_policy.endorsed_measurement_digest:
        raise EATAttestationCryptoError("EAT_MEASUREMENT_MISMATCH")

    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "outcome": EAT_ATTESTATION_CRYPTO_VERIFIED,
        "eat_profile": trust_policy.expected_profile,
        "issuer": trust_policy.expected_issuer,
        "audience": trust_policy.expected_audience,
        "attestation_key_id": kid,
        "subject_jkt": subject_jkt,
        "key_attributes_root": canonical_hash("AEGIS_EAT_KEY_ATTRIBUTES_V1", dict(key_attributes)),
        "measurement_component": component,
        "measurement_algorithm": measurement_alg,
        "measurement_digest": measurement_digest,
        "nonce_sha256": hashlib.sha256(nonce.encode("utf-8")).hexdigest(),
        "token_sha256": hashlib.sha256(raw_token.encode("ascii")).hexdigest(),
        "verification_time_epoch": now,
        "trust_policy_root": trust_policy.root,
        "authority_granted": False,
    }
    receipt_root = canonical_hash(RECEIPT_DOMAIN, unsigned)
    return EATAttestationCryptoReceipt(**unsigned, receipt_root=receipt_root)
