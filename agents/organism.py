"""Durable, fail-closed organizational work loop for AEGIS Ω.

Provider contributions are content-addressed NON_AUTHORITATIVE_EVIDENCE. Claims
are scheduling leases only: they never confer authority. Claim fencing mirrors
the existing Frontier SSEStreamLease owner/generation/token semantics and is
persisted in the same hash-chained organism store.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Iterator

GENESIS = "0" * 64
STORE_VERSION = "AEGIS_ORGANISM_STORE_V1"
JOURNAL_DOMAIN = "AEGIS_ORGANISM_JOURNAL_V1"
CONTRIBUTION_SCHEMA = "AEGIS_PROVIDER_CONTRIBUTION_ARTIFACT_V1"
MAX_TEXT_CONTRIBUTION_BYTES = 262_144
MAX_CLAIM_LEASE_MS = 900_000
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9._:/@+\-]{1,128}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_TEXT_MEDIA = frozenset({"text/plain", "text/markdown", "application/json"})


class WorkStatus(str, Enum):
    QUEUED = "QUEUED"
    WAITING_OPERATOR = "WAITING_OPERATOR"
    RUNNING = "RUNNING"
    EXECUTED = "EXECUTED"
    BLOCKED_AUTHORITY = "BLOCKED_AUTHORITY"
    FAILED = "FAILED"
    DENIED = "DENIED"


TERMINAL = {WorkStatus.EXECUTED, WorkStatus.BLOCKED_AUTHORITY, WorkStatus.FAILED, WorkStatus.DENIED}


@dataclass
class WorkOrder:
    work_id: str
    event_type: str
    payload: dict[str, Any]
    consequence_class: str
    status: WorkStatus
    max_attempts: int = 3
    attempts: int = 0
    created_ms: int = 0
    updated_ms: int = 0
    approval_ref: str | None = None
    last_error: str | None = None
    contribution_refs: tuple[str, ...] = ()
    claim_owner_identity: str | None = None
    claim_generation: int = 0
    claim_fencing_token: str | None = None
    claim_expires_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["contribution_refs"] = list(self.contribution_refs)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WorkOrder":
        x = dict(d)
        x["status"] = WorkStatus(x["status"])
        x["contribution_refs"] = tuple(x.get("contribution_refs", ()))
        return cls(**x)


Dispatcher = Callable[[str, dict[str, Any]], Awaitable[Iterable[Any]]]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _domain_hash(domain: str, value: Any) -> str:
    return hashlib.sha256(_canonical({"domain": domain, "value": value})).hexdigest()


def _hash_event(prev: str, seq: int, event_type: str, body: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(JOURNAL_DOMAIN.encode("ascii"))
    h.update(b"\0")
    h.update(prev.encode("ascii"))
    h.update(b"\0")
    h.update(str(seq).encode("ascii"))
    h.update(b"\0")
    h.update(event_type.encode("utf-8"))
    h.update(b"\0")
    h.update(_canonical(body))
    return h.hexdigest()


def _frontier_fence(work_id: str, owner_identity: str, generation: int) -> str:
    """Byte-identical to platform/sol/frontier/stream_lease.py::_fence."""
    if not work_id or not owner_identity:
        raise ValueError("WORK_CLAIM_IDENTITY_REQUIRED")
    if generation < 0:
        raise ValueError("WORK_CLAIM_GENERATION_INVALID")
    material = f"{work_id}\x00{owner_identity}\x00{generation}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class ContributionArtifactStore:
    """Content-addressed text evidence. Artifact existence never grants authority."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def put_text(self, text: str, *, media_type: str = "text/markdown") -> dict[str, Any]:
        if media_type not in _ALLOWED_TEXT_MEDIA:
            raise ValueError("CONTRIBUTION_MEDIA_TYPE_INVALID")
        raw = text.encode("utf-8")
        if not raw:
            raise ValueError("CONTRIBUTION_EMPTY")
        if len(raw) > MAX_TEXT_CONTRIBUTION_BYTES:
            raise ValueError("CONTRIBUTION_TOO_LARGE")
        digest = hashlib.sha256(raw).hexdigest()
        path = self.root / digest[:2] / f"{digest}.json"
        record = {
            "schema_version": CONTRIBUTION_SCHEMA,
            "sha256": digest,
            "media_type": media_type,
            "byte_length": len(raw),
            "content": text,
            "authority": "NON_AUTHORITATIVE_EVIDENCE",
        }
        rendered = json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False)
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != record:
                raise ValueError("CONTRIBUTION_CONTENT_ADDRESS_COLLISION")
        else:
            _atomic_write(path, rendered)
        return {**record, "artifact_path": str(path)}

    def get(self, digest: str) -> dict[str, Any]:
        if not _SHA256_RE.fullmatch(digest):
            raise ValueError("ARTIFACT_DIGEST_INVALID")
        path = self.root / digest[:2] / f"{digest}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        actual = hashlib.sha256(str(record.get("content", "")).encode("utf-8")).hexdigest()
        if record.get("sha256") != digest or actual != digest:
            raise ValueError("CONTRIBUTION_ARTIFACT_TAMPER_DETECTED")
        return record


class OrganismStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._state: dict[str, Any]
        if self.path.exists():
            self.refresh()
        else:
            self._state = {"store_version": STORE_VERSION, "orders": {}, "journal": []}
            self._persist()

    def _validate(self) -> None:
        if self._state.get("store_version") != STORE_VERSION:
            raise ValueError("ORGANISM_STORE_VERSION_MISMATCH")
        prev = GENESIS
        for seq, entry in enumerate(self._state.get("journal", [])):
            if entry.get("seq") != seq:
                raise ValueError("ORGANISM_JOURNAL_SEQUENCE_MISMATCH")
            expected = _hash_event(prev, seq, entry.get("event_type", ""), entry.get("body", {}))
            if entry.get("prev_hash") != prev or entry.get("event_hash") != expected:
                raise ValueError("ORGANISM_JOURNAL_TAMPER_DETECTED")
            prev = expected

    def refresh(self) -> None:
        self._state = json.loads(self.path.read_text(encoding="utf-8"))
        self._validate()

    @contextmanager
    def exclusive(self, *, timeout_ms: int = 5_000) -> Iterator[None]:
        """Cross-process local-store lock using atomic directory creation.

        A stale lock is never guessed away. Timeout is fail-closed and requires
        operator/remediation rather than risking split-brain scheduling.
        """
        lock = Path(str(self.path) + ".lock")
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            try:
                lock.mkdir(parents=False)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise ValueError("ORGANISM_STORE_LOCK_TIMEOUT")
                time.sleep(0.01)
        try:
            self.refresh()
            yield
        finally:
            try:
                lock.rmdir()
            except FileNotFoundError:
                pass

    def _persist(self) -> None:
        _atomic_write(self.path, json.dumps(self._state, sort_keys=True, indent=2, ensure_ascii=False))

    def _append(self, event_type: str, body: dict[str, Any]) -> None:
        journal = self._state["journal"]
        prev = journal[-1]["event_hash"] if journal else GENESIS
        seq = len(journal)
        event_hash = _hash_event(prev, seq, event_type, body)
        journal.append({"seq": seq, "event_type": event_type, "body": body, "prev_hash": prev, "event_hash": event_hash})

    def state_root(self) -> str:
        journal = self._state["journal"]
        return journal[-1]["event_hash"] if journal else GENESIS

    def save_order(self, order: WorkOrder, event_type: str, *, event_body: dict[str, Any] | None = None) -> None:
        self._state["orders"][order.work_id] = order.to_dict()
        self._append(event_type, event_body if event_body is not None else order.to_dict())
        self._persist()

    def get(self, work_id: str) -> WorkOrder | None:
        raw = self._state["orders"].get(work_id)
        return WorkOrder.from_dict(raw) if raw else None

    def orders(self) -> list[WorkOrder]:
        return [WorkOrder.from_dict(x) for x in self._state["orders"].values()]

    def journal(self) -> list[dict[str, Any]]:
        return list(self._state["journal"])


