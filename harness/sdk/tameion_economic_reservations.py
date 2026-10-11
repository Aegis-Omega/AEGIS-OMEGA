"""Durable atomic *testnet evidence* reservation journal for the Tameion safety lab.

SQLite transactions serialize competing local workers, enforce immutable budgets,
prevent idempotency collisions and hold UNKNOWN attempts against budget. This is
NOT a wallet, payment engine, authority source or a distributed custody ledger.

Use a local filesystem with SQLite locks (not NFS or multiple uncoordinated DBs).
No real money, automatic refunds, signer, RPC, network or broadcast path exists.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+\-=]{0,127}\Z")
MAX_MICROUNITS = 1_000_000  # Matches pre-existing Tameion testnet demo ceiling, NOT USDC network limit.
STATES = ("RESERVED", "OUTCOME_UNKNOWN", "OBSERVATION_RECORDED")


class ReservationDenied(ValueError):
    """Explicit fail-closed denial; no state change was committed."""


def _hash(name: str, value: str) -> None:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise ReservationDenied(f"{name}:INVALID_HASH")


def _id(name: str, value: str) -> None:
    if not isinstance(value, str) or ID.fullmatch(value) is None:
        raise ReservationDenied(f"{name}:INVALID_ID")


def _integer(name: str, value: int, *, minimum: int = 0, maximum: int = MAX_MICROUNITS) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ReservationDenied(f"{name}:INVALID_INTEGER")


def _root(domain: str, value: object) -> str:
    raw = json.dumps({"domain": domain, "value": value}, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ReservationSnapshot:
    scope: str
    policy_root: str
    budget_microunits: int
    generation: int
    reserved_microunits: int
    unknown_microunits: int
    observed_microunits: int
    authority_effect: str = "NONE"

    @property
    def used_microunits(self) -> int:
        return self.reserved_microunits + self.unknown_microunits + self.observed_microunits

    @property
    def root(self) -> str:
        return _root("AEGIS_TAMEION_RESERVATION_SNAPSHOT_V1", asdict(self))


@dataclass(frozen=True)
class ReservationReceipt:
    scope: str
    attempt_id: str
    policy_root: str
    intent_root: str
    boundary_root: str
    amount_microunits: int
    state: str
    generation: int
    observation_root: str | None
    operation: str
    authority_effect: str = "NONE"
    network_effect: str = "NONE"
    settlement_asserted: bool = False

    @property
    def root(self) -> str:
        return _root("AEGIS_TAMEION_RESERVATION_RECEIPT_V1", asdict(self))


class EconomicReservationLedger:
    """One DB file is a single, shared local authority-neutral reservation journal."""

    def __init__(self, database_path: str | Path) -> None:
        raw = str(database_path)
        if not raw or raw == ":memory:" or raw.startswith("file:"):
            raise ReservationDenied("DATABASE_PERSISTENCE_REQUIRED")
        path = Path(raw)
        if not path.parent.is_dir():
            raise ReservationDenied("DATABASE_PARENT_MISSING")
        self.path = str(path.resolve())
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS scopes (
                    scope TEXT PRIMARY KEY,
                    policy_root TEXT NOT NULL,
                    budget INTEGER NOT NULL CHECK(budget > 0 AND budget <= 1000000),
                    generation INTEGER NOT NULL DEFAULT 0 CHECK(generation >= 0)
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    scope TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    intent_root TEXT NOT NULL,
                    boundary_root TEXT NOT NULL,
                    amount INTEGER NOT NULL CHECK(amount > 0 AND amount <= 1000000),
                    state TEXT NOT NULL CHECK(state IN ('RESERVED','OUTCOME_UNKNOWN','OBSERVATION_RECORDED')),
                    observation_root TEXT UNIQUE,
                    generation INTEGER NOT NULL,
                    PRIMARY KEY(scope, attempt_id),
                    FOREIGN KEY(scope) REFERENCES scopes(scope)
                );
                """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15.0, isolation_level=None)
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def _connection(self):
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _receipt(scope: str, row: tuple, policy_root: str, operation: str) -> ReservationReceipt:
        attempt_id, intent_root, boundary_root, amount, state, obs, gen = row
        return ReservationReceipt(scope, attempt_id, policy_root, intent_root,
                                  boundary_root, amount, state, gen, obs, operation)

    @staticmethod
    def _summary(db: sqlite3.Connection, scope: str) -> ReservationSnapshot:
        record = db.execute("SELECT policy_root, budget, generation FROM scopes WHERE scope=?", (scope,)).fetchone()
        if record is None:
            raise ReservationDenied("UNKNOWN_SCOPE")
        amounts = dict(db.execute("SELECT state, SUM(amount) FROM attempts WHERE scope=? GROUP BY state", (scope,)))
        return ReservationSnapshot(scope=scope, policy_root=record[0], budget_microunits=record[1],
                                   generation=record[2], reserved_microunits=amounts.get("RESERVED", 0),
                                   unknown_microunits=amounts.get("OUTCOME_UNKNOWN", 0),
                                   observed_microunits=amounts.get("OBSERVATION_RECORDED", 0))

    def open_scope(self, *, scope: str, policy_root: str, budget_microunits: int) -> ReservationSnapshot:
        _id("scope", scope)
        _hash("policy_root", policy_root)
        _integer("budget", budget_microunits, minimum=1)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT policy_root, budget FROM scopes WHERE scope=?", (scope,)).fetchone()
            if existing is None:
                db.execute("INSERT INTO scopes(scope,policy_root,budget) VALUES(?,?,?)",
                           (scope, policy_root, budget_microunits))
            elif existing != (policy_root, budget_microunits):
                raise ReservationDenied("SCOPE_POLICY_IMMUTABLE")
            return self._summary(db, scope)

    def snapshot(self, scope: str) -> ReservationSnapshot:
        _id("scope", scope)
        with self._connection() as db:
            db.execute("BEGIN")
            return self._summary(db, scope)

    def reserve(self, *, scope: str, policy_root: str, attempt_id: str,
                intent_root: str, boundary_root: str, amount_microunits: int,
                expected_generation: int) -> ReservationReceipt:
        _id("scope", scope)
        _id("attempt_id", attempt_id)
        for name, value in (("policy_root", policy_root), ("intent_root", intent_root),
                            ("boundary_root", boundary_root)):
            _hash(name, value)
        _integer("amount", amount_microunits, minimum=1)
        _integer("expected_generation", expected_generation, maximum=2**63-1)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            snap = self._summary(db, scope)
            if policy_root != snap.policy_root:
                raise ReservationDenied("POLICY_ROOT_MISMATCH")
            current = db.execute(
                "SELECT attempt_id,intent_root,boundary_root,amount,state,observation_root,generation "
                "FROM attempts WHERE scope=? AND attempt_id=?", (scope, attempt_id)
            ).fetchone()
            if current is not None:
                if current[1:4] != (intent_root, boundary_root, amount_microunits):
                    raise ReservationDenied("IDEMPOTENCY_COLLISION")
                return self._receipt(scope, current, policy_root, "REPLAYED_NO_MUTATION")
            if expected_generation != snap.generation:
                raise ReservationDenied("STALE_FENCING_GENERATION")
            if snap.used_microunits + amount_microunits > snap.budget_microunits:
                raise ReservationDenied("ATOMIC_BUDGET_EXCEEDED")
            generation = snap.generation + 1
            db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,'RESERVED',NULL,?)",
                       (scope, attempt_id, intent_root, boundary_root, amount_microunits, generation))
            db.execute("UPDATE scopes SET generation=? WHERE scope=?", (generation, scope))
            current = db.execute(
                "SELECT attempt_id,intent_root,boundary_root,amount,state,observation_root,generation "
                "FROM attempts WHERE scope=? AND attempt_id=?", (scope, attempt_id)
            ).fetchone()
            return self._receipt(scope, current, policy_root, "RESERVED_EVIDENCE_ONLY")

    def record_unknown(self, *, scope: str, attempt_id: str,
                       expected_generation: int) -> ReservationReceipt:
        """Unknown external outcome retains reservation; NEVER auto-release/refund."""
        return self._transition(scope, attempt_id, expected_generation, "OUTCOME_UNKNOWN", None)

    def record_observation(self, *, scope: str, attempt_id: str,
                           expected_generation: int, observation_root: str) -> ReservationReceipt:
        """Record supplied evidence digest; NOT proof of payment/finality or signature authenticity."""
        _hash("observation_root", observation_root)
        return self._transition(scope, attempt_id, expected_generation, "OBSERVATION_RECORDED", observation_root)

    def _transition(self, scope: str, attempt_id: str, expected_generation: int,
                    next_state: str, observation_root: str | None) -> ReservationReceipt:
        _id("scope", scope)
        _id("attempt_id", attempt_id)
        _integer("expected_generation", expected_generation, maximum=2**63-1)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            snap = self._summary(db, scope)
            current = db.execute(
                "SELECT attempt_id,intent_root,boundary_root,amount,state,observation_root,generation "
                "FROM attempts WHERE scope=? AND attempt_id=?", (scope, attempt_id)
            ).fetchone()
            if current is None:
                raise ReservationDenied("UNKNOWN_ATTEMPT")
            if current[4] == next_state and current[5] == observation_root:
                return self._receipt(scope, current, snap.policy_root, "REPLAYED_NO_MUTATION")
            if current[4] == "OBSERVATION_RECORDED":
                raise ReservationDenied("OBSERVED_STATE_IMMUTABLE")
            if current[4] == "OUTCOME_UNKNOWN" and next_state == "OUTCOME_UNKNOWN":
                raise ReservationDenied("UNKNOWN_STATE_IMMUTABLE")
            if expected_generation != snap.generation:
                raise ReservationDenied("STALE_FENCING_GENERATION")
            generation = snap.generation + 1
            try:
                db.execute("UPDATE attempts SET state=?,observation_root=?,generation=? WHERE scope=? AND attempt_id=?",
                           (next_state, observation_root, generation, scope, attempt_id))
            except sqlite3.IntegrityError as exc:
                raise ReservationDenied("OBSERVATION_REUSE_FORBIDDEN") from exc
            db.execute("UPDATE scopes SET generation=? WHERE scope=?", (generation, scope))
            updated = db.execute(
                "SELECT attempt_id,intent_root,boundary_root,amount,state,observation_root,generation "
                "FROM attempts WHERE scope=? AND attempt_id=?", (scope, attempt_id)
            ).fetchone()
            return self._receipt(scope, updated, snap.policy_root, "OBSERVATION_RECORDED_NOT_VERIFIED" if next_state == "OBSERVATION_RECORDED" else "UNKNOWN_RETAINED")


