"""Cross-domain evidence-bound information mesh for EXISTING AEGIS roles.

No model calls, payments, authority decisions, agent invocations, or network.
Informational bridge between existing cognitive, revenue, formal, security,
engineering and operational lanes. Untrusted text always remains inert data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from agents.dendrite_mesh import (
    DendriteEvent, DendriteMesh, DendriteNode, MAX_EVENTS,
    MAX_TEXT_BYTES, SCHEMA, digest, DIGEST_RE, HEAD_RE, NAME_RE,
)

TOPICS = frozenset({"research", "formal", "engineering", "security", "commerce", "operations"})
SOURCES = frozenset({"cognitive", "revenue", "formal", "security", "engineering", "operations"})
_SOURCE_TOPIC = {
    "cognitive": "research", "revenue": "commerce", "formal": "formal",
    "security": "security", "engineering": "engineering", "operations": "operations",
}
_SOURCE_ROLE = {
    "cognitive": "corpus_ingestor", "revenue": "strategy", "formal": "applied_science",
    "security": "cybersecurity", "engineering": "engineering",
    "operations": "platform_engineering",
}


def system_mesh() -> DendriteMesh:
    """Role names originate in existing agents.yaml; edges confer no authority."""
    capabilities = {
        "corpus_ingestor": {"research"},
        "batch_processor": {"research", "formal"},
        "applied_science": {"research", "formal"},
        "ai_research": {"research", "formal", "engineering"},
        "cybersecurity": set(TOPICS),
        "ai_safety": {"research", "formal", "engineering", "security"},
        "chronologist": set(TOPICS),
        "engineering": {"engineering", "formal", "security"},
        "platform_engineering": {"engineering", "operations", "security"},
        "devex": {"engineering", "formal"},
        "data_governance": {"research", "formal", "security"},
        "strategy": {"research", "commerce"},
        "product_management": {"research", "engineering", "commerce"},
        "finance": {"commerce"},
        "biz_dev": {"commerce"},
        "sales": {"commerce"},
        "solutions_engineering": {"engineering", "commerce"},
        "customer_success": {"commerce"},
        "compliance": {"security", "formal", "commerce"},
    }
    quarantine_roles = {"cybersecurity", "ai_safety", "chronologist", "data_governance", "corpus_ingestor"}
    nodes = {
        n: DendriteNode(n, frozenset(t), frozenset({"CANDIDATE", "QUARANTINE"})
                        if n in quarantine_roles else frozenset({"CANDIDATE"}))
        for n, t in capabilities.items()
    }
    edges = {
        "corpus_ingestor": ("batch_processor", "applied_science", "cybersecurity", "data_governance"),
        "batch_processor": ("ai_research", "chronologist", "product_management"),
        "applied_science": ("ai_research", "engineering", "chronologist"),
        "ai_research": ("chronologist", "product_management", "devex"),
        "cybersecurity": ("ai_safety", "chronologist", "compliance", "engineering"),
        "ai_safety": ("chronologist", "data_governance"),
        "chronologist": ("corpus_ingestor",),
        "engineering": ("devex", "platform_engineering", "cybersecurity", "product_management"),
        "platform_engineering": ("chronologist", "cybersecurity", "solutions_engineering"),
        "devex": ("chronologist",),
        "data_governance": ("chronologist",),
        "strategy": ("product_management", "biz_dev", "compliance", "cybersecurity"),
        "product_management": ("solutions_engineering", "finance", "sales", "strategy", "chronologist"),
        "finance": ("chronologist",),
        "biz_dev": ("sales",),
        "sales": ("customer_success", "solutions_engineering"),
        "solutions_engineering": ("chronologist",),
        "customer_success": ("chronologist",),
        "compliance": ("chronologist",),
    }
    return DendriteMesh(nodes, edges)


@dataclass(frozen=True)
class EvidencePacket:
    """Source-bound informational record; never a verified fact or authority token."""
    source: str
    topic: str
    origin: str
    source_head: str
    source_record: str
    sequence: int
    text: str
    channel: str = "CANDIDATE"

    def event(self) -> DendriteEvent:
        if not isinstance(self.source, str) or self.source not in SOURCES or self.topic != _SOURCE_TOPIC[self.source]:
            raise ValueError("SOURCE_TOPIC_MISMATCH")
        expected_origin = ("cybersecurity" if self.channel == "QUARANTINE"
                           and self.source != "cognitive" else _SOURCE_ROLE[self.source])
        if self.origin != expected_origin:
            raise ValueError("SOURCE_ROLE_MISMATCH")
        return DendriteEvent.create(
            origin=self.origin, topic=self.topic, channel=self.channel,
            source_head=self.source_head, source_record=self.source_record,
            sequence=self.sequence, text=self.text,
        )


def spread_packets(packets: list[EvidencePacket], *, ttl: int = 5) -> dict[str, Any]:
    if not isinstance(packets, list) or not 0 < len(packets) <= MAX_EVENTS:
        raise ValueError("INVALID_PACKET_BATCH")
    mesh = system_mesh()
    routed = [mesh.propagate(pkt.event(), ttl=ttl) for pkt in packets]
    hashes = [r["event_hash"] for r in routed]
    if len(set(hashes)) != len(hashes):
        raise ValueError("DUPLICATE_EVENT_IN_BATCH")
    body = {
        "schema": "AEGIS_DENDRITE_SYSTEM_V1", "parent_schema": SCHEMA,
        "authority_effect": "NONE", "execution_effect": "NONE",
        "source_authenticity": "NOT_VERIFIED",
        "delivery_kind": "IN_MEMORY_READ_ONLY",
        "events": routed, "ingress_sources": [p.source for p in packets],
    }
    return {**body, "receipt_hash": digest(body)}


def from_revenue_cycle(cycle: Any, *, source_head: str, ttl: int = 5) -> dict[str, Any]:
    """Consume RevenueCycleResult artifacts; a projection is never realized revenue.

    The caller must separately authenticate source_head and lineage_root.
    """
    if not getattr(cycle, "chain_valid", False):
        raise ValueError("REVENUE_LINEAGE_INVALID")
    root = getattr(cycle, "lineage_terminal_hash", "")
    if not isinstance(root, str) or not DIGEST_RE.fullmatch(root):
        raise ValueError("REVENUE_LINEAGE_ROOT_MISSING")
    if not isinstance(source_head, str) or not HEAD_RE.fullmatch(source_head):
        raise ValueError("INVALID_SOURCE_HEAD")
    artifacts = getattr(cycle, "artifacts", None)
    if not isinstance(artifacts, list) or not 0 < len(artifacts) <= MAX_EVENTS:
        raise ValueError("INVALID_REVENUE_ARTIFACTS")
    packets = []
    sequences = set()
    for art in artifacts:
        seq = getattr(art, "sequence", None)
        role = getattr(art, "role", None)
        output = getattr(art, "output", None)
        envelope_id = getattr(art, "envelope_id", None)
        if type(seq) is not int or seq < 0 or seq in sequences:
            raise ValueError("INVALID_REVENUE_SEQUENCE")
        sequences.add(seq)
        if not isinstance(role, str) or not NAME_RE.fullmatch(role):
            raise ValueError("INVALID_REVENUE_ROLE")
        if not isinstance(output, str) or not output.strip() or len(output.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("INVALID_REVENUE_TEXT")
        if not isinstance(envelope_id, str) or not envelope_id.strip() or len(envelope_id) > 200:
            raise ValueError("INVALID_REVENUE_ENVELOPE")
        source_record = digest({"role": role, "sequence": seq, "text": output,
                                "envelope_id": envelope_id, "lineage_root": root})
        packets.append(EvidencePacket("revenue", "commerce", "strategy",
                                      source_head, source_record, seq,
                                      f"[{role}] {output}"))
    receipt = spread_packets(packets, ttl=ttl)
    return {**receipt, "revenue_lineage_root": root,
            "result_root": digest({"mesh": receipt["receipt_hash"], "lineage_root": root})}


def from_source_record(record: Mapping[str, Any], *, ttl: int = 5) -> dict[str, Any]:
    """Strict offline ingress for formal/security/engineering/operations receipts."""
    if not isinstance(record, Mapping):
        raise ValueError("INVALID_SOURCE_RECORD")
    required = {"source", "source_head", "source_record", "sequence", "text", "channel"}
    if set(record) != required:
        raise ValueError("SOURCE_RECORD_FIELDS_INVALID")
    source = record["source"]
    if not isinstance(source, str) or source not in {"formal", "security", "engineering", "operations"}:
        raise ValueError("SOURCE_NOT_EXTERNAL")
    packet = EvidencePacket(
        source=source, topic=_SOURCE_TOPIC[source],
        origin="cybersecurity" if record["channel"] == "QUARANTINE" else _SOURCE_ROLE[source],
        source_head=record["source_head"], source_record=record["source_record"],
        sequence=record["sequence"], text=record["text"], channel=record["channel"],
    )
    return spread_packets([packet], ttl=ttl)


def from_cognitive_pipeline(pipeline: Any, *, source_head: str, ttl: int = 5) -> dict[str, Any]:
    """Connect existing KAN arbitration; heuristic acceptance is NOT verified truth."""
    if not getattr(pipeline, "chain_valid", False):
        raise ValueError("COGNITIVE_CHAIN_INVALID")
    root = getattr(pipeline, "kan_terminal_hash", "")
    if not isinstance(root, str) or not DIGEST_RE.fullmatch(root):
        raise ValueError("COGNITIVE_ROOT_INVALID")
    values = getattr(pipeline, "arbitration", None)
    if not isinstance(values, list) or not 0 < len(values) <= MAX_EVENTS:
        raise ValueError("COGNITIVE_ITEMS_INVALID")
    packets = []
    for v in values:
        if not isinstance(v, Mapping) or type(v.get("admitted")) is not bool:
            raise ValueError("COGNITIVE_ITEM_INVALID")
        record = v.get("record_hash")
        if not isinstance(record, str) or not DIGEST_RE.fullmatch(record):
            raise ValueError("COGNITIVE_RECORD_INVALID")
        packets.append(EvidencePacket(
            "cognitive", "research", "corpus_ingestor", source_head,
            record, v.get("sequence"), v.get("claim"),
            "CANDIDATE" if v["admitted"] else "QUARANTINE",
        ))
    receipt = spread_packets(packets, ttl=ttl)
    return {**receipt, "cognitive_root": root,
            "result_root": digest({"mesh": receipt["receipt_hash"], "cognitive_root": root})}


def main() -> None:
    """Replay one bounded source record locally; no network or dispatch."""
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="AEGIS cross-domain dendritic replay (read-only)")
    parser.add_argument("record", type=Path, help="JSON source information record")
    parser.add_argument("--ttl", type=int, default=5)
    args = parser.parse_args()
    with args.record.open("rb") as handle:
        raw = handle.read(8193)
    if len(raw) > 8192:
        parser.error("record exceeds 8192 bytes")
    try:
        obj = json.loads(raw)
        result = from_source_record(obj, ttl=args.ttl)
    except (ValueError, TypeError, UnicodeError) as exc:
        parser.error(f"invalid information receipt: {type(exc).__name__}: {exc}")
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
