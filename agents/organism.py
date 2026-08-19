"""Durable, fail-closed organizational work loop for AEGIS Ω.

This module is intentionally small: it turns the existing governed coordinator
into a persistent company loop. It does not grant new authority. D1/D2 work may
enter the existing Automaton-3-gated dispatcher; D3 waits for explicit operator
approval; D4 is denied. State is persisted with a hash-chained journal so a
restart cannot silently forget or rewrite prior work.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable


GENESIS = "0" * 64
STORE_VERSION = "AEGIS_ORGANISM_STORE_V1"
JOURNAL_DOMAIN = "AEGIS_ORGANISM_JOURNAL_V1"


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


class OrganismStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.exists():
            self._state = json.loads(self.path.read_text(encoding="utf-8"))
            self._validate()
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

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(self._state, sort_keys=True, indent=2, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _append(self, event_type: str, body: dict[str, Any]) -> None:
        journal = self._state["journal"]
        prev = journal[-1]["event_hash"] if journal else GENESIS
        seq = len(journal)
        event_hash = _hash_event(prev, seq, event_type, body)
        journal.append({"seq": seq, "event_type": event_type, "body": body, "prev_hash": prev, "event_hash": event_hash})

    def save_order(self, order: WorkOrder, event_type: str) -> None:
        body = order.to_dict()
        self._state["orders"][order.work_id] = body
        self._append(event_type, body)
        self._persist()

    def get(self, work_id: str) -> WorkOrder | None:
        raw = self._state["orders"].get(work_id)
        return WorkOrder.from_dict(raw) if raw else None

    def orders(self) -> list[WorkOrder]:
        return [WorkOrder.from_dict(x) for x in self._state["orders"].values()]

    def journal(self) -> list[dict[str, Any]]:
        return list(self._state["journal"])


class OrganizationOrganism:
    def __init__(self, store: OrganismStore, dispatcher: Dispatcher | None = None):
        self.store = store
        self.dispatcher = dispatcher or self._default_dispatcher

    @staticmethod
    async def _default_dispatcher(event_type: str, payload: dict[str, Any]):
        from agents.coordinator import dispatch_event
        return await dispatch_event(event_type, payload)

    def orders(self) -> list[WorkOrder]:
        return sorted(self.store.orders(), key=lambda w: (w.created_ms, w.work_id))

    def get(self, work_id: str) -> WorkOrder:
        order = self.store.get(work_id)
        if order is None:
            raise KeyError(work_id)
        return order

    def submit(
        self,
        work_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        consequence_class: str,
        max_attempts: int = 3,
    ) -> WorkOrder:
        existing = self.store.get(work_id)
        if existing is not None:
            return existing
        if not work_id or not event_type:
            raise ValueError("WORK_ID_AND_EVENT_REQUIRED")
        if max_attempts < 1:
            raise ValueError("MAX_ATTEMPTS_INVALID")
        cc = consequence_class.upper()
        now = int(time.time() * 1000)
        if cc in {"D0", "D1", "D2"}:
            status = WorkStatus.QUEUED
        elif cc == "D3":
            status = WorkStatus.WAITING_OPERATOR
        else:
            status = WorkStatus.DENIED
        order = WorkOrder(work_id, event_type, dict(payload), cc, status, max_attempts=max_attempts, created_ms=now, updated_ms=now)
        self.store.save_order(order, "WORK_SUBMITTED")
        return order

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
        order.updated_ms = int(time.time() * 1000)
        self.store.save_order(order, "OPERATOR_APPROVED")
        return True

    def _next_queued(self) -> WorkOrder | None:
        for order in self.orders():
            if order.status == WorkStatus.QUEUED:
                return order
        return None

    async def tick(self) -> WorkOrder | None:
        order = self._next_queued()
        if order is None:
            return None
        if order.consequence_class == "D3" and not order.approval_ref:
            order.status = WorkStatus.WAITING_OPERATOR
            order.updated_ms = int(time.time() * 1000)
            self.store.save_order(order, "OPERATOR_APPROVAL_REQUIRED")
            return order
        if order.consequence_class == "D4":
            order.status = WorkStatus.DENIED
            order.updated_ms = int(time.time() * 1000)
            self.store.save_order(order, "WORK_DENIED")
            return order

        order.status = WorkStatus.RUNNING
        order.attempts += 1
        order.updated_ms = int(time.time() * 1000)
        self.store.save_order(order, "WORK_DISPATCH_STARTED")
        try:
            results = list(await self.dispatcher(order.event_type, dict(order.payload)))
            if not results:
                order.status = WorkStatus.BLOCKED_AUTHORITY
                order.last_error = "NO_ADMITTED_DISPATCH_RESULT"
            elif all(bool(getattr(r, "is_valid", False)) for r in results):
                order.status = WorkStatus.EXECUTED
                refs: list[str] = []
                for r in results:
                    role = getattr(getattr(r, "role", None), "value", str(getattr(r, "role", "unknown")))
                    refs.append(f"agent:{role}:task:{getattr(r, 'task_id', order.work_id)}")
                order.contribution_refs = tuple(refs)
                order.last_error = None
            else:
                order.status = WorkStatus.FAILED
                order.last_error = "INVALID_AGENT_RESULT"
        except Exception as exc:  # fail closed; bounded retry below
            order.last_error = f"DISPATCH_ERROR:{type(exc).__name__}:{exc}"
            order.status = WorkStatus.QUEUED if order.attempts < order.max_attempts else WorkStatus.FAILED

        order.updated_ms = int(time.time() * 1000)
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
    parser = argparse.ArgumentParser(description="AEGIS Ω durable organization organism")
    sub = parser.add_subparsers(dest="command", required=True)
    p_submit = sub.add_parser("submit")
    p_submit.add_argument("--id", required=True)
    p_submit.add_argument("--event", required=True)
    p_submit.add_argument("--payload", default="{}")
    p_submit.add_argument("--consequence", default="D1")
    p_tick = sub.add_parser("tick")
    p_run = sub.add_parser("run")
    p_run.add_argument("--max-ticks", type=int, default=100)
    p_inbox = sub.add_parser("inbox")
    p_approve = sub.add_parser("approve")
    p_approve.add_argument("--id", required=True)
    p_approve.add_argument("--approval-ref", required=True)
    sub.add_parser("status")
    args = parser.parse_args()

    org = OrganizationOrganism(OrganismStore(default_store_path()))
    if args.command == "submit":
        print(json.dumps(org.submit(args.id, args.event, json.loads(args.payload), consequence_class=args.consequence).to_dict(), sort_keys=True))
    elif args.command == "tick":
        result = asyncio.run(org.tick())
        print(json.dumps(result.to_dict() if result else {"status": "IDLE"}, sort_keys=True))
    elif args.command == "run":
        print(json.dumps([w.to_dict() for w in asyncio.run(org.run_until_idle(max_ticks=args.max_ticks))], sort_keys=True))
    elif args.command == "inbox":
        print(json.dumps([w.to_dict() for w in org.operator_inbox()], sort_keys=True))
    elif args.command == "approve":
        print(json.dumps({"approved": org.approve(args.id, approval_ref=args.approval_ref)}, sort_keys=True))
    elif args.command == "status":
        print(json.dumps({"orders": [w.to_dict() for w in org.orders()], "journal_length": len(org.store.journal())}, sort_keys=True))


if __name__ == "__main__":
    main()
