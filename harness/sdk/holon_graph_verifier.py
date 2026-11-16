"""Read-only, closed-world holon graph validation over the existing MHP-1 bridge.

This verifies topology and authenticated evidence references, NOT the truth of a
meaning, validity of a formal claim, the reviewer's competence, or authority to act.
It uses existing HolonSnapshotV1, HolonMeaningLensV1 and HolonMeaningVerifierV1.
"""
from __future__ import annotations

import hashlib
import heapq
from dataclasses import asdict, dataclass, field
from typing import Protocol

from harness.sdk.holon_meaning_bridge import (
    HolonMeaningLensV1,
    HolonMeaningReceiptV1,
    HolonMeaningVerifierV1,
    HolonSnapshotV1,
    TrustedArtifactBytesStore,
)
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash, require_hash

DOM_GRAPH_MANIFEST = "AEGIS_HOLON_GRAPH_MANIFEST_V1"
DOM_RESEARCH_SOURCE = "AEGIS_HOLON_RESEARCH_SOURCE_ATTESTATION_V1"
DOM_GRAPH_VERIFICATION = "AEGIS_HOLON_GRAPH_VERIFICATION_V1"
DOM_GRAPH_RECEIPT = "AEGIS_HOLON_GRAPH_RECEIPT_V1"

SCALE_ORDER = (
    "subatomic", "atomic", "molecular", "cellular", "organism", "field"
)
GROUNDING_TIERS = frozenset(("T0", "T1", "T2"))
ALL_TIERS = frozenset(("T0", "T1", "T2", "T3", "T4", "T5"))
MAX_HOLONS = 4096
MAX_EDGES = 32768
MAX_MEANING_RECEIPTS = 16384
MAX_SOURCE_REFERENCES = 16384
PASS = "PASS_STRUCTURAL_ONLY"
DENIED = "FAIL_HOLON_GRAPH_DENIED"


class HolonGraphError(ValueError):
    pass


def _id(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or not value.strip() or len(value) > 512:
        raise HolonGraphError(f"{name}:INVALID")
    return value


def _sha(name: str, value: object) -> str:
    try:
        require_hash(name, value)
    except (ValueError, TypeError) as exc:
        raise HolonGraphError(f"{name}:INVALID_SHA256") from exc
    return value


def _roots(name: str, roots: tuple[str, ...]) -> None:
    if not isinstance(roots, tuple):
        raise HolonGraphError(f"{name}:NOT_TUPLE")
    if len(roots) != len(set(roots)):
        raise HolonGraphError(f"{name}:DUPLICATE")
    for root in roots:
        _sha(name, root)


@dataclass(frozen=True)
class HolonGraphNodeRefV1:
    holon_id: str
    snapshot_root: str
    meaning_receipt_roots: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _id("holon_id", self.holon_id)
        _sha("snapshot_root", self.snapshot_root)
        _roots("meaning_receipt_roots", self.meaning_receipt_roots)


@dataclass(frozen=True)
class HolonGraphManifestV1:
    """Closed-world inventory. Its hash is an identity, NOT a verification proof."""

    nodes: tuple[HolonGraphNodeRefV1, ...]
    schema_version: str = field(default="aegis.holon-graph-manifest.v1", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.nodes, tuple) or not self.nodes:
            raise HolonGraphError("GRAPH_NODES_REQUIRED")
        if len(self.nodes) > MAX_HOLONS:
            raise HolonGraphError("GRAPH_TOO_LARGE")
        if any(not isinstance(n, HolonGraphNodeRefV1) for n in self.nodes):
            raise HolonGraphError("GRAPH_NODE_REF_INVALID")
        if len({n.holon_id for n in self.nodes}) != len(self.nodes):
            raise HolonGraphError("GRAPH_DUPLICATE_HOLON_ID")
        if sum(len(n.meaning_receipt_roots) for n in self.nodes) > MAX_MEANING_RECEIPTS:
            raise HolonGraphError("GRAPH_TOO_MANY_MEANINGS")

    @property
    def root(self) -> str:
        # Reorderings of the same set of graph nodes do not alter graph identity.
        return canonical_hash(DOM_GRAPH_MANIFEST, {
            "schema_version": self.schema_version,
            "nodes": [
                {
                    "holon_id": n.holon_id,
                    "snapshot_root": n.snapshot_root,
                    "meaning_receipt_roots": sorted(n.meaning_receipt_roots),
                }
                for n in sorted(self.nodes, key=lambda n: n.holon_id)
            ],
        })


@dataclass(frozen=True)
class ResearchSourceAttestationV1:
    """External research-document identity and separately reviewed tier claim.

    Construction of this record does NOT make it trusted. A trusted store must
    perform independent readback, and artifact bytes must match its digest.
    """

    document_id: str
    content_root: str
    reviewed_tier: str
    review_receipt_root: str
    verifier_root: str
    policy_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-research-source-attestation.v1", init=False)

    def __post_init__(self) -> None:
        _id("document_id", self.document_id)
        for key in ("content_root", "review_receipt_root", "verifier_root", "policy_root"):
            _sha(key, getattr(self, key))
        if self.reviewed_tier not in ALL_TIERS:
            raise HolonGraphError("SOURCE_REVIEW_TIER_INVALID")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_RESEARCH_SOURCE, asdict(self))


