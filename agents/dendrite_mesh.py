"""AEGIS dendrite mesh: deterministic, read-only propagation of epistemic events.

A topic-scoped informational overlay, NOT an authority or execution router.
It deliberately reuses the existing Gossip Router's TTL/dedup/fan-out invariants
without replacing the Rust telemetry router or Automaton-3 authorization.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from dataclasses import dataclass
from typing import Any, Mapping

SCHEMA = "AEGIS_DENDRITE_MESH_V1"
CHANNELS = frozenset({"CANDIDATE", "QUARANTINE"})
HEAD_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
MAX_HOPS = 8
MAX_NODES = 32
MAX_FANOUT = 8
MAX_EVENTS = 64
MAX_TEXT_BYTES = 4096


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class DendriteEvent:
    origin: str
    topic: str
    channel: str
    source_head: str
    source_record: str
    sequence: int
    text: str
    event_hash: str
    schema: str = SCHEMA

    def payload(self) -> dict[str, Any]:
        return {"schema": self.schema, "origin": self.origin, "topic": self.topic,
                "channel": self.channel, "source_head": self.source_head,
                "source_record": self.source_record, "sequence": self.sequence,
                "text": self.text, "authority_effect": "NONE",
                "epistemic_status": "UNVERIFIED_SOURCE_CLAIM"}

    def validate(self) -> None:
        if self.schema != SCHEMA or not NAME_RE.fullmatch(self.origin):
            raise ValueError("INVALID_ORIGIN_OR_SCHEMA")
        if not NAME_RE.fullmatch(self.topic) or self.channel not in CHANNELS:
            raise ValueError("INVALID_TOPIC_OR_CHANNEL")
        if not HEAD_RE.fullmatch(self.source_head):
            raise ValueError("INVALID_SOURCE_HEAD")
        if not DIGEST_RE.fullmatch(self.source_record):
            raise ValueError("INVALID_SOURCE_RECORD")
        if type(self.sequence) is not int or not 0 <= self.sequence < (1 << 63):
            raise ValueError("INVALID_SEQUENCE")
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("INVALID_TEXT_SIZE")
        if not DIGEST_RE.fullmatch(self.event_hash) or self.event_hash != digest(self.payload()):
            raise ValueError("EVENT_DIGEST_MISMATCH")

    @classmethod
    def create(cls, *, origin: str, topic: str, channel: str,
               source_head: str, source_record: str, sequence: int,
               text: str) -> "DendriteEvent":
        provisional = cls(origin, topic, channel, source_head, source_record,
                          sequence, text, "0" * 64)
        event = cls(origin, topic, channel, source_head, source_record,
                    sequence, text, digest(provisional.payload()))
        event.validate()
        return event


@dataclass(frozen=True)
class DendriteNode:
    name: str
    topics: frozenset[str]
    channels: frozenset[str]

    def accepts(self, event: DendriteEvent) -> bool:
        return event.topic in self.topics and event.channel in self.channels


class DendriteMesh:
    """Deterministic BFS across declared dendrites; ZERO dispatch and ZERO I/O."""

    def __init__(self, nodes: Mapping[str, DendriteNode],
                 links: Mapping[str, tuple[str, ...]]) -> None:
        if not nodes or len(nodes) > MAX_NODES:
            raise ValueError("INVALID_MESH_SIZE")
        self.nodes = dict(nodes)
        self.links: dict[str, tuple[str, ...]] = {}
        for name, node in nodes.items():
            if name != node.name or not NAME_RE.fullmatch(name):
                raise ValueError("INVALID_NODE_NAME")
            if not node.topics or not all(NAME_RE.fullmatch(t) for t in node.topics):
                raise ValueError("INVALID_SUBSCRIPTIONS")
            if not node.channels or not node.channels <= CHANNELS:
                raise ValueError("INVALID_CHANNELS")
        if set(links) - set(nodes):
            raise ValueError("UNKNOWN_SOURCE_NODE")
        for name in sorted(nodes):
            peers = tuple(links.get(name, ()))
            if len(peers) > MAX_FANOUT or len(set(peers)) != len(peers):
                raise ValueError("INVALID_FANOUT")
            if any(p not in nodes for p in peers):
                raise ValueError("UNKNOWN_TARGET_NODE")
            self.links[name] = tuple(sorted(peers))

    def propagate(self, event: DendriteEvent, *, ttl: int = 4) -> dict[str, Any]:
        event.validate()
        if type(ttl) is not int or not 0 <= ttl <= MAX_HOPS:
            raise ValueError("INVALID_TTL")
        if event.origin not in self.nodes:
            raise ValueError("UNKNOWN_EVENT_ORIGIN")
        if not self.nodes[event.origin].accepts(event):
            raise ValueError("ORIGIN_NOT_SUBSCRIBED")
        visited: set[str] = set()
        routes: list[dict[str, Any]] = []
        deliveries: list[str] = []
        queue = deque([(event.origin, None, 0)])
        while queue:
            at, parent, hops = queue.popleft()
            if at in visited:
                routes.append({"from": parent, "to": at, "hop": hops,
                               "result": "DUPLICATE"})
                continue
            node = self.nodes[at]
            if not node.accepts(event):
                routes.append({"from": parent, "to": at, "hop": hops,
                               "result": "NOT_SUBSCRIBED"})
                continue
            visited.add(at)
            deliveries.append(at)
            routes.append({"from": parent, "to": at, "hop": hops,
                           "result": "OBSERVED"})
            if hops >= ttl:
                continue
            for peer in self.links[at]:
                queue.append((peer, at, hops + 1))
        body: dict[str, Any] = {
            "schema": SCHEMA, "event_hash": event.event_hash,
            "source_head": event.source_head, "source_record": event.source_record,
            "authority_effect": "NONE", "execution_effect": "NONE",
            "epistemic_status": "UNVERIFIED_SOURCE_CLAIM",
            "ttl": ttl, "delivered_roles": deliveries, "routes": routes,
        }
        return {**body, "receipt_hash": digest(body)}


def default_mesh() -> DendriteMesh:
    """Existing AEGIS agent role names, with read-only knowledge handoffs."""
    names = ("corpus_ingestor", "batch_processor", "applied_science",
             "cybersecurity", "chronologist", "ai_research",
             "product_management", "strategy", "finance")
    nodes = {
        name: DendriteNode(name, frozenset({"research"}),
                           frozenset({"CANDIDATE", "QUARANTINE"})
                           if name in {"corpus_ingestor", "cybersecurity", "chronologist"}
                           else frozenset({"CANDIDATE"}))
        for name in names
    }
    return DendriteMesh(nodes, {
        "corpus_ingestor": ("batch_processor", "applied_science", "cybersecurity"),
        "batch_processor": ("chronologist", "product_management"),
        "applied_science": ("chronologist", "ai_research"),
        "cybersecurity": ("chronologist",),
        "ai_research": ("chronologist",),
        "product_management": ("strategy",),
        "strategy": ("finance",),
        "finance": ("chronologist",),
        "chronologist": ("corpus_ingestor",),
    })


def propagate_pipeline(result: Any, *, source_head: str,
                       ttl: int = 4) -> dict[str, Any]:
    """Bridge existing cognitive_pipeline results to mesh; NO agent execution.

    'admitted' by the deterministic KAN scorer is NOT independently verified truth.
    Every exported claim remains UNVERIFIED_SOURCE_CLAIM.
    """
    if not getattr(result, "chain_valid", False):
        raise ValueError("PIPELINE_CHAIN_INVALID")
    if not DIGEST_RE.fullmatch(getattr(result, "kan_terminal_hash", "")):
        raise ValueError("PIPELINE_ROOT_INVALID")
    claims = result.arbitration
    if len(claims) > MAX_EVENTS:
        raise ValueError("TOO_MANY_EVENTS")
    mesh = default_mesh()
    events = []
    for v in claims:
        if not isinstance(v, dict) or type(v.get("admitted")) is not bool:
            raise ValueError("INVALID_PIPELINE_VERDICT")
        if not DIGEST_RE.fullmatch(v.get("record_hash", "")):
            raise ValueError("INVALID_RECORD_HASH")
        event = DendriteEvent.create(
            origin="corpus_ingestor", topic="research",
            channel="CANDIDATE" if v["admitted"] else "QUARANTINE",
            source_head=source_head, source_record=v["record_hash"],
            sequence=v["sequence"], text=v["claim"])
        events.append(mesh.propagate(event, ttl=ttl))
    body = {"schema": SCHEMA, "pipeline_root": result.kan_terminal_hash,
            "source_head": source_head, "epistemic_status": "UNVERIFIED_SOURCE_CLAIMS",
            "authority_effect": "NONE", "execution_effect": "NONE", "events": events}
    return {**body, "receipt_hash": digest(body)}
