"""Cryptographic SCITT authorization-registration verifier for AEGIS.

This module implements a deliberately narrow high-assurance profile:

* RFC 9943 Signed Statement and Receipt envelopes are COSE_Sign1;
* the authorization Signed Statement is locally re-verified against an
  externally configured authorization-issuer trust key;
* its payload is deterministic CBOR and binds the expected scope, holder key,
  endorsed measurement, authorization-time evidence reference and expiry;
* the SCITT Receipt uses the RFC9162_SHA256 VDS inclusion-proof profile from
  RFC 9942;
* the exact Signed Statement bytes are used as the VDS entry;
* the reconstructed Merkle root becomes the detached COSE_Sign1 payload and
  the Transparency Service signature is verified against external trust.

The resulting receipt is evidence of authorization registration only. It does
not grant AEGIS authority, prove transaction-time verification, prove an effect,
or establish global non-equivocation/supersession status.
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping

import cbor2
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from harness.sdk.principal_binding import canonical_hash

SCHEMA_VERSION = "1.0.0"
SCITT_AUTHORIZATION_REGISTRATION_VERIFIED = "SCITT_AUTHORIZATION_REGISTRATION_VERIFIED"
RECEIPT_KIND = "AEGIS_SCITT_AUTHORIZATION_REGISTRATION_RECEIPT_V1"
TRUST_POLICY_KIND = "AEGIS_SCITT_AUTHORIZATION_TRUST_POLICY_V1"
RECEIPT_DOMAIN = "AEGIS_SCITT_AUTHORIZATION_REGISTRATION_RECEIPT_V1"
RFC9162_SHA256_VDS = 1
COSE_ALG_ES256 = -7
COSE_TAG_SIGN1 = 18
COSE_HDR_ALG = 1
COSE_HDR_CONTENT_TYPE = 3
COSE_HDR_KID = 4
COSE_HDR_CWT_CLAIMS = 15
COSE_HDR_VDS = 395
COSE_HDR_VDP = 396
COSE_VDP_INCLUSION = -1
PRIVATE_JWK_MEMBERS = frozenset(("d", "p", "q", "dp", "dq", "qi", "oth", "k"))
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SCITTAuthorizationError(ValueError):
    """Fail-closed verifier error carrying a stable denial code."""


def _string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SCITTAuthorizationError(code)
    return value


def _integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SCITTAuthorizationError(code)
    return value


def _hex64(value: Any, code: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SCITTAuthorizationError(code)
    return value


def _bytes(value: Any, code: str) -> bytes:
    if not isinstance(value, bytes) or not value:
        raise SCITTAuthorizationError(code)
    return value


def _b64u_decode(value: str, code: str) -> bytes:
    try:
        padded = value + "=" * ((4 - len(value) % 4) % 4)
        return base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except Exception as exc:
        raise SCITTAuthorizationError(code) from exc


def _validated_jwks(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("keys"), list) or not value["keys"]:
        raise SCITTAuthorizationError("SCITT_TRUST_JWKS_INVALID")
    keys: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value["keys"]:
        if not isinstance(item, Mapping) or PRIVATE_JWK_MEMBERS.intersection(item.keys()):
            raise SCITTAuthorizationError("SCITT_TRUST_JWKS_INVALID")
        if item.get("kty") != "EC" or item.get("crv") != "P-256":
            raise SCITTAuthorizationError("SCITT_TRUST_JWKS_INVALID")
        kid = _string(item.get("kid"), "SCITT_TRUST_JWKS_INVALID")
        if kid in seen:
            raise SCITTAuthorizationError("SCITT_TRUST_JWKS_INVALID")
        seen.add(kid)
        if item.get("alg") not in (None, "ES256"):
            raise SCITTAuthorizationError("SCITT_TRUST_JWKS_INVALID")
        if item.get("use") not in (None, "sig"):
            raise SCITTAuthorizationError("SCITT_TRUST_JWKS_INVALID")
        x = _b64u_decode(_string(item.get("x"), "SCITT_TRUST_JWKS_INVALID"), "SCITT_TRUST_JWKS_INVALID")
        y = _b64u_decode(_string(item.get("y"), "SCITT_TRUST_JWKS_INVALID"), "SCITT_TRUST_JWKS_INVALID")
        if len(x) != 32 or len(y) != 32:
            raise SCITTAuthorizationError("SCITT_TRUST_JWKS_INVALID")
        keys.append(dict(item))
    return {"keys": keys}


def _public_key_from_jwk(jwk: Mapping[str, Any]):
    try:
        x = _b64u_decode(_string(jwk.get("x"), "SCITT_TRUST_JWKS_INVALID"), "SCITT_TRUST_JWKS_INVALID")
        y = _b64u_decode(_string(jwk.get("y"), "SCITT_TRUST_JWKS_INVALID"), "SCITT_TRUST_JWKS_INVALID")
        return ec.EllipticCurvePublicNumbers(
            int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
        ).public_key()
    except SCITTAuthorizationError:
        raise
    except Exception as exc:
        raise SCITTAuthorizationError("SCITT_TRUST_JWKS_INVALID") from exc


def _kid_text(value: Any, code: str) -> str:
    if isinstance(value, bytes):
        try:
            decoded = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SCITTAuthorizationError(code) from exc
        return _string(decoded, code)
    return _string(value, code)


def _select_jwk(jwks: Mapping[str, Any], kid: str, code: str) -> Mapping[str, Any]:
    matches = [item for item in jwks["keys"] if item.get("kid") == kid]
    if len(matches) != 1:
        raise SCITTAuthorizationError(code)
    return matches[0]


def _verify_es256(*, jwk: Mapping[str, Any], signing_input: bytes, signature: bytes, code: str) -> None:
    if len(signature) != 64:
        raise SCITTAuthorizationError(code)
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    try:
        _public_key_from_jwk(jwk).verify(
            encode_dss_signature(r, s), signing_input, ec.ECDSA(hashes.SHA256())
        )
    except SCITTAuthorizationError:
        raise
    except InvalidSignature as exc:
        raise SCITTAuthorizationError(code) from exc
    except Exception as exc:
        raise SCITTAuthorizationError(code) from exc


def _decode_sign1(raw: bytes, code: str) -> tuple[bytes, dict[Any, Any], bytes | None, bytes]:
    _bytes(raw, code)
    try:
        value = cbor2.loads(raw)
    except Exception as exc:
        raise SCITTAuthorizationError(code) from exc
    if not isinstance(value, cbor2.CBORTag) or value.tag != COSE_TAG_SIGN1:
        raise SCITTAuthorizationError(code)
    parts = value.value
    if not isinstance(parts, list) or len(parts) != 4:
        raise SCITTAuthorizationError(code)
    protected_bstr, unprotected, payload, signature = parts
    if not isinstance(protected_bstr, bytes) or not isinstance(unprotected, dict):
        raise SCITTAuthorizationError(code)
    if payload is not None and not isinstance(payload, bytes):
        raise SCITTAuthorizationError(code)
    if not isinstance(signature, bytes):
        raise SCITTAuthorizationError(code)
    return protected_bstr, unprotected, payload, signature


def _decode_protected(raw: bytes, code: str) -> dict[Any, Any]:
    try:
        value = cbor2.loads(raw)
    except Exception as exc:
        raise SCITTAuthorizationError(code) from exc
    if not isinstance(value, dict):
        raise SCITTAuthorizationError(code)
    if cbor2.dumps(value, canonical=True) != raw:
        raise SCITTAuthorizationError(code)
    return value


def _cwt_identity(protected: Mapping[Any, Any], *, issuer: str, subject: str, prefix: str) -> None:
    claims = protected.get(COSE_HDR_CWT_CLAIMS)
    if not isinstance(claims, Mapping):
        raise SCITTAuthorizationError(f"{prefix}_CWT_CLAIMS_MISSING")
    if claims.get(1) != issuer:
        raise SCITTAuthorizationError(f"{prefix}_ISSUER_MISMATCH")
    if claims.get(2) != subject:
        raise SCITTAuthorizationError(f"{prefix}_SUBJECT_MISMATCH")


@dataclass(frozen=True)
class SCITTAuthorizationTrustPolicy:
    schema_version: str
    policy_id: str
    authorization_issuer: str
    authorization_subject: str
    authorization_issuer_jwks: Mapping[str, Any]
    expected_content_type: str
    transparency_service_issuer: str
    transparency_service_subject: str
    transparency_service_jwks: Mapping[str, Any]
    allowed_cose_algs: tuple[int, ...]
    required_vds: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SCITTAuthorizationTrustPolicy":
        if not isinstance(value, Mapping):
            raise SCITTAuthorizationError("SCITT_TRUST_POLICY_NOT_OBJECT")
        if value.get("schema_version") != SCHEMA_VERSION:
            raise SCITTAuthorizationError("SCITT_TRUST_POLICY_SCHEMA_UNSUPPORTED")
        raw_algs = value.get("allowed_cose_algs")
        if not isinstance(raw_algs, list) or not raw_algs or any(
            isinstance(item, bool) or not isinstance(item, int) for item in raw_algs
        ):
            raise SCITTAuthorizationError("SCITT_ALLOWED_ALGS_INVALID")
        algs = tuple(raw_algs)
        if len(set(algs)) != len(algs) or any(item != COSE_ALG_ES256 for item in algs):
            raise SCITTAuthorizationError("SCITT_ALLOWED_ALGS_INVALID")
        required_vds = _integer(value.get("required_vds"), "SCITT_VDS_INVALID")
        if required_vds != RFC9162_SHA256_VDS:
            raise SCITTAuthorizationError("SCITT_VDS_UNSUPPORTED")
        return cls(
            schema_version=SCHEMA_VERSION,
            policy_id=_string(value.get("policy_id"), "SCITT_TRUST_POLICY_ID_MISSING"),
            authorization_issuer=_string(value.get("authorization_issuer"), "SCITT_AUTHORIZATION_ISSUER_MISSING"),
            authorization_subject=_string(value.get("authorization_subject"), "SCITT_AUTHORIZATION_SUBJECT_MISSING"),
            authorization_issuer_jwks=_validated_jwks(value.get("authorization_issuer_jwks")),
            expected_content_type=_string(value.get("expected_content_type"), "SCITT_CONTENT_TYPE_MISSING"),
            transparency_service_issuer=_string(value.get("transparency_service_issuer"), "SCITT_TS_ISSUER_MISSING"),
            transparency_service_subject=_string(value.get("transparency_service_subject"), "SCITT_TS_SUBJECT_MISSING"),
            transparency_service_jwks=_validated_jwks(value.get("transparency_service_jwks")),
            allowed_cose_algs=algs,
            required_vds=required_vds,
        )

    @property
    def root(self) -> str:
        return canonical_hash(
            TRUST_POLICY_KIND,
            {
                "schema_version": self.schema_version,
                "policy_id": self.policy_id,
                "authorization_issuer": self.authorization_issuer,
                "authorization_subject": self.authorization_subject,
                "authorization_issuer_jwks": self.authorization_issuer_jwks,
                "expected_content_type": self.expected_content_type,
                "transparency_service_issuer": self.transparency_service_issuer,
                "transparency_service_subject": self.transparency_service_subject,
                "transparency_service_jwks": self.transparency_service_jwks,
                "allowed_cose_algs": list(self.allowed_cose_algs),
                "required_vds": self.required_vds,
            },
        )


@dataclass(frozen=True)
class SCITTAuthorizationRegistrationReceipt:
    schema_version: str
    receipt_kind: str
    outcome: str
    registration_verified: bool
    authorization_issuer: str
    authorization_subject: str
    transparency_service_issuer: str
    transparency_service_subject: str
    scope_root: str
    holder_jkt: str
    measurement_digest: str
    authorization_time_evidence_root: str
    expires_at_epoch: int
    tree_size: int
    leaf_index: int
    merkle_root_sha256: str
    signed_statement_sha256: str
    statement_payload_sha256: str
    cose_receipt_sha256: str
    trust_policy_root: str
    verification_time_epoch: int
    authority_granted: bool
    receipt_root: str


def _scope_from_statement(
    raw_statement: bytes,
    *,
    policy: SCITTAuthorizationTrustPolicy,
    expected_scope_root: str,
    expected_holder_jkt: str,
    expected_measurement_digest: str,
    verification_time_epoch: int,
) -> tuple[dict[str, Any], bytes]:
    protected_bstr, unprotected, payload, signature = _decode_sign1(raw_statement, "SCITT_AUTHORIZATION_STATEMENT_INVALID")
    if unprotected != {}:
        raise SCITTAuthorizationError("SCITT_STATEMENT_UNPROTECTED_NOT_EMPTY")
    if payload is None:
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_PAYLOAD_MISSING")
    protected = _decode_protected(protected_bstr, "SCITT_AUTHORIZATION_PROTECTED_INVALID")
    alg = protected.get(COSE_HDR_ALG)
    if alg not in policy.allowed_cose_algs:
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_ALG_NOT_ALLOWED")
    if protected.get(COSE_HDR_CONTENT_TYPE) != policy.expected_content_type:
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_CONTENT_TYPE_MISMATCH")
    _cwt_identity(
        protected,
        issuer=policy.authorization_issuer,
        subject=policy.authorization_subject,
        prefix="SCITT_AUTHORIZATION",
    )
    kid = _kid_text(protected.get(COSE_HDR_KID), "SCITT_AUTHORIZATION_KID_MISSING")
    issuer_jwk = _select_jwk(policy.authorization_issuer_jwks, kid, "SCITT_AUTHORIZATION_KID_UNTRUSTED")
    sig_structure = cbor2.dumps(["Signature1", protected_bstr, b"", payload], canonical=True)
    _verify_es256(
        jwk=issuer_jwk,
        signing_input=sig_structure,
        signature=signature,
        code="SCITT_AUTHORIZATION_SIGNATURE_INVALID",
    )
    try:
        scope = cbor2.loads(payload)
    except Exception as exc:
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_PAYLOAD_INVALID") from exc
    if not isinstance(scope, dict):
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_PAYLOAD_INVALID")
    if cbor2.dumps(scope, canonical=True) != payload:
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_PAYLOAD_NOT_DETERMINISTIC")
    if scope.get("schema_version") != SCHEMA_VERSION:
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_SCOPE_SCHEMA_UNSUPPORTED")
    if scope.get("scope_root") != expected_scope_root:
        raise SCITTAuthorizationError("SCITT_SCOPE_ROOT_MISMATCH")
    if scope.get("holder_jkt") != expected_holder_jkt:
        raise SCITTAuthorizationError("SCITT_SCOPE_HOLDER_MISMATCH")
    if scope.get("measurement_digest") != expected_measurement_digest:
        raise SCITTAuthorizationError("SCITT_SCOPE_MEASUREMENT_MISMATCH")
    _hex64(scope.get("scope_root"), "SCITT_SCOPE_ROOT_INVALID")
    _string(scope.get("holder_jkt"), "SCITT_SCOPE_HOLDER_INVALID")
    _hex64(scope.get("measurement_digest"), "SCITT_SCOPE_MEASUREMENT_INVALID")
    _hex64(scope.get("authorization_time_evidence_root"), "SCITT_AUTH_TIME_EVIDENCE_ROOT_INVALID")
    expiry = _integer(scope.get("expires_at_epoch"), "SCITT_AUTHORIZATION_EXPIRY_INVALID")
    if expiry <= verification_time_epoch:
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_SCOPE_EXPIRED")
    action_classes = scope.get("action_classes")
    if not isinstance(action_classes, list) or not action_classes or any(
        not isinstance(item, str) or not item for item in action_classes
    ):
        raise SCITTAuthorizationError("SCITT_AUTHORIZATION_ACTION_CLASSES_INVALID")
    return scope, payload


def _leaf_hash(entry: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + entry).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _rfc9162_inclusion_root(entry: bytes, *, tree_size: int, leaf_index: int, path: list[bytes]) -> bytes:
    if tree_size <= 0 or leaf_index < 0 or leaf_index >= tree_size:
        raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID")
    if any(not isinstance(item, bytes) or len(item) != 32 for item in path):
        raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID")
    fn = leaf_index
    sn = tree_size - 1
    root = _leaf_hash(entry)
    for proof_hash in path:
        if sn == 0:
            raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID")
        if (fn & 1) or fn == sn:
            root = _node_hash(proof_hash, root)
            if not (fn & 1):
                while not (fn & 1) and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            root = _node_hash(root, proof_hash)
        fn >>= 1
        sn >>= 1
    if sn != 0:
        raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID")
    return root


def _verify_receipt(
    raw_receipt: bytes,
    *,
    signed_statement: bytes,
    policy: SCITTAuthorizationTrustPolicy,
) -> tuple[int, int, bytes]:
    protected_bstr, unprotected, payload, signature = _decode_sign1(raw_receipt, "SCITT_RECEIPT_INVALID")
    if payload is not None:
        raise SCITTAuthorizationError("SCITT_RECEIPT_PAYLOAD_MUST_BE_DETACHED")
    protected = _decode_protected(protected_bstr, "SCITT_RECEIPT_PROTECTED_INVALID")
    alg = protected.get(COSE_HDR_ALG)
    if alg not in policy.allowed_cose_algs:
        raise SCITTAuthorizationError("SCITT_RECEIPT_ALG_NOT_ALLOWED")
    if protected.get(COSE_HDR_VDS) != policy.required_vds:
        raise SCITTAuthorizationError("SCITT_VDS_UNSUPPORTED")
    _cwt_identity(
        protected,
        issuer=policy.transparency_service_issuer,
        subject=policy.transparency_service_subject,
        prefix="SCITT_TS",
    )
    kid = _kid_text(protected.get(COSE_HDR_KID), "SCITT_TS_KID_MISSING")
    ts_jwk = _select_jwk(policy.transparency_service_jwks, kid, "SCITT_TS_KID_UNTRUSTED")

    vdp = unprotected.get(COSE_HDR_VDP)
    if not isinstance(vdp, Mapping):
        raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID")
    proofs = vdp.get(COSE_VDP_INCLUSION)
    if not isinstance(proofs, list) or len(proofs) != 1 or not isinstance(proofs[0], bytes):
        raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID")
    try:
        proof = cbor2.loads(proofs[0])
    except Exception as exc:
        raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID") from exc
    if not isinstance(proof, list) or len(proof) != 3:
        raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID")
    tree_size = _integer(proof[0], "SCITT_INCLUSION_PROOF_INVALID")
    leaf_index = _integer(proof[1], "SCITT_INCLUSION_PROOF_INVALID")
    path = proof[2]
    if not isinstance(path, list):
        raise SCITTAuthorizationError("SCITT_INCLUSION_PROOF_INVALID")
    root = _rfc9162_inclusion_root(
        signed_statement,
        tree_size=tree_size,
        leaf_index=leaf_index,
        path=path,
    )
    sig_structure = cbor2.dumps(["Signature1", protected_bstr, b"", root], canonical=True)
    try:
        _verify_es256(
            jwk=ts_jwk,
            signing_input=sig_structure,
            signature=signature,
            code="SCITT_RECEIPT_CRYPTOGRAPHIC_VERIFICATION_FAILED",
        )
    except SCITTAuthorizationError as exc:
        if str(exc) == "SCITT_TRUST_JWKS_INVALID":
            raise
        raise SCITTAuthorizationError("SCITT_RECEIPT_CRYPTOGRAPHIC_VERIFICATION_FAILED") from exc
    return tree_size, leaf_index, root


def verify_scitt_authorization_registration(
    *,
    signed_statement: bytes,
    receipt: bytes,
    trust_policy: SCITTAuthorizationTrustPolicy,
    expected_scope_root: str,
    expected_holder_jkt: str,
    expected_measurement_digest: str,
    verification_time_epoch: int,
) -> SCITTAuthorizationRegistrationReceipt:
    """Verify one authorization Signed Statement and its SCITT inclusion Receipt."""
    if not isinstance(trust_policy, SCITTAuthorizationTrustPolicy):
        raise SCITTAuthorizationError("SCITT_TRUST_POLICY_INVALID")
    now = _integer(verification_time_epoch, "SCITT_VERIFICATION_TIME_INVALID")
    if now < 0:
        raise SCITTAuthorizationError("SCITT_VERIFICATION_TIME_INVALID")
    expected_scope = _hex64(expected_scope_root, "SCITT_EXPECTED_SCOPE_ROOT_INVALID")
    expected_holder = _string(expected_holder_jkt, "SCITT_EXPECTED_HOLDER_JKT_INVALID")
    expected_measurement = _hex64(expected_measurement_digest, "SCITT_EXPECTED_MEASUREMENT_INVALID")
    raw_statement = _bytes(signed_statement, "SCITT_AUTHORIZATION_STATEMENT_INVALID")
    raw_receipt = _bytes(receipt, "SCITT_RECEIPT_INVALID")

    scope, payload = _scope_from_statement(
        raw_statement,
        policy=trust_policy,
        expected_scope_root=expected_scope,
        expected_holder_jkt=expected_holder,
        expected_measurement_digest=expected_measurement,
        verification_time_epoch=now,
    )
    tree_size, leaf_index, merkle_root = _verify_receipt(
        raw_receipt,
        signed_statement=raw_statement,
        policy=trust_policy,
    )

    policy_root = trust_policy.root
    body = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "outcome": SCITT_AUTHORIZATION_REGISTRATION_VERIFIED,
        "registration_verified": True,
        "authorization_issuer": trust_policy.authorization_issuer,
        "authorization_subject": trust_policy.authorization_subject,
        "transparency_service_issuer": trust_policy.transparency_service_issuer,
        "transparency_service_subject": trust_policy.transparency_service_subject,
        "scope_root": scope["scope_root"],
        "holder_jkt": scope["holder_jkt"],
        "measurement_digest": scope["measurement_digest"],
        "authorization_time_evidence_root": scope["authorization_time_evidence_root"],
        "expires_at_epoch": scope["expires_at_epoch"],
        "tree_size": tree_size,
        "leaf_index": leaf_index,
        "merkle_root_sha256": merkle_root.hex(),
        "signed_statement_sha256": hashlib.sha256(raw_statement).hexdigest(),
        "statement_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "cose_receipt_sha256": hashlib.sha256(raw_receipt).hexdigest(),
        "trust_policy_root": policy_root,
        "verification_time_epoch": now,
        "authority_granted": False,
    }
    receipt_root = canonical_hash(RECEIPT_DOMAIN, body)
    return SCITTAuthorizationRegistrationReceipt(**body, receipt_root=receipt_root)
