"""Authority-bound composition for cryptographic RuntimePoP evidence.

This layer deliberately sits between ``runtime_pop_crypto`` and the existing
structural ``principal_binding`` contract.

Security boundary:

* presented credential/evidence is not a trust anchor;
* caller-supplied ``verification_state=VERIFIED`` / ``proof_root`` values are
  discarded;
* issuer, audience, issuer verification keys, X.509 roots, allowed PoP modes,
  allowed SPIFFE trust domains, and verification time come from the verifier /
  deployment boundary rather than the presented credential;
* the structural RuntimePoP proof root binds both the cryptographic receipt and
  the exact trust-policy root;
* this module still grants no AEGIS authority. It only produces evidence that
  can be consumed as a necessary precondition by Automaton-3.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from harness.sdk.principal_binding import (
    VERIFIED,
    ExecutionPrincipalBinding,
    RuntimePoPVerification,
    canonical_hash,
)
from harness.sdk.runtime_pop_crypto import (
    CRYPTO_SCHEMA_VERSION,
    CRYPTO_VERIFIER_IDENTITY,
    SUPPORTED_CRYPTO_MODES,
    CryptoVerificationError,
    ReplayStore,
    RuntimePoPCryptoReceipt,
    verify_runtime_pop_evidence,
)

TRUST_POLICY_SCHEMA_VERSION = "1.0.0"
TRUST_POLICY_KIND = "AEGIS_RUNTIME_POP_TRUST_POLICY_V1"
TRUST_BOUND_PROOF_DOMAIN = "AEGIS_RUNTIME_POP_TRUST_BOUND_PROOF_V1"
_PRIVATE_JWK_MEMBERS = frozenset(("d", "p", "q", "dp", "dq", "qi", "oth", "k"))


def _nonempty_string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CryptoVerificationError(code)
    return value


def _string_tuple(value: Any, *, code: str, nonempty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise CryptoVerificationError(code)
    items = tuple(value)
    if nonempty and not items:
        raise CryptoVerificationError(code)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise CryptoVerificationError(code)
    if len(set(items)) != len(items):
        raise CryptoVerificationError(code)
    return items


@dataclass(frozen=True)
class RuntimePoPTrustPolicy:
    """Deployment/operator-selected trust anchors for RuntimePoP verification."""

    schema_version: str
    policy_id: str
    expected_issuer: str
    expected_audience: str
    issuer_jwks: Mapping[str, Any]
    x509_trust_roots_pem: tuple[str, ...]
    allowed_binding_modes: tuple[str, ...]
    allowed_spiffe_trust_domains: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimePoPTrustPolicy":
        if not isinstance(value, Mapping):
            raise CryptoVerificationError("RUNTIME_POP_TRUST_POLICY_NOT_OBJECT")
        if value.get("schema_version") != TRUST_POLICY_SCHEMA_VERSION:
            raise CryptoVerificationError("RUNTIME_POP_TRUST_POLICY_SCHEMA_UNSUPPORTED")

        policy_id = _nonempty_string(value.get("policy_id"), "RUNTIME_POP_TRUST_POLICY_ID_MISSING")
        expected_issuer = _nonempty_string(value.get("expected_issuer"), "RUNTIME_POP_TRUST_ISSUER_MISSING")
        expected_audience = _nonempty_string(value.get("expected_audience"), "RUNTIME_POP_TRUST_AUDIENCE_MISSING")

        raw_jwks = value.get("issuer_jwks")
        if not isinstance(raw_jwks, Mapping) or not isinstance(raw_jwks.get("keys"), list) or not raw_jwks["keys"]:
            raise CryptoVerificationError("RUNTIME_POP_TRUST_JWKS_INVALID")
        keys: list[dict[str, Any]] = []
        for item in raw_jwks["keys"]:
            if not isinstance(item, Mapping):
                raise CryptoVerificationError("RUNTIME_POP_TRUST_JWKS_INVALID")
            if _PRIVATE_JWK_MEMBERS.intersection(item.keys()):
                raise CryptoVerificationError("RUNTIME_POP_TRUST_PRIVATE_JWK_FORBIDDEN")
            keys.append(dict(item))
        issuer_jwks: Mapping[str, Any] = {"keys": keys}

        roots = _string_tuple(
            value.get("x509_trust_roots_pem"),
            code="RUNTIME_POP_TRUST_ROOTS_INVALID",
        )
        modes = _string_tuple(
            value.get("allowed_binding_modes"),
            code="RUNTIME_POP_TRUST_BINDING_MODES_INVALID",
        )
        if any(mode not in SUPPORTED_CRYPTO_MODES for mode in modes):
            raise CryptoVerificationError("RUNTIME_POP_TRUST_BINDING_MODE_UNSUPPORTED")

        domains = _string_tuple(
            value.get("allowed_spiffe_trust_domains"),
            code="RUNTIME_POP_TRUST_SPIFFE_DOMAINS_INVALID",
        )
        for domain in domains:
            if "://" in domain or "/" in domain or "?" in domain or "#" in domain or "@" in domain:
                raise CryptoVerificationError("RUNTIME_POP_TRUST_SPIFFE_DOMAIN_INVALID")

        return cls(
            schema_version=TRUST_POLICY_SCHEMA_VERSION,
            policy_id=policy_id,
            expected_issuer=expected_issuer,
            expected_audience=expected_audience,
            issuer_jwks=issuer_jwks,
            x509_trust_roots_pem=roots,
            allowed_binding_modes=modes,
            allowed_spiffe_trust_domains=domains,
        )

    @property
    def root(self) -> str:
        return canonical_hash(
            TRUST_POLICY_KIND,
            {
                "schema_version": self.schema_version,
                "policy_id": self.policy_id,
                "expected_issuer": self.expected_issuer,
                "expected_audience": self.expected_audience,
                "issuer_jwks": self.issuer_jwks,
                "x509_trust_roots_pem": list(self.x509_trust_roots_pem),
                "allowed_binding_modes": list(self.allowed_binding_modes),
                "allowed_spiffe_trust_domains": list(self.allowed_spiffe_trust_domains),
            },
        )


class SQLiteReplayStore:
    """Durable, atomic DPoP replay store for a shared local filesystem.

    SQLite gives multiple processes on one host an atomic uniqueness boundary.
    It is not a claim of cross-host/global replay protection. Distributed
    deployments must point all verifiers at a shared transactional store or
    supply another ``ReplayStore`` implementation with equivalent atomic
    consume semantics.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_absolute():
            raise CryptoVerificationError("DPOP_REPLAY_DB_PATH_NOT_ABSOLUTE")
        if not self.path.parent.exists():
            raise CryptoVerificationError("DPOP_REPLAY_DB_PARENT_MISSING")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS dpop_replay ("
                    "replay_key TEXT PRIMARY KEY, "
                    "expires_at INTEGER NOT NULL CHECK(expires_at >= 0)"
                    ")"
                )
        except sqlite3.Error as exc:
            raise CryptoVerificationError("DPOP_REPLAY_DB_UNAVAILABLE") from exc

    def consume(self, key: str, *, now_epoch: int, expires_at: int) -> bool:
        if not isinstance(key, str) or not key:
            raise CryptoVerificationError("DPOP_REPLAY_KEY_INVALID")
        if isinstance(now_epoch, bool) or not isinstance(now_epoch, int) or now_epoch < 0:
            raise CryptoVerificationError("DPOP_REPLAY_NOW_INVALID")
        if isinstance(expires_at, bool) or not isinstance(expires_at, int) or expires_at <= now_epoch:
            raise CryptoVerificationError("DPOP_REPLAY_EXPIRY_INVALID")
        try:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM dpop_replay WHERE expires_at <= ?", (now_epoch,))
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO dpop_replay(replay_key, expires_at) VALUES (?, ?)",
                    (key, expires_at),
                )
                inserted = cursor.rowcount == 1
                connection.execute("COMMIT")
                return inserted
            except Exception:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                connection.close()
        except CryptoVerificationError:
            raise
        except sqlite3.Error as exc:
            raise CryptoVerificationError("DPOP_REPLAY_DB_UNAVAILABLE") from exc