class OrganizationOrganism:
    def __init__(self, store: OrganismStore, dispatcher: Dispatcher | None = None, contribution_store: ContributionArtifactStore | None = None):
        self.store = store
        self.dispatcher = dispatcher or self._default_dispatcher
        self.contribution_store = contribution_store or ContributionArtifactStore(store.path.parent / "contributions")

    @staticmethod
    async def _default_dispatcher(event_type: str, payload: dict[str, Any]):
        from agents.coordinator import dispatch_event
        return await dispatch_event(event_type, payload)

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    def orders(self) -> list[WorkOrder]:
        return sorted(self.store.orders(), key=lambda w: (w.created_ms, w.work_id))

    def get(self, work_id: str) -> WorkOrder:
        order = self.store.get(work_id)
        if order is None:
            raise KeyError(work_id)
        return order

    @staticmethod
    def _claim_active(order: WorkOrder, now_ms: int) -> bool:
        return (
            order.claim_owner_identity is not None
            and order.claim_fencing_token is not None
            and order.claim_expires_ms is not None
            and now_ms <= order.claim_expires_ms
        )

    @staticmethod
    def _claim_view(order: WorkOrder) -> dict[str, Any]:
        if order.claim_owner_identity is None or order.claim_fencing_token is None or order.claim_expires_ms is None:
            raise ValueError("WORK_CLAIM_MISSING")
        return {
            "claim_kind": "AEGIS_DURABLE_WORK_CLAIM_V1",
            "work_id": order.work_id,
            "owner_identity": order.claim_owner_identity,
            "generation": order.claim_generation,
            "fencing_token": order.claim_fencing_token,
            "expires_ms": order.claim_expires_ms,
            "authority": "SCHEDULING_LEASE_ONLY",
        }

    def next_work(self, *, limit: int = 10, now_ms: int | None = None) -> list[WorkOrder]:
        if limit < 1 or limit > 100:
            raise ValueError("NEXT_WORK_LIMIT_INVALID")
        if now_ms is None:
            now_ms = self._now_ms()
        self.store.refresh()
        return [
            w for w in self.orders()
            if w.status == WorkStatus.QUEUED and not w.contribution_refs and not self._claim_active(w, now_ms)
        ][:limit]

    def submit(self, work_id: str, event_type: str, payload: dict[str, Any], *, consequence_class: str, max_attempts: int = 3) -> WorkOrder:
        existing = self.store.get(work_id)
        if existing is not None:
            return existing
        if not work_id or not event_type:
            raise ValueError("WORK_ID_AND_EVENT_REQUIRED")
        if max_attempts < 1:
            raise ValueError("MAX_ATTEMPTS_INVALID")
        cc = consequence_class.upper()
        now = self._now_ms()
        if cc in {"D0", "D1", "D2"}:
            status = WorkStatus.QUEUED
        elif cc == "D3":
            status = WorkStatus.WAITING_OPERATOR
        else:
            status = WorkStatus.DENIED
        order = WorkOrder(work_id, event_type, dict(payload), cc, status, max_attempts=max_attempts, created_ms=now, updated_ms=now)
        self.store.save_order(order, "WORK_SUBMITTED")
        return order

    def prepare_claim(self, work_id: str) -> dict[str, Any]:
        self.store.refresh()
        order = self.get(work_id)
        return {
            "work_id": work_id,
            "state_root": self.store.state_root(),
            "order_digest": _domain_hash("AEGIS_ORGANISM_CLAIM_PRESTATE_V1", order.to_dict()),
            "next_generation": order.claim_generation + 1,
        }

    def claim_work(self, work_id: str, *, owner_identity: str, expected_state_root: str, lease_ms: int, now_ms: int | None = None) -> dict[str, Any]:
        if not _IDENTITY_RE.fullmatch(owner_identity):
            raise ValueError("WORK_CLAIM_OWNER_INVALID")
        if not _SHA256_RE.fullmatch(expected_state_root):
            raise ValueError("WORK_CLAIM_PRESTATE_INVALID")
        if isinstance(lease_ms, bool) or not isinstance(lease_ms, int) or not (1 <= lease_ms <= MAX_CLAIM_LEASE_MS):
            raise ValueError("WORK_CLAIM_LEASE_INVALID")
        if now_ms is None:
            now_ms = self._now_ms()
        if isinstance(now_ms, bool) or not isinstance(now_ms, int) or now_ms < 0:
            raise ValueError("WORK_CLAIM_TIME_INVALID")
        with self.store.exclusive():
            if self.store.state_root() != expected_state_root:
                raise ValueError("WORK_CLAIM_PRESTATE_STALE")
            order = self.get(work_id)
            if order.status != WorkStatus.QUEUED or order.contribution_refs:
                raise ValueError("WORK_NOT_CLAIMABLE")
            if self._claim_active(order, now_ms):
                if order.claim_owner_identity == owner_identity:
                    return self._claim_view(order)
                raise ValueError("WORK_CLAIM_ACTIVE")
            prior_generation = order.claim_generation
            generation = prior_generation + 1
            token = _frontier_fence(work_id, owner_identity, generation)
            order.claim_owner_identity = owner_identity
            order.claim_generation = generation
            order.claim_fencing_token = token
            order.claim_expires_ms = now_ms + lease_ms
            order.updated_ms = now_ms
            self.store.save_order(order, "WORK_CLAIMED", event_body={
                "work_id": work_id,
                "owner_identity": owner_identity,
                "generation": generation,
                "fencing_token_digest": _domain_hash("AEGIS_WORK_CLAIM_FENCE_REDACTION_V1", token),
                "expires_ms": order.claim_expires_ms,
                "replaces_generation": prior_generation,
                "authority": "SCHEDULING_LEASE_ONLY",
            })
            return self._claim_view(order)

    def _verify_claim(self, order: WorkOrder, *, owner_identity: str, claim_generation: int, claim_fencing_token: str, now_ms: int) -> None:
        if order.claim_owner_identity is None or order.claim_fencing_token is None or order.claim_expires_ms is None:
            raise ValueError("WORK_CLAIM_MISSING")
        if order.claim_owner_identity != owner_identity:
            raise ValueError("WORK_CLAIM_OWNER_MISMATCH")
        if order.claim_generation != claim_generation:
            raise ValueError("WORK_CLAIM_GENERATION_MISMATCH")
        if order.claim_fencing_token != claim_fencing_token:
            raise ValueError("WORK_CLAIM_FENCE_MISMATCH")
        if now_ms > order.claim_expires_ms:
            raise ValueError("WORK_CLAIM_EXPIRED")

    def release_claim(self, work_id: str, *, owner_identity: str, claim_generation: int, claim_fencing_token: str, now_ms: int | None = None) -> bool:
        if now_ms is None:
            now_ms = self._now_ms()
        with self.store.exclusive():
            order = self.get(work_id)
            self._verify_claim(order, owner_identity=owner_identity, claim_generation=claim_generation, claim_fencing_token=claim_fencing_token, now_ms=now_ms)
            order.claim_owner_identity = None
            order.claim_fencing_token = None
            order.claim_expires_ms = None
            order.updated_ms = now_ms
            self.store.save_order(order, "WORK_CLAIM_RELEASED", event_body={
                "work_id": work_id,
                "owner_identity": owner_identity,
                "generation": claim_generation,
                "authority": "SCHEDULING_LEASE_ONLY",
            })
            return True

    def prepare_contribution(self, work_id: str) -> dict[str, str]:
        order = self.get(work_id)
        order_digest = _domain_hash("AEGIS_ORGANISM_ORDER_PRESTATE_V1", order.to_dict())
        state_root = self.store.state_root()
        rollback_reference = f"organism:{work_id}:order:{order_digest}:state:{state_root}"
        return {"work_id": work_id, "order_digest": order_digest, "state_root": state_root, "rollback_reference": rollback_reference}

    def _verify_contribution_prestate(self, work_id: str, rollback_reference: str | None) -> dict[str, str]:
        prepared = self.prepare_contribution(work_id)
        if rollback_reference is not None and rollback_reference != prepared["rollback_reference"]:
            raise ValueError("CONTRIBUTION_PRESTATE_STALE")
        return prepared

    @staticmethod
    def _validate_contribution_identity(provider: str, model: str, source_ref: str, artifact_digest: str) -> str:
        for value, code in ((provider, "PROVIDER_ID_INVALID"), (model, "MODEL_ID_INVALID"), (source_ref, "SOURCE_REF_INVALID")):
            if not _IDENTITY_RE.fullmatch(value):
                raise ValueError(code)
        if not _SHA256_RE.fullmatch(artifact_digest):
            raise ValueError("ARTIFACT_DIGEST_INVALID")
        return f"provider:{provider}:model:{model}:sha256:{artifact_digest}:source:{source_ref}"

    def record_contribution(self, work_id: str, *, provider: str, model: str, artifact_digest: str, source_ref: str, rollback_reference: str | None = None) -> str:
        prepared = self._verify_contribution_prestate(work_id, rollback_reference)
        order = self.get(work_id)
        if order.claim_owner_identity is not None:
            raise ValueError("WORK_CLAIM_REQUIRED")
        contribution_ref = self._validate_contribution_identity(provider, model, source_ref, artifact_digest)
        if contribution_ref in order.contribution_refs:
            return contribution_ref
        order.contribution_refs = (*order.contribution_refs, contribution_ref)
        order.updated_ms = self._now_ms()
        self.store.save_order(order, "PROVIDER_CONTRIBUTION_RECORDED", event_body={
            "work_id": work_id,
            "provider": provider,
            "model": model,
            "artifact_digest": artifact_digest,
            "source_ref": source_ref,
            "contribution_ref": contribution_ref,
            "authority": "NON_AUTHORITATIVE_EVIDENCE",
            "pre_state_root": prepared["state_root"],
            "pre_order_digest": prepared["order_digest"],
            "rollback_reference": prepared["rollback_reference"],
            "status_after": order.status.value,
        })
        return contribution_ref

    def record_claimed_contribution(self, work_id: str, *, owner_identity: str, claim_generation: int, claim_fencing_token: str, provider: str, model: str, artifact_digest: str, source_ref: str, now_ms: int | None = None) -> str:
        if now_ms is None:
            now_ms = self._now_ms()
        contribution_ref = self._validate_contribution_identity(provider, model, source_ref, artifact_digest)
        with self.store.exclusive():
            order = self.get(work_id)
            self._verify_claim(order, owner_identity=owner_identity, claim_generation=claim_generation, claim_fencing_token=claim_fencing_token, now_ms=now_ms)
            if contribution_ref not in order.contribution_refs:
                order.contribution_refs = (*order.contribution_refs, contribution_ref)
            order.claim_owner_identity = None
            order.claim_fencing_token = None
            order.claim_expires_ms = None
            order.updated_ms = now_ms
            self.store.save_order(order, "PROVIDER_CLAIMED_CONTRIBUTION_RECORDED", event_body={
                "work_id": work_id,
                "owner_identity": owner_identity,
                "claim_generation": claim_generation,
                "claim_fencing_token_digest": _domain_hash("AEGIS_WORK_CLAIM_FENCE_REDACTION_V1", claim_fencing_token),
                "provider": provider,
                "model": model,
                "artifact_digest": artifact_digest,
                "source_ref": source_ref,
                "contribution_ref": contribution_ref,
                "authority": "NON_AUTHORITATIVE_EVIDENCE",
                "status_after": order.status.value,
            })
            return contribution_ref

    def contribute_text(self, work_id: str, *, provider: str, model: str, text: str, source_ref: str, media_type: str = "text/markdown", rollback_reference: str | None = None) -> dict[str, Any]:
        prepared = self._verify_contribution_prestate(work_id, rollback_reference)
        artifact = self.contribution_store.put_text(text, media_type=media_type)
        ref = self.record_contribution(work_id, provider=provider, model=model, artifact_digest=artifact["sha256"], source_ref=source_ref, rollback_reference=prepared["rollback_reference"])
        return {"contribution_ref": ref, "artifact": artifact, "rollback_reference": prepared["rollback_reference"], "authority": "NON_AUTHORITATIVE_EVIDENCE", "work": self.get(work_id).to_dict()}

    def operator_inbox(self) -> list[WorkOrder]:
        return [w for w in self.orders() if w.status == WorkStatus.WAITING_OPERATOR]

    def approve(self, work_id: str, *, approval_ref: str) -> bool:
        order = self.get(work_id)
        if order.consequence_class != "D3" or order.status != WorkStatus.WAITING_OPERATOR:
            return False
        if not approval_ref:
            return False
        order.approval_ref = approval_ref
        order.status = WorkStatus.QUEUED
        order.updated_ms = self._now_ms()
        self.store.save_order(order, "OPERATOR_APPROVED")
        return True

    def _next_queued(self) -> WorkOrder | None:
        items = self.next_work(limit=1)
        return items[0] if items else None

    async def tick(self) -> WorkOrder | None:
        order = self._next_queued()
        if order is None:
            return None
        if order.consequence_class == "D3" and not order.approval_ref:
            order.status = WorkStatus.WAITING_OPERATOR
            order.updated_ms = self._now_ms()
            self.store.save_order(order, "OPERATOR_APPROVAL_REQUIRED")
            return order
        if order.consequence_class == "D4":
            order.status = WorkStatus.DENIED
            order.updated_ms = self._now_ms()
            self.store.save_order(order, "WORK_DENIED")
            return order
        order.status = WorkStatus.RUNNING
        order.attempts += 1
        order.updated_ms = self._now_ms()
        self.store.save_order(order, "WORK_DISPATCH_STARTED")
        try:
            results = list(await self.dispatcher(order.event_type, dict(order.payload)))
            if not results:
                order.status = WorkStatus.BLOCKED_AUTHORITY
                order.last_error = "NO_ADMITTED_DISPATCH_RESULT"
            elif all(bool(getattr(r, "is_valid", False)) for r in results):
                order.status = WorkStatus.EXECUTED
                refs: list[str] = list(order.contribution_refs)
                for r in results:
                    role = getattr(getattr(r, "role", None), "value", str(getattr(r, "role", "unknown")))
                    refs.append(f"agent:{role}:task:{getattr(r, 'task_id', order.work_id)}")
                order.contribution_refs = tuple(dict.fromkeys(refs))
                order.last_error = None
            else:
                order.status = WorkStatus.FAILED
                order.last_error = "INVALID_AGENT_RESULT"
        except Exception as exc:
            order.last_error = f"DISPATCH_ERROR:{type(exc).__name__}:{exc}"
            order.status = WorkStatus.QUEUED if order.attempts < order.max_attempts else WorkStatus.FAILED
        order.updated_ms = self._now_ms()
        self.store.save_order(order, "WORK_DISPATCH_RESULT")
        return order

    async def run_until_idle(self, *, max_ticks: int = 100) -> list[WorkOrder]:
        completed: list[WorkOrder] = []
        for _ in range(max_ticks):
            result = await self.tick()
            if result is None:
                break
            if result.status in TERMINAL:
                completed.append(result)
        return completed