def reserve_tameion_evidence(
    ledger: EconomicReservationLedger, *, scope: str, expected_generation: int,
    policy: object, attempt: object, obligation: object, binding: object,
    plan: object, unsigned_call: object, bundle: object, decision: object,
    pinned_policy_root: str, pinned_decision_root: str,
    pinned_mutation_receipt_root: str,
) -> ReservationReceipt:
    """Re-audit the native Tameion object graph then durably reserve synthetic budget.

    PolicyDecision and all pins MUST come from a trusted upstream validator.
    Budget check is recomputed with local persisted values; transaction generation
    fencing forces concurrent contenders to re-evaluate before reserving.
    This is a local capability *observation*, not spend permission.
    """
    from dataclasses import replace
    from harness.sdk.tameion_economic_kernel import audit_economic_boundary

    snapshot = ledger.snapshot(scope)
    if (policy.root != snapshot.policy_root or
        policy.budget_microunits != snapshot.budget_microunits or
        policy.root != pinned_policy_root):
        raise ReservationDenied("POLICY_SCOPE_MISMATCH")
    if expected_generation != snapshot.generation:
        raise ReservationDenied("STALE_FENCING_GENERATION")

    checked_attempt = replace(
        attempt,
        confirmed_spend_microunits=snapshot.observed_microunits,
        reserved_spend_microunits=snapshot.reserved_microunits + snapshot.unknown_microunits,
    )
    finding = audit_economic_boundary(
        policy=policy, attempt=checked_attempt, obligation=obligation,
        binding=binding, plan=plan, unsigned_call=unsigned_call, bundle=bundle,
        decision=decision, pinned_policy_root=pinned_policy_root,
        pinned_decision_root=pinned_decision_root,
        pinned_mutation_receipt_root=pinned_mutation_receipt_root,
    )
    if finding.outcome != "BOUNDARY_CHECKS_PASSED" or finding.denial_codes:
        raise ReservationDenied("BOUNDARY_DENIED:" + ",".join(finding.denial_codes))
    if (finding.authority_effect != "NONE" or finding.network_effect != "NONE" or
        finding.settlement_asserted is not False):
        raise ReservationDenied("BOUNDARY_AUTHORITY_ESCALATION")
    return ledger.reserve(
        scope=scope, policy_root=policy.root,
        attempt_id=checked_attempt.attempt_id,
        intent_root=plan.root, boundary_root=finding.root,
        amount_microunits=plan.amount_microunits,
        expected_generation=expected_generation,
    )