def _spiffe_trust_domain(runtime_principal: str) -> str:
    parsed = urlsplit(runtime_principal)
    if parsed.scheme != "spiffe" or not parsed.netloc or parsed.path in ("", "/") or parsed.query or parsed.fragment:
        raise CryptoVerificationError("EXECUTION_RUNTIME_PRINCIPAL_INVALID")
    return parsed.netloc


def bind_execution_principal_from_crypto(
    raw_principal: Mapping[str, Any],
    crypto_evidence: Mapping[str, Any],
    *,
    trust_policy: RuntimePoPTrustPolicy,
    verification_time_epoch: int,
    generation: int,
    replay_store: ReplayStore | None = None,
) -> tuple[ExecutionPrincipalBinding, RuntimePoPCryptoReceipt, str]:
    """Replace self-asserted RuntimePoP state with trust/time-bound crypto evidence."""
    if not isinstance(raw_principal, Mapping):
        raise CryptoVerificationError("EXECUTION_PRINCIPAL_NOT_OBJECT")
    if not isinstance(crypto_evidence, Mapping):
        raise CryptoVerificationError("RUNTIME_POP_CRYPTO_EVIDENCE_NOT_OBJECT")
    if not isinstance(trust_policy, RuntimePoPTrustPolicy):
        raise CryptoVerificationError("RUNTIME_POP_TRUST_POLICY_INVALID")
    if isinstance(verification_time_epoch, bool) or not isinstance(verification_time_epoch, int) or verification_time_epoch < 0:
        raise CryptoVerificationError("RUNTIME_POP_VERIFICATION_TIME_INVALID")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise CryptoVerificationError("RUNTIME_POP_GENERATION_INVALID")

    raw_runtime = raw_principal.get("runtime_principal")
    if not isinstance(raw_runtime, str) or not raw_runtime.strip():
        raise CryptoVerificationError("EXECUTION_RUNTIME_PRINCIPAL_MISSING")
    raw_pop = raw_principal.get("runtime_pop")
    if not isinstance(raw_pop, Mapping):
        raise CryptoVerificationError("EXECUTION_RUNTIME_POP_MISSING")
    declared_mode = raw_pop.get("binding_mode")
    if not isinstance(declared_mode, str) or not declared_mode.strip():
        raise CryptoVerificationError("EXECUTION_RUNTIME_POP_MODE_MISSING")
    if declared_mode not in trust_policy.allowed_binding_modes:
        raise CryptoVerificationError("RUNTIME_POP_BINDING_MODE_NOT_ALLOWED")

    trust_domain = _spiffe_trust_domain(raw_runtime)
    if trust_domain not in trust_policy.allowed_spiffe_trust_domains:
        raise CryptoVerificationError("SPIFFE_TRUST_DOMAIN_NOT_ALLOWED")

    presented_runtime = crypto_evidence.get("runtime_principal")
    if presented_runtime is not None and presented_runtime != raw_runtime:
        raise CryptoVerificationError("CRYPTO_EVIDENCE_RUNTIME_PRINCIPAL_MISMATCH")
    presented_mode = crypto_evidence.get("binding_mode")
    if presented_mode is not None and presented_mode != declared_mode:
        raise CryptoVerificationError("CRYPTO_EVIDENCE_BINDING_MODE_MISMATCH")

    # Copy presented evidence, then overwrite every verifier-controlled field.
    # The credential cannot choose issuer keys, audience, certificate roots, or
    # the clock against which token/proof freshness is evaluated.
    trusted_evidence = dict(crypto_evidence)
    trusted_evidence["schema_version"] = CRYPTO_SCHEMA_VERSION
    trusted_evidence["runtime_principal"] = raw_runtime
    trusted_evidence["binding_mode"] = declared_mode
    trusted_evidence["now_epoch"] = verification_time_epoch
    trusted_evidence["expected_issuer"] = trust_policy.expected_issuer
    trusted_evidence["expected_audience"] = trust_policy.expected_audience
    trusted_evidence["issuer_jwks"] = {"keys": [dict(item) for item in trust_policy.issuer_jwks["keys"]]}
    trusted_evidence["x509_trust_roots_pem"] = list(trust_policy.x509_trust_roots_pem)

    receipt = verify_runtime_pop_evidence(trusted_evidence, replay_store=replay_store)
    if receipt.runtime_principal != raw_runtime:
        raise CryptoVerificationError("CRYPTO_RUNTIME_PRINCIPAL_MISMATCH")
    if receipt.binding_mode != declared_mode:
        raise CryptoVerificationError("CRYPTO_BINDING_MODE_MISMATCH")
    if receipt.verifier_identity != CRYPTO_VERIFIER_IDENTITY:
        raise CryptoVerificationError("CRYPTO_VERIFIER_IDENTITY_MISMATCH")
    if receipt.verification_time_epoch != verification_time_epoch:
        raise CryptoVerificationError("CRYPTO_VERIFICATION_TIME_MISMATCH")

    policy_root = trust_policy.root
    trust_bound_root = canonical_hash(
        TRUST_BOUND_PROOF_DOMAIN,
        {
            "crypto_receipt_root": receipt.proof_root,
            "trust_policy_root": policy_root,
            "runtime_principal": raw_runtime,
            "binding_mode": declared_mode,
        },
    )
    derived_pop = RuntimePoPVerification(
        runtime_principal=raw_runtime,
        binding_mode=declared_mode,
        verification_state=VERIFIED,
        verifier_identity=receipt.verifier_identity,
        proof_root=trust_bound_root,
        evidence_ref=f"crypto+trust:sha256:{trust_bound_root}",
        generation=generation,
    )

    sanitized = dict(raw_principal)
    sanitized["runtime_pop"] = asdict(derived_pop)
    try:
        binding = ExecutionPrincipalBinding.from_mapping(sanitized)
    except Exception as exc:
        raise CryptoVerificationError("EXECUTION_PRINCIPAL_REBIND_INVALID") from exc
    return binding, receipt, policy_root
