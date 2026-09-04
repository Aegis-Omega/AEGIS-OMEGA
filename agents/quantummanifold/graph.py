"""Fail-closed typed-DAG validation for QuantumManifold Scheduler v0.1.

This module validates only the structural graph invariants declared by the
approved scheduler specification. It does not rank actions or grant authority.
"""
from __future__ import annotations

from collections import deque
from typing import Any

ALLOWED_NODE_TYPES = frozenset(
    {
        "CLAIM",
        "OBLIGATION",
        "EVIDENCE",
        "THREAD",
        "ACTION_CANDIDATE",
    }
)

ALLOWED_EDGE_TYPES = frozenset(
    {
        "DEPENDS_ON",
        "SUPPORTED_BY",
        "FALSIFIED_BY",
        "BLOCKS",
        "CLOSES",
        "DERIVED_FROM",
        "BELONGS_TO_THREAD",
    }
)


def validate_typed_dag(graph: dict[str, Any]) -> None:
    """Validate v0.1 node/edge types, identity, endpoints, and acyclicity."""
    nodes = graph["nodes"]
    edges = graph["edges"]

    nodes_by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if node["type"] not in ALLOWED_NODE_TYPES:
            raise ValueError("UNKNOWN_NODE_TYPE")

        node_id = node["id"]
        previous = nodes_by_id.get(node_id)
        if previous is not None:
            if previous != node:
                raise ValueError("NODE_ID_COLLISION")
            continue
        nodes_by_id[node_id] = node

    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes_by_id}
    indegree: dict[str, int] = {node_id: 0 for node_id in nodes_by_id}

    for edge in edges:
        if edge["type"] not in ALLOWED_EDGE_TYPES:
            raise ValueError("UNKNOWN_EDGE_TYPE")

        source = edge["source"]
        target = edge["target"]
        if source not in nodes_by_id or target not in nodes_by_id:
            raise ValueError("DANGLING_EDGE")

        adjacency[source].append(target)
        indegree[target] += 1

    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target in adjacency[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if visited != len(nodes_by_id):
        raise ValueError("GRAPH_CYCLE_DETECTED")
