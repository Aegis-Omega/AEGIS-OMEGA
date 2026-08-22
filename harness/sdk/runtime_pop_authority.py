"""Authority-bound composition for cryptographic RuntimePoP evidence.

This layer deliberately sits between ``runtime_pop_crypto`` and the existing
structural ``principal_binding`` contract. Caller-supplied
``verification_state=VERIFIED`` / ``proof_root`` values are never trusted: they
are replaced with values derived from a successful cryptographic receipt before
the principal binding reaches Automaton-3 authority evaluation.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from harness.sdk.principal_binding import ExecutionPrincipalBinding
from harness.sdk.runtime_pop_crypto import (
    CryptoVerificationError,
    ReplayStore,
    RuntimePoPCryptoReceipt,
    verify_runtime_pop_evidence,
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


def bind_execution_principal_from_crypto(
    raw_principal: Mapping[str, Any],
    crypto_evidence: Mapping[str, Any],
    *,
    generation: int,
    replay_store: ReplayStore | None = None,
) -> tuple[ExecutionPrincipalBinding, RuntimePoPCryptoReceipt]:
    """Replace self-asserted RuntimePoP state with cryptographically derived evidence."""
    if not isinstance(raw_principal, Mapping):
        raise CryptoVerificationError("EXECUTION_PRINCIPAL_NOT_OBJECT")
    if not isinstance(crypto_evidence, Mapping):
        raise CryptoVerificationError("RUNTIME_POP_CRYPTO_EVIDENCE_NOT_OBJECT")
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

    receipt = verify_runtime_pop_evidence(crypto_evidence, replay_store=replay_store)
    if receipt.runtime_principal != raw_runtime:
        raise CryptoVerificationError("CRYPTO_RUNTIME_PRINCIPAL_MISMATCH")
    if receipt.binding_mode != declared_mode:
        raise CryptoVerificationError("CRYPTO_BINDING_MODE_MISMATCH")

    derived_pop = receipt.to_runtime_pop_verification(generation=generation)
    sanitized = dict(raw_principal)
    sanitized["runtime_pop"] = asdict(derived_pop)
    try:
        binding = ExecutionPrincipalBinding.from_mapping(sanitized)
    except Exception as exc:
        raise CryptoVerificationError("EXECUTION_PRINCIPAL_REBIND_INVALID") from exc
    return binding, receipt
