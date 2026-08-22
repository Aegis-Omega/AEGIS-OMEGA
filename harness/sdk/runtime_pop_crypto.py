"""Cryptographic RuntimePoP evidence verification.

This module closes a deliberately narrower gap than authority admission:

* SPIFFE X.509-SVID peer certificates are path-validated and bound to the
  expected runtime principal.
* RFC 8705 certificate-bound JWT access tokens are bound to the TLS peer
  certificate via ``cnf.x5t#S256``.
* RFC 9449 DPoP proofs are signature-verified and bound to the exact HTTP
  request, access token, nonce (when required), and a single-use ``jti``.

A successful verification produces evidence for ``RuntimePoPVerification`` from
``principal_binding``. It never grants AEGIS authority and never stores raw
access tokens, DPoP proofs, or certificate bodies in its receipt.

Important mTLS boundary: the ``tls_peer_certificate_der_b64`` input is expected
to come directly from the trusted TLS termination boundary for the request being
authorized. This module validates the certificate and token binding; it does not
replay or independently reconstruct the TLS handshake transcript.
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit, urlunsplit

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.x509.oid import ExtendedKeyUsageOID
from cryptography.x509.verification import (
    Criticality,
    ExtensionPolicy,
    PolicyBuilder,
    Store,
    VerificationError,
)

from harness.sdk.principal_binding import (
    DPOP_CERT_BOUND,
    MTLS_CERT_BOUND,
    MTLS_DPOP_CERT_BOUND,
    VERIFIED,
    RuntimePoPVerification,
    canonical_hash,
)

CRYPTO_SCHEMA_VERSION = "1.0.0"
CRYPTO_RECEIPT_KIND = "AEGIS_RUNTIME_POP_CRYPTO_RECEIPT_V1"
CRYPTO_VERIFIER_IDENTITY = "aegis:runtime-pop-crypto-v1"
SUPPORTED_CRYPTO_MODES = frozenset((MTLS_CERT_BOUND, DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND))
SUPPORTED_JWS_ALGS = frozenset(("RS256", "ES256"))
PRIVATE_JWK_MEMBERS = frozenset(("d", "p", "q", "dp", "dq", "qi", "oth", "k"))
MAX_DPOP_AGE_SECONDS = 300
MAX_DPOP_FUTURE_SKEW_SECONDS = 60
NONE = "NONE"


class CryptoVerificationError(ValueError):
    """Fail-closed verifier error carrying a stable denial code."""


class ReplayStore(Protocol):
    def consume(self, key: str, *, now_epoch: int, expires_at: int) -> bool:
        """Atomically consume a replay key; False means it was already consumed."""


class InMemoryReplayStore:
    """Thread-safe bounded-lifetime replay store for tests and single-process use.

    Production distributed runtimes should provide a durable/atomic ReplayStore
    implementation (for example, a transactional database or Redis SET NX style
    primitive) so replay state is shared across replicas.
    """

    def __init__(self) -> None:
        self._entries: dict[str, int] = {}
        self._lock = threading.Lock()

    def consume(self, key: str, *, now_epoch: int, expires_at: int) -> bool:
        with self._lock:
            expired = [item for item, expiry in self._entries.items() if expiry <= now_epoch]
            for item in expired:
                self._entries.pop(item, None)
            if key in self._entries:
                return False
            self._entries[key] = expires_at
            return True


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str, *, code: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise CryptoVerificationError(code)
    try:
        padded = value + "=" * ((4 - len(value) % 4) % 4)
        return base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except Exception as exc:
        raise CryptoVerificationError(code) from exc


def _require_string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CryptoVerificationError(code)
    return value


def _require_int(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CryptoVerificationError(code)
    return value


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def jwk_thumbprint(jwk: Mapping[str, Any]) -> str:
    """Return RFC 7638 SHA-256 JWK thumbprint for supported public keys."""
    if not isinstance(jwk, Mapping):
        raise CryptoVerificationError("JWK_INVALID")
    if PRIVATE_JWK_MEMBERS.intersection(jwk.keys()):
        raise CryptoVerificationError("JWK_PRIVATE_MATERIAL_FORBIDDEN")
    kty = jwk.get("kty")
    if kty == "RSA":
        members = {
            "e": _require_string(jwk.get("e"), "JWK_RSA_E_MISSING"),
            "kty": "RSA",
            "n": _require_string(jwk.get("n"), "JWK_RSA_N_MISSING"),
        }
    elif kty == "EC":
        crv = _require_string(jwk.get("crv"), "JWK_EC_CRV_MISSING")
        if crv != "P-256":
            raise CryptoVerificationError("JWK_EC_CURVE_UNSUPPORTED")
        members = {
            "crv": crv,
            "kty": "EC",
            "x": _require_string(jwk.get("x"), "JWK_EC_X_MISSING"),
            "y": _require_string(jwk.get("y"), "JWK_EC_Y_MISSING"),
        }
    else:
        raise CryptoVerificationError("JWK_KTY_UNSUPPORTED")
    return b64url_encode(hashlib.sha256(_canonical_json(members)).digest())


def _public_key_from_jwk(jwk: Mapping[str, Any]):
    if PRIVATE_JWK_MEMBERS.intersection(jwk.keys()):
        raise CryptoVerificationError("JWK_PRIVATE_MATERIAL_FORBIDDEN")
    kty = jwk.get("kty")
    try:
        if kty == "RSA":
            n = int.from_bytes(_b64url_decode(_require_string(jwk.get("n"), "JWK_RSA_N_MISSING"), code="JWK_RSA_N_INVALID"), "big")
            e = int.from_bytes(_b64url_decode(_require_string(jwk.get("e"), "JWK_RSA_E_MISSING"), code="JWK_RSA_E_INVALID"), "big")
            if n <= 0 or e <= 1:
                raise ValueError("invalid RSA numbers")
            return rsa.RSAPublicNumbers(e=e, n=n).public_key()
        if kty == "EC":
            if jwk.get("crv") != "P-256":
                raise CryptoVerificationError("JWK_EC_CURVE_UNSUPPORTED")
            x_bytes = _b64url_decode(_require_string(jwk.get("x"), "JWK_EC_X_MISSING"), code="JWK_EC_X_INVALID")
            y_bytes = _b64url_decode(_require_string(jwk.get("y"), "JWK_EC_Y_MISSING"), code="JWK_EC_Y_INVALID")
            if len(x_bytes) != 32 or len(y_bytes) != 32:
                raise CryptoVerificationError("JWK_EC_COORDINATE_SIZE_INVALID")
            return ec.EllipticCurvePublicNumbers(
                int.from_bytes(x_bytes, "big"),
                int.from_bytes(y_bytes, "big"),
                ec.SECP256R1(),
            ).public_key()
    except CryptoVerificationError:
        raise
    except Exception as exc:
        raise CryptoVerificationError("JWK_PUBLIC_KEY_INVALID") from exc
    raise CryptoVerificationError("JWK_KTY_UNSUPPORTED")


def _parse_jwt(token: str, *, code: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    _require_string(token, code)
    parts = token.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise CryptoVerificationError(code)
    try:
        header = json.loads(_b64url_decode(parts[0], code=code))
        payload = json.loads(_b64url_decode(parts[1], code=code))
        signature = _b64url_decode(parts[2], code=code)
    except CryptoVerificationError:
        raise
    except Exception as exc:
        raise CryptoVerificationError(code) from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise CryptoVerificationError(code)
    return header, payload, f"{parts[0]}.{parts[1]}".encode("ascii"), signature


def _verify_signature(*, alg: str, public_key: Any, signing_input: bytes, signature: bytes, code: str) -> None:
    if alg not in SUPPORTED_JWS_ALGS:
        raise CryptoVerificationError(code.replace("SIGNATURE_INVALID", "ALG_UNSUPPORTED"))
    try:
        if alg == "RS256":
            if not isinstance(public_key, rsa.RSAPublicKey):
                raise CryptoVerificationError(code)
            public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
            return
        if alg == "ES256":
            if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256R1):
                raise CryptoVerificationError(code)
            if len(signature) != 64:
                raise CryptoVerificationError(code)
            r = int.from_bytes(signature[:32], "big")
            s = int.from_bytes(signature[32:], "big")
            public_key.verify(encode_dss_signature(r, s), signing_input, ec.ECDSA(hashes.SHA256()))
            return
    except CryptoVerificationError:
        raise
    except InvalidSignature as exc:
        raise CryptoVerificationError(code) from exc
    except Exception as exc:
        raise CryptoVerificationError(code) from exc
    raise CryptoVerificationError(code)


def _select_issuer_jwk(jwks: Mapping[str, Any], *, kid: str, alg: str) -> Mapping[str, Any]:
    if not isinstance(jwks, Mapping) or not isinstance(jwks.get("keys"), list):
        raise CryptoVerificationError("ACCESS_TOKEN_JWKS_INVALID")
    matches = [item for item in jwks["keys"] if isinstance(item, Mapping) and item.get("kid") == kid]
    if len(matches) != 1:
        raise CryptoVerificationError("ACCESS_TOKEN_JWK_NOT_UNIQUE")
    jwk = matches[0]
    declared_alg = jwk.get("alg")
    if declared_alg is not None and declared_alg != alg:
        raise CryptoVerificationError("ACCESS_TOKEN_JWK_ALG_MISMATCH")
    if jwk.get("use") not in (None, "sig"):
        raise CryptoVerificationError("ACCESS_TOKEN_JWK_USE_INVALID")
    return jwk


def _verify_access_token(
    token: str,
    *,
    jwks: Mapping[str, Any],
    expected_issuer: str,
    expected_audience: str,
    now_epoch: int,
) -> dict[str, Any]:
    header, claims, signing_input, signature = _parse_jwt(token, code="ACCESS_TOKEN_JWT_INVALID")
    alg = _require_string(header.get("alg"), "ACCESS_TOKEN_ALG_MISSING")
    if alg not in SUPPORTED_JWS_ALGS:
        raise CryptoVerificationError("ACCESS_TOKEN_ALG_UNSUPPORTED")
    kid = _require_string(header.get("kid"), "ACCESS_TOKEN_KID_MISSING")
    jwk = _select_issuer_jwk(jwks, kid=kid, alg=alg)
    public_key = _public_key_from_jwk(jwk)
    _verify_signature(
        alg=alg,
        public_key=public_key,
        signing_input=signing_input,
        signature=signature,
        code="ACCESS_TOKEN_SIGNATURE_INVALID",
    )

    if claims.get("iss") != expected_issuer:
        raise CryptoVerificationError("ACCESS_TOKEN_ISSUER_MISMATCH")
    audience = claims.get("aud")
    if isinstance(audience, str):
        audiences = (audience,)
    elif isinstance(audience, list) and all(isinstance(item, str) for item in audience):
        audiences = tuple(audience)
    else:
        raise CryptoVerificationError("ACCESS_TOKEN_AUDIENCE_INVALID")
    if expected_audience not in audiences:
        raise CryptoVerificationError("ACCESS_TOKEN_AUDIENCE_MISMATCH")

    exp = _require_int(claims.get("exp"), "ACCESS_TOKEN_EXP_MISSING")
    if exp <= now_epoch:
        raise CryptoVerificationError("ACCESS_TOKEN_EXPIRED")
    if "nbf" in claims:
        nbf = _require_int(claims["nbf"], "ACCESS_TOKEN_NBF_INVALID")
        if nbf > now_epoch:
            raise CryptoVerificationError("ACCESS_TOKEN_NOT_YET_VALID")
    if "iat" in claims:
        iat = _require_int(claims["iat"], "ACCESS_TOKEN_IAT_INVALID")
        if iat > now_epoch + MAX_DPOP_FUTURE_SKEW_SECONDS:
            raise CryptoVerificationError("ACCESS_TOKEN_IAT_IN_FUTURE")
    return claims


def _load_peer_certificate(value: Any) -> x509.Certificate:
    raw = _require_string(value, "TLS_PEER_CERTIFICATE_MISSING")
    try:
        der = base64.b64decode(raw.encode("ascii"), validate=True)
        return x509.load_der_x509_certificate(der)
    except Exception as exc:
        raise CryptoVerificationError("TLS_PEER_CERTIFICATE_INVALID") from exc


def _load_pem_certificates(values: Any, *, required: bool, code: str) -> list[x509.Certificate]:
    if not isinstance(values, list):
        raise CryptoVerificationError(code)
    if required and not values:
        raise CryptoVerificationError(code)
    certificates: list[x509.Certificate] = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise CryptoVerificationError(code)
        try:
            certificates.append(x509.load_pem_x509_certificate(item.encode("ascii")))
        except Exception as exc:
            raise CryptoVerificationError(code) from exc
    return certificates


def _validate_spiffe_leaf(leaf: x509.Certificate, *, expected_runtime_principal: str) -> str:
    try:
        san_extension = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound as exc:
        raise CryptoVerificationError("SPIFFE_SAN_MISSING") from exc
    uri_sans = san_extension.value.get_values_for_type(x509.UniformResourceIdentifier)
    if len(uri_sans) != 1:
        raise CryptoVerificationError("SPIFFE_URI_SAN_COUNT_INVALID")
    spiffe_id = uri_sans[0]
    parsed = urlsplit(spiffe_id)
    if parsed.scheme != "spiffe" or not parsed.netloc or parsed.path in ("", "/") or parsed.query or parsed.fragment:
        raise CryptoVerificationError("SPIFFE_ID_INVALID")
    if spiffe_id != expected_runtime_principal:
        raise CryptoVerificationError("SPIFFE_ID_MISMATCH")

    try:
        basic_extension = leaf.extensions.get_extension_for_class(x509.BasicConstraints)
    except x509.ExtensionNotFound as exc:
        raise CryptoVerificationError("SPIFFE_BASIC_CONSTRAINTS_MISSING") from exc
    if basic_extension.value.ca:
        raise CryptoVerificationError("SPIFFE_LEAF_CA_FORBIDDEN")

    try:
        key_usage_extension = leaf.extensions.get_extension_for_class(x509.KeyUsage)
    except x509.ExtensionNotFound as exc:
        raise CryptoVerificationError("SPIFFE_KEY_USAGE_MISSING") from exc
    usage = key_usage_extension.value
    if not key_usage_extension.critical:
        raise CryptoVerificationError("SPIFFE_KEY_USAGE_NOT_CRITICAL")
    if not usage.digital_signature:
        raise CryptoVerificationError("SPIFFE_DIGITAL_SIGNATURE_REQUIRED")
    if usage.key_cert_sign or usage.crl_sign:
        raise CryptoVerificationError("SPIFFE_LEAF_SIGNING_USAGE_FORBIDDEN")

    # SPIFFE says leaf EKU SHOULD be present; when present the standard carries
    # both client/server auth. For this inbound RuntimePoP profile we require at
    # least clientAuth and deliberately do not make optional serverAuth an
    # authentication dependency.
    try:
        eku = leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if ExtendedKeyUsageOID.CLIENT_AUTH not in eku:
            raise CryptoVerificationError("SPIFFE_CLIENT_AUTH_EKU_REQUIRED")
    except x509.ExtensionNotFound:
        pass

    return spiffe_id


def _ca_basic_constraints(_policy: Any, _cert: x509.Certificate, extension: x509.BasicConstraints) -> None:
    if not extension.ca:
        raise ValueError("CA basicConstraints.cA must be true")


def _ca_key_usage(_policy: Any, _cert: x509.Certificate, extension: x509.KeyUsage) -> None:
    if not extension.key_cert_sign:
        raise ValueError("CA keyCertSign must be true")


def _ee_basic_constraints(_policy: Any, _cert: x509.Certificate, extension: x509.BasicConstraints) -> None:
    if extension.ca:
        raise ValueError("leaf basicConstraints.cA must be false")


def _ee_key_usage(_policy: Any, _cert: x509.Certificate, extension: x509.KeyUsage) -> None:
    if not extension.digital_signature or extension.key_cert_sign or extension.crl_sign:
        raise ValueError("invalid SPIFFE leaf key usage")


def _verify_spiffe_path(
    leaf: x509.Certificate,
    *,
    intermediates: list[x509.Certificate],
    roots: list[x509.Certificate],
    now_epoch: int,
) -> None:
    try:
        ca_policy = (
            ExtensionPolicy.permit_all()
            .require_present(x509.BasicConstraints, Criticality.AGNOSTIC, _ca_basic_constraints)
            .require_present(x509.KeyUsage, Criticality.CRITICAL, _ca_key_usage)
        )
        ee_policy = (
            ExtensionPolicy.permit_all()
            .require_present(x509.BasicConstraints, Criticality.AGNOSTIC, _ee_basic_constraints)
            .require_present(x509.KeyUsage, Criticality.CRITICAL, _ee_key_usage)
            .require_present(x509.SubjectAlternativeName, Criticality.AGNOSTIC, None)
        )
        verifier = (
            PolicyBuilder()
            .store(Store(roots))
            .time(datetime.fromtimestamp(now_epoch, tz=timezone.utc))
            .extension_policies(ee_policy=ee_policy, ca_policy=ca_policy)
            .build_client_verifier()
        )
        verifier.verify(leaf, intermediates)
    except (VerificationError, ValueError, TypeError) as exc:
        raise CryptoVerificationError("X509_PATH_INVALID") from exc


def _certificate_thumbprint_s256(cert: x509.Certificate) -> str:
    return b64url_encode(hashlib.sha256(cert.public_bytes(x509.Encoding.DER) if hasattr(x509, "Encoding") else cert.public_bytes(__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.DER)).digest())


def _certificate_thumbprint_s256_stable(cert: x509.Certificate) -> str:
    # Keep serialization import out of public receipt types while supporting
    # cryptography versions where Encoding lives in serialization only.
    from cryptography.hazmat.primitives import serialization

    return b64url_encode(hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).digest())


def _normalized_htu(uri: str) -> str:
    raw = _require_string(uri, "REQUEST_URI_MISSING")
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise CryptoVerificationError("REQUEST_URI_INVALID")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))


def _verify_dpop(
    proof: str,
    *,
    access_token: str,
    token_claims: Mapping[str, Any],
    request_method: str,
    request_uri: str,
    now_epoch: int,
    expected_nonce: str | None,
    replay_store: ReplayStore | None,
) -> tuple[str, str]:
    header, claims, signing_input, signature = _parse_jwt(proof, code="DPOP_JWT_INVALID")
    if header.get("typ") != "dpop+jwt":
        raise CryptoVerificationError("DPOP_TYP_INVALID")
    alg = _require_string(header.get("alg"), "DPOP_ALG_MISSING")
    if alg not in SUPPORTED_JWS_ALGS:
        raise CryptoVerificationError("DPOP_ALG_UNSUPPORTED")
    jwk = header.get("jwk")
    if not isinstance(jwk, Mapping):
        raise CryptoVerificationError("DPOP_JWK_MISSING")
    public_key = _public_key_from_jwk(jwk)
    _verify_signature(
        alg=alg,
        public_key=public_key,
        signing_input=signing_input,
        signature=signature,
        code="DPOP_SIGNATURE_INVALID",
    )
    jkt = jwk_thumbprint(jwk)

    jti = _require_string(claims.get("jti"), "DPOP_JTI_MISSING")
    if len(jti) < 12:
        raise CryptoVerificationError("DPOP_JTI_TOO_SHORT")
    method = _require_string(request_method, "REQUEST_METHOD_MISSING").upper()
    if claims.get("htm") != method:
        raise CryptoVerificationError("DPOP_HTM_MISMATCH")
    expected_htu = _normalized_htu(request_uri)
    if claims.get("htu") != expected_htu:
        raise CryptoVerificationError("DPOP_HTU_MISMATCH")
    iat = _require_int(claims.get("iat"), "DPOP_IAT_MISSING")
    if now_epoch - iat > MAX_DPOP_AGE_SECONDS:
        raise CryptoVerificationError("DPOP_IAT_STALE")
    if iat - now_epoch > MAX_DPOP_FUTURE_SKEW_SECONDS:
        raise CryptoVerificationError("DPOP_IAT_IN_FUTURE")

    expected_ath = b64url_encode(hashlib.sha256(access_token.encode("ascii")).digest())
    if claims.get("ath") != expected_ath:
        raise CryptoVerificationError("DPOP_ATH_MISMATCH")
    if expected_nonce is not None and claims.get("nonce") != expected_nonce:
        raise CryptoVerificationError("DPOP_NONCE_MISMATCH")

    cnf = token_claims.get("cnf")
    if not isinstance(cnf, Mapping) or cnf.get("jkt") != jkt:
        raise CryptoVerificationError("DPOP_TOKEN_KEY_BINDING_MISMATCH")

    if replay_store is None:
        raise CryptoVerificationError("DPOP_REPLAY_STORE_REQUIRED")
    replay_key = canonical_hash("AEGIS_DPOP_REPLAY_KEY_V1", {"jkt": jkt, "jti": jti})
    if not replay_store.consume(
        replay_key,
        now_epoch=now_epoch,
        expires_at=iat + MAX_DPOP_AGE_SECONDS + MAX_DPOP_FUTURE_SKEW_SECONDS,
    ):
        raise CryptoVerificationError("DPOP_REPLAY_DETECTED")
    return jkt, expected_htu


@dataclass(frozen=True)
class RuntimePoPCryptoReceipt:
    schema_version: str
    receipt_kind: str
    cryptographic_verified: bool
    verifier_identity: str
    runtime_principal: str
    binding_mode: str
    verification_time_epoch: int
    certificate_thumbprint_s256: str
    dpop_jkt: str
    access_token_sha256: str
    dpop_proof_sha256: str
    request_method: str
    request_uri: str
    proof_root: str

    def to_runtime_pop_verification(self, *, generation: int) -> RuntimePoPVerification:
        if not self.cryptographic_verified:
            raise CryptoVerificationError("CRYPTO_RECEIPT_NOT_VERIFIED")
        if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
            raise CryptoVerificationError("CRYPTO_RECEIPT_GENERATION_INVALID")
        return RuntimePoPVerification(
            runtime_principal=self.runtime_principal,
            binding_mode=self.binding_mode,
            verification_state=VERIFIED,
            verifier_identity=self.verifier_identity,
            proof_root=self.proof_root,
            evidence_ref=f"crypto:sha256:{self.proof_root}",
            generation=generation,
        )


def verify_runtime_pop_evidence(
    evidence: Mapping[str, Any],
    *,
    replay_store: ReplayStore | None = None,
) -> RuntimePoPCryptoReceipt:
    """Cryptographically verify RuntimePoP evidence and emit a non-authority receipt."""
    if not isinstance(evidence, Mapping):
        raise CryptoVerificationError("CRYPTO_EVIDENCE_NOT_OBJECT")
    if evidence.get("schema_version") != CRYPTO_SCHEMA_VERSION:
        raise CryptoVerificationError("CRYPTO_SCHEMA_UNSUPPORTED")
    mode = _require_string(evidence.get("binding_mode"), "CRYPTO_BINDING_MODE_MISSING")
    if mode not in SUPPORTED_CRYPTO_MODES:
        raise CryptoVerificationError("CRYPTO_POP_MODE_REQUIRED")
    runtime_principal = _require_string(evidence.get("runtime_principal"), "CRYPTO_RUNTIME_PRINCIPAL_MISSING")
    parsed_runtime = urlsplit(runtime_principal)
    if parsed_runtime.scheme != "spiffe" or not parsed_runtime.netloc or parsed_runtime.path in ("", "/"):
        raise CryptoVerificationError("CRYPTO_RUNTIME_PRINCIPAL_INVALID")
    now_epoch = _require_int(evidence.get("now_epoch"), "CRYPTO_NOW_INVALID")
    request_method = _require_string(evidence.get("request_method"), "REQUEST_METHOD_MISSING").upper()
    request_uri = _normalized_htu(_require_string(evidence.get("request_uri"), "REQUEST_URI_MISSING"))
    expected_issuer = _require_string(evidence.get("expected_issuer"), "ACCESS_TOKEN_EXPECTED_ISSUER_MISSING")
    expected_audience = _require_string(evidence.get("expected_audience"), "ACCESS_TOKEN_EXPECTED_AUDIENCE_MISSING")
    access_token = _require_string(evidence.get("access_token"), "ACCESS_TOKEN_MISSING")
    issuer_jwks = evidence.get("issuer_jwks")
    if not isinstance(issuer_jwks, Mapping):
        raise CryptoVerificationError("ACCESS_TOKEN_JWKS_INVALID")

    token_claims = _verify_access_token(
        access_token,
        jwks=issuer_jwks,
        expected_issuer=expected_issuer,
        expected_audience=expected_audience,
        now_epoch=now_epoch,
    )
    cnf = token_claims.get("cnf")
    if not isinstance(cnf, Mapping):
        raise CryptoVerificationError("ACCESS_TOKEN_CNF_MISSING")

    certificate_thumbprint = NONE
    if mode in (MTLS_CERT_BOUND, MTLS_DPOP_CERT_BOUND):
        leaf = _load_peer_certificate(evidence.get("tls_peer_certificate_der_b64"))
        # Leaf-specific SPIFFE errors are intentionally emitted before generic
        # path errors so a malformed SVID is never misclassified as a trust-only
        # failure.
        _validate_spiffe_leaf(leaf, expected_runtime_principal=runtime_principal)
        roots = _load_pem_certificates(
            evidence.get("x509_trust_roots_pem"),
            required=True,
            code="X509_TRUST_ROOTS_INVALID",
        )
        intermediates = _load_pem_certificates(
            evidence.get("x509_intermediates_pem", []),
            required=False,
            code="X509_INTERMEDIATES_INVALID",
        )
        _verify_spiffe_path(leaf, intermediates=intermediates, roots=roots, now_epoch=now_epoch)
        certificate_thumbprint = _certificate_thumbprint_s256_stable(leaf)
        if cnf.get("x5t#S256") != certificate_thumbprint:
            raise CryptoVerificationError("MTLS_TOKEN_CERT_BINDING_MISMATCH")

    dpop_jkt = NONE
    dpop_proof_hash = "0" * 64
    if mode in (DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND):
        proof = _require_string(evidence.get("dpop_proof"), "DPOP_PROOF_MISSING")
        expected_nonce = evidence.get("expected_nonce")
        if expected_nonce is not None and (not isinstance(expected_nonce, str) or not expected_nonce):
            raise CryptoVerificationError("DPOP_EXPECTED_NONCE_INVALID")
        dpop_jkt, verified_htu = _verify_dpop(
            proof,
            access_token=access_token,
            token_claims=token_claims,
            request_method=request_method,
            request_uri=request_uri,
            now_epoch=now_epoch,
            expected_nonce=expected_nonce,
            replay_store=replay_store,
        )
        if verified_htu != request_uri:
            raise CryptoVerificationError("DPOP_HTU_MISMATCH")
        dpop_proof_hash = hashlib.sha256(proof.encode("ascii")).hexdigest()

    unsigned = {
        "schema_version": CRYPTO_SCHEMA_VERSION,
        "receipt_kind": CRYPTO_RECEIPT_KIND,
        "cryptographic_verified": True,
        "verifier_identity": CRYPTO_VERIFIER_IDENTITY,
        "runtime_principal": runtime_principal,
        "binding_mode": mode,
        "verification_time_epoch": now_epoch,
        "certificate_thumbprint_s256": certificate_thumbprint,
        "dpop_jkt": dpop_jkt,
        "access_token_sha256": hashlib.sha256(access_token.encode("ascii")).hexdigest(),
        "dpop_proof_sha256": dpop_proof_hash,
        "request_method": request_method,
        "request_uri": request_uri,
    }
    proof_root = canonical_hash("AEGIS_RUNTIME_POP_CRYPTO_RECEIPT_V1", unsigned)
    return RuntimePoPCryptoReceipt(**unsigned, proof_root=proof_root)