class TrustedHolonGraphManifestStore(Protocol):
    def fetch_verified(self, root: str) -> HolonGraphManifestV1 | None: ...


class TrustedHolonSnapshotStore(Protocol):
    def fetch_verified(self, root: str) -> HolonSnapshotV1 | None: ...


class TrustedResearchSourceStore(Protocol):
    def fetch_verified(self, document_id: str) -> ResearchSourceAttestationV1 | None: ...


class TrustedHolonMeaningLensStore(Protocol):
    def fetch_verified(self, root: str) -> HolonMeaningLensV1 | None: ...


class TrustedHolonMeaningReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> HolonMeaningReceiptV1 | None: ...


@dataclass(frozen=True)
class HolonGraphVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class HolonGraphReceiptV1:
    manifest_root: str
    verified_snapshot_roots: tuple[str, ...]
    verified_source_attestation_roots: tuple[str, ...]
    verified_meaning_receipt_roots: tuple[str, ...]
    node_count: int
    edge_count: int
    source_count: int
    meaning_receipt_count: int
    contextual_reading_count: int
    competing_reading_count: int
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-graph-receipt.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_GRAPH_RECEIPT, asdict(self))


class HolonGraphVerifierV1:
    """Fail-closed verifier of a bounded, complete, authenticated holon inventory.

    A structurally passing graph has not verified source-review competence,
    source claims, human interpretations, cross-lingual equivalence, or effect.
    """

    def __init__(
        self,
        *,
        manifests: TrustedHolonGraphManifestStore,
        snapshots: TrustedHolonSnapshotStore,
        sources: TrustedResearchSourceStore,
        artifacts: TrustedArtifactBytesStore,
        lenses: TrustedHolonMeaningLensStore,
        meaning_receipts: TrustedHolonMeaningReceiptStore,
        meaning_verifier: HolonMeaningVerifierV1,
    ) -> None:
        self.manifests = manifests
        self.snapshots = snapshots
        self.sources = sources
        self.artifacts = artifacts
        self.lenses = lenses
        self.meaning_receipts = meaning_receipts
        self.meaning_verifier = meaning_verifier

    def verify(self, manifest_root: str) -> tuple[HolonGraphVerificationV1, HolonGraphReceiptV1 | None]:
        def deny(code: str):
            return HolonGraphVerificationV1(DENIED, (code,), None), None

        try:
            _sha("manifest_root", manifest_root)
        except HolonGraphError:
            return deny("GRAPH_MANIFEST_ROOT_INVALID")
        manifest = self.manifests.fetch_verified(manifest_root)
        if not isinstance(manifest, HolonGraphManifestV1) or manifest.root != manifest_root:
            return deny("GRAPH_MANIFEST_UNTRUSTED")

        nodes: dict[str, HolonSnapshotV1] = {}
        ref_by_id = {ref.holon_id: ref for ref in manifest.nodes}
        for node_id in sorted(ref_by_id):
            ref = ref_by_id[node_id]
            node = self.snapshots.fetch_verified(ref.snapshot_root)
            if (not isinstance(node, HolonSnapshotV1)
                    or node.root != ref.snapshot_root or node.holon_id != node_id):
                return deny("GRAPH_SNAPSHOT_UNTRUSTED")
            nodes[node_id] = node

        edge_count = 0
        indegree = {node_id: 0 for node_id in nodes}
        children = {node_id: [] for node_id in nodes}
        # Both directions must be genuine references in the SAME closed world.
        for node_id in sorted(nodes):
            node = nodes[node_id]
            edge_count += len(node.part_of)
            if edge_count > MAX_EDGES:
                return deny("GRAPH_TOO_MANY_EDGES")
            for parent_id in sorted(node.part_of):
                parent = nodes.get(parent_id)
                if parent is None:
                    return deny("GRAPH_PARENT_UNRESOLVED")
                if node_id not in parent.composed_of:
                    return deny("GRAPH_PARENT_RECIPROCITY_MISSING")
                if SCALE_ORDER.index(parent.scale) < SCALE_ORDER.index(node.scale):
                    return deny("GRAPH_SCALE_INVERSION")
                children[parent_id].append(node_id)
                indegree[node_id] += 1
            for child_id in sorted(node.composed_of):
                child = nodes.get(child_id)
                if child is None:
                    return deny("GRAPH_CHILD_UNRESOLVED")
                if node_id not in child.part_of:
                    return deny("GRAPH_CHILD_RECIPROCITY_MISSING")

        # Iterative deterministic Kahn topological pass; no recursive DFS limit.
        ready = [node_id for node_id, n in indegree.items() if n == 0]
        heapq.heapify(ready)
        visited = 0
        while ready:
            parent_id = heapq.heappop(ready)
            visited += 1
            for child_id in sorted(children[parent_id]):
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    heapq.heappush(ready, child_id)
        if visited != len(nodes):
            return deny("GRAPH_CYCLE_DETECTED")

        # Research-doc identities are verified by independent stores; the
        # 'reviewed_tier' field is independently attested, not a proof of truth.
        doc_ids = sorted({doc_id for node in nodes.values() for doc_id in node.provenance})
        if len(doc_ids) > MAX_SOURCE_REFERENCES:
            return deny("GRAPH_TOO_MANY_SOURCES")
        source_receipts: dict[str, ResearchSourceAttestationV1] = {}
        for document_id in doc_ids:
            source = self.sources.fetch_verified(document_id)
            if (not isinstance(source, ResearchSourceAttestationV1)
                    or source.document_id != document_id or source.authority_class != NO_AUTHORITY):
                return deny("GRAPH_RESEARCH_SOURCE_UNTRUSTED")
            payload = self.artifacts.fetch_verified(source.content_root)
            if (not isinstance(payload, bytes) or not payload
                    or hashlib.sha256(payload).hexdigest() != source.content_root):
                return deny("GRAPH_RESEARCH_BYTES_UNTRUSTED")
            source_receipts[document_id] = source
        for node in nodes.values():
            if node.tier in GROUNDING_TIERS and not any(
                source_receipts[doc].reviewed_tier in GROUNDING_TIERS
                for doc in node.provenance
            ):
                return deny("GRAPH_HIGH_TIER_GROUNDING_ABSENT")

        verified_meanings = []
        contextual_readings = 0
        competing_readings = 0
        for node_id in sorted(ref_by_id):
            node = nodes[node_id]
            for meaning_root in sorted(ref_by_id[node_id].meaning_receipt_roots):
                previous = self.meaning_receipts.fetch_verified(meaning_root)
                if (not isinstance(previous, HolonMeaningReceiptV1)
                        or previous.root != meaning_root or previous.authority_class != NO_AUTHORITY
                        or previous.holon_root != node.root):
                    return deny("GRAPH_MEANING_RECEIPT_UNTRUSTED")
                lens = self.lenses.fetch_verified(previous.lens_root)
                if (not isinstance(lens, HolonMeaningLensV1)
                        or lens.root != previous.lens_root
                        or lens.holon.root != node.root):
                    return deny("GRAPH_MEANING_LENS_UNTRUSTED")
                result, verified = self.meaning_verifier.verify(lens)
                if (result.status != "PASS" or verified is None
                        or verified != previous or verified.root != meaning_root):
                    return deny("GRAPH_MEANING_VERIFICATION_FAILED")
                verified_meanings.append(meaning_root)
                contextual_readings += len(lens.readings)
                competing_readings += max(0, len(lens.readings) - 1)

        snapshot_roots = tuple(sorted(ref.snapshot_root for ref in manifest.nodes))
        source_roots = tuple(sorted(src.root for src in source_receipts.values()))
        meaning_roots = tuple(sorted(verified_meanings))
        verification_root = canonical_hash(DOM_GRAPH_VERIFICATION, {
            "manifest_root": manifest_root,
            "verified_snapshot_roots": snapshot_roots,
            "verified_source_attestation_roots": source_roots,
            "verified_meaning_receipt_roots": meaning_roots,
            "node_count": len(nodes),
            "edge_count": edge_count,
            "source_count": len(source_roots),
            "meaning_receipt_count": len(meaning_roots),
            "contextual_reading_count": contextual_readings,
            "competing_reading_count": competing_readings,
            "status": PASS,
        })
        receipt = HolonGraphReceiptV1(
            manifest_root, snapshot_roots, source_roots, meaning_roots,
            len(nodes), edge_count, len(source_roots), len(meaning_roots),
            contextual_readings, competing_readings, verification_root,
        )
        return HolonGraphVerificationV1(PASS, (), verification_root), receipt