def default_store_path() -> Path:
    return Path(os.environ.get("AEGIS_ORGANISM_STORE", ".aegis/runtime/organism.json"))


def main() -> None:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="AEGIS Ω durable organization organism")
    sub = parser.add_subparsers(dest="command", required=True)
    p_submit = sub.add_parser("submit")
    p_submit.add_argument("--id", required=True)
    p_submit.add_argument("--event", required=True)
    p_submit.add_argument("--payload", default="{}")
    p_submit.add_argument("--consequence", default="D1")
    p_next = sub.add_parser("next")
    p_next.add_argument("--limit", type=int, default=10)
    p_prepare = sub.add_parser("prepare-contribution")
    p_prepare.add_argument("--id", required=True)
    sub.add_parser("tick")
    p_run = sub.add_parser("run")
    p_run.add_argument("--max-ticks", type=int, default=100)
    sub.add_parser("inbox")
    p_approve = sub.add_parser("approve")
    p_approve.add_argument("--id", required=True)
    p_approve.add_argument("--approval-ref", required=True)
    p_contrib = sub.add_parser("contribute")
    p_contrib.add_argument("--id", required=True)
    p_contrib.add_argument("--provider", required=True)
    p_contrib.add_argument("--model", required=True)
    p_contrib.add_argument("--artifact-digest", required=True)
    p_contrib.add_argument("--source-ref", required=True)
    p_contrib.add_argument("--rollback-reference")
    sub.add_parser("contribute-json")
    sub.add_parser("status")
    args = parser.parse_args()
    org = OrganizationOrganism(OrganismStore(default_store_path()))
    if args.command == "submit":
        print(json.dumps(org.submit(args.id, args.event, json.loads(args.payload), consequence_class=args.consequence).to_dict(), sort_keys=True))
    elif args.command == "next":
        print(json.dumps([w.to_dict() for w in org.next_work(limit=args.limit)], sort_keys=True))
    elif args.command == "prepare-contribution":
        print(json.dumps(org.prepare_contribution(args.id), sort_keys=True))
    elif args.command == "tick":
        result = asyncio.run(org.tick())
        print(json.dumps(result.to_dict() if result else {"status": "IDLE"}, sort_keys=True))
    elif args.command == "run":
        print(json.dumps([w.to_dict() for w in asyncio.run(org.run_until_idle(max_ticks=args.max_ticks))], sort_keys=True))
    elif args.command == "inbox":
        print(json.dumps([w.to_dict() for w in org.operator_inbox()], sort_keys=True))
    elif args.command == "approve":
        print(json.dumps({"approved": org.approve(args.id, approval_ref=args.approval_ref)}, sort_keys=True))
    elif args.command == "contribute":
        ref = org.record_contribution(args.id, provider=args.provider, model=args.model, artifact_digest=args.artifact_digest, source_ref=args.source_ref, rollback_reference=args.rollback_reference)
        print(json.dumps({"contribution_ref": ref, "authority": "NON_AUTHORITATIVE_EVIDENCE", "work": org.get(args.id).to_dict()}, sort_keys=True))
    elif args.command == "contribute-json":
        body = json.loads(sys.stdin.read())
        result = org.contribute_text(body["work_id"], provider=body["provider"], model=body["model"], text=body["text"], source_ref=body["source_ref"], media_type=body.get("media_type", "text/markdown"), rollback_reference=body.get("rollback_reference"))
        print(json.dumps(result, sort_keys=True))
    elif args.command == "status":
        print(json.dumps({"orders": [w.to_dict() for w in org.orders()], "journal_length": len(org.store.journal()), "state_root": org.store.state_root()}, sort_keys=True))


if __name__ == "__main__":
    main()
