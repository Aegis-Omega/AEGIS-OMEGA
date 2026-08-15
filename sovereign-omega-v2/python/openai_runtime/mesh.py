from __future__ import annotations

from collections import deque
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .chain import stable_local_digest
from .types import ChainLayer, OmegaRunResult, RunStatus


class MeshAdmissionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class CollectiveNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    kind: Literal["model", "human", "connector", "runtime", "sensor"]
    provider: str = Field(min_length=1)
    model: str | None = None
    role: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    failure_domain: str = Field(min_length=1)
    identity_root: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("capabilities")
    @classmethod
    def _normalize_caps(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class HyphalEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    allowed_capabilities: list[str] = Field(default_factory=list)
    requires_evidence: bool = True

    @field_validator("allowed_capabilities")
    @classmethod
    def _normalize_caps(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class RoutedEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    route: list[str] = Field(min_length=1)
    requested_capabilities: list[str]
    capabilities: list[str]
    route_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class NodeObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    failure_domain: str
    model: str
    execution_id: str
    chain_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    witness_digests: list[str] = Field(min_length=1)
    evidence_digests: list[str] = Field(default_factory=list)
    trace_id: str | None = None
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("witness_digests")
    @classmethod
    def _validate_witnesses(cls, value: list[str]) -> list[str]:
        for digest in value:
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("witness digests must be lowercase SHA-256")
        return sorted(set(value))


class CollectiveAdmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admitted: bool
    identity_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    mesh_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    independent_failure_domains: int = Field(ge=0)
    admitted_node_ids: list[str] = Field(default_factory=list)
    obstruction_codes: list[str] = Field(default_factory=list)
    observation_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class MycorrhizalMesh:
    """Distributed cognition graph with conserved identity and contractive authority.

    This is a systems architecture inspired by mycorrhizal networks. It does not
    claim biological equivalence. Identity is a mesh invariant, while execution
    authority can only contract along a route.
    """

    def __init__(self, identity_root: str):
        if len(identity_root) != 64 or any(ch not in "0123456789abcdef" for ch in identity_root):
            raise ValueError("identity_root must be lowercase SHA-256")
        self.identity_root = identity_root
        self._nodes: dict[str, CollectiveNode] = {}
        self._edges: dict[tuple[str, str], HyphalEdge] = {}

    def add_node(self, node: CollectiveNode) -> None:
        if node.identity_root != self.identity_root:
            raise MeshAdmissionError(
                "MESH_IDENTITY_MISMATCH",
                f"node {node.node_id} does not share the conserved identity root",
            )
        existing = self._nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise MeshAdmissionError("MESH_EDGE_INVALID", f"node id already bound: {node.node_id}")
        self._nodes[node.node_id] = node

    def add_edge(self, edge: HyphalEdge) -> None:
        if edge.source == edge.target:
            raise MeshAdmissionError("MESH_EDGE_INVALID", "self edges are not admitted")
        source = self._nodes.get(edge.source)
        target = self._nodes.get(edge.target)
        if source is None or target is None:
            raise MeshAdmissionError("MESH_NODE_NOT_REGISTERED", "edge endpoints must be registered")
        effective = set(source.capabilities) & set(target.capabilities)
        advertised = set(edge.allowed_capabilities)
        if not advertised.issubset(effective):
            raise MeshAdmissionError(
                "MESH_EDGE_INVALID",
                "edge cannot advertise capabilities absent from either endpoint",
            )
        self._edges[(edge.source, edge.target)] = edge

    def mesh_root_digest(self) -> str:
        nodes = [self._nodes[key].model_dump(mode="json") for key in sorted(self._nodes)]
        edges = [self._edges[key].model_dump(mode="json") for key in sorted(self._edges)]
        return stable_local_digest(
            {"identity_root": self.identity_root, "nodes": nodes, "edges": edges}
        )

    def _find_route(self, source: str, target: str) -> list[str]:
        if source not in self._nodes or target not in self._nodes:
            raise MeshAdmissionError("MESH_NODE_NOT_REGISTERED", "route endpoints must be registered")
        queue: deque[tuple[str, list[str]]] = deque([(source, [source])])
        seen = {source}
        while queue:
            current, path = queue.popleft()
            if current == target:
                return path
            neighbors = sorted(
                edge.target
                for (src, _), edge in self._edges.items()
                if src == current
            )
            for neighbor in neighbors:
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
        raise MeshAdmissionError("MESH_ROUTE_NOT_FOUND", f"no route {source}->{target}")

    def route(self, source: str, target: str, requested_capabilities: list[str]) -> RoutedEnvelope:
        requested = sorted({cap.strip() for cap in requested_capabilities if cap.strip()})
        route = self._find_route(source, target)
        effective = set(requested) & set(self._nodes[source].capabilities)
        for left, right in zip(route, route[1:]):
            edge = self._edges[(left, right)]
            effective &= set(edge.allowed_capabilities)
            effective &= set(self._nodes[right].capabilities)
        if not set(requested).issubset(effective):
            raise MeshAdmissionError(
                "MESH_AUTHORITY_CONTRACTED",
                "requested authority does not survive the complete route",
            )
        route_payload = {
            "identity_root": self.identity_root,
            "route": route,
            "requested_capabilities": requested,
            "capabilities": sorted(effective),
            "mesh_root_digest": self.mesh_root_digest(),
        }
        return RoutedEnvelope(
            identity_root=self.identity_root,
            route=route,
            requested_capabilities=requested,
            capabilities=sorted(effective),
            route_digest=stable_local_digest(route_payload),
        )

    def observation_from_run(self, node_id: str, run: OmegaRunResult) -> NodeObservation:
        node = self._nodes.get(node_id)
        if node is None:
            raise MeshAdmissionError("MESH_NODE_NOT_REGISTERED", f"unknown node: {node_id}")
        if run.status != RunStatus.SUCCEEDED or run.final_output is None:
            raise MeshAdmissionError("COLLECTIVE_RUN_NOT_ADMITTED", "only successful runs may enter the mesh")
        layers = [receipt.layer for receipt in run.chain if receipt.admitted]
        if tuple(layers) != tuple(ChainLayer):
            raise MeshAdmissionError(
                "COLLECTIVE_RUN_NOT_ADMITTED",
                "run must carry a complete admitted L0-L7 chain",
            )
        if not run.chain_root_digest:
            raise MeshAdmissionError("COLLECTIVE_WITNESS_MISSING", "chain root digest is required")
        witnesses = sorted({run.chain_root_digest, *run.evidence_digests})
        return NodeObservation(
            node_id=node_id,
            failure_domain=node.failure_domain,
            model=run.model,
            execution_id=run.execution_id,
            chain_root_digest=run.chain_root_digest,
            witness_digests=witnesses,
            evidence_digests=sorted(set(run.evidence_digests)),
            trace_id=run.trace_id,
            output_digest=stable_local_digest(run.final_output),
        )

    def admit_collective(
        self,
        observations: list[NodeObservation],
        *,
        min_failure_domains: int = 2,
    ) -> CollectiveAdmission:
        if min_failure_domains <= 0:
            raise ValueError("min_failure_domains must be positive")

        obstruction_codes: list[str] = []
        admitted_ids: list[str] = []
        domains: set[str] = set()

        for observation in observations:
            node = self._nodes.get(observation.node_id)
            if node is None:
                obstruction_codes.append("MESH_NODE_NOT_REGISTERED")
                continue
            if node.failure_domain != observation.failure_domain:
                obstruction_codes.append("MESH_IDENTITY_MISMATCH")
                continue
            if not observation.witness_digests:
                obstruction_codes.append("COLLECTIVE_WITNESS_MISSING")
                continue
            admitted_ids.append(observation.node_id)
            domains.add(observation.failure_domain)

        if len(domains) < min_failure_domains:
            obstruction_codes.append("COLLECTIVE_DIVERSITY_INSUFFICIENT")

        unique_codes = sorted(set(obstruction_codes))
        normalized_observations = sorted(
            (obs.model_dump(mode="json") for obs in observations),
            key=lambda item: item["node_id"],
        )
        observation_root = stable_local_digest(normalized_observations)

        return CollectiveAdmission(
            admitted=not unique_codes,
            identity_root=self.identity_root,
            mesh_root_digest=self.mesh_root_digest(),
            independent_failure_domains=len(domains),
            admitted_node_ids=sorted(set(admitted_ids)),
            obstruction_codes=unique_codes,
            observation_root_digest=observation_root,
        )
