# Workspace Memory Model — Append-Only Provenance Graph

## Epistemic Tier: T1 · Gate 11

---

## WorkspaceMemoryGraph Semantics

`WorkspaceMemoryGraph` is the IDE's long-term memory: an append-only, immutable
provenance graph that records every significant event in the workspace's lifetime.
It is the evolutionary record of the workspace — not just its current state.

Nodes represent discrete events or artifacts. Edges represent causal relationships
between them. Together, they form a directed acyclic graph (DAG) of workspace
provenance that can be replayed from any starting point.

The graph is never mutated — `addNode` and `addEdge` each return a new instance.
The previous instance remains valid and can be used as a replay checkpoint.

---

## 6 Node Types

| Type | Meaning |
|------|---------|
| `file` | A file artifact in the workspace |
| `mutation` | A recorded state mutation (write, delete, rename) |
| `agent_interaction` | An agent's read or write interaction with the workspace |
| `extension_impact` | A side effect produced by an admitted plugin |
| `telemetry_transition` | A telemetry metric crossing a significant threshold |
| `ontology_reference` | A reference to an external ontology term or definition |

Every node carries a `payload_hash: SHA256Hex` — the hash of the event payload
that it represents. This binds the graph node to the event substrate's integrity chain.

---

## Lineage Tracing

`replayLineage(target_node_id)` returns all edges whose `to_node_id` matches
`target_node_id`. These are the incoming edges — the causal ancestors of that node.

To trace full provenance of a node:
1. Call `replayLineage(target)` to get its immediate predecessors
2. For each predecessor's `from_node_id`, repeat recursively
3. The resulting tree is the complete causal ancestry of the target node

This is a standard graph ancestry walk and is bounded by the graph's depth.

---

## Memory Density Metric

`workspace_memory_density = memoryEntries / governedPathCount`

This metric (from `agent-telemetry.ts`) measures how thoroughly the workspace
is documented in agent memory relative to the number of paths under governance.

- `density = 0`: no memory (governance blind)
- `density = 1`: one memory entry per governed path
- `density > 1`: multiple memory entries per path (deep workspace understanding)

If `governedPathCount = 0`, density is `0` (not `Infinity`) by constitutional convention.

---

## Replay Archives as Evolutionary Workspace Memory

The workspace memory graph is not a snapshot — it is an evolutionary record.
Each `addNode` or `addEdge` call extends the record of what happened without
erasing the record of what came before.

This property means:
- Any past state of the graph can be reconstructed by replaying events up to a target sequence
- The graph can be diff'd across any two sequences to show exactly what changed
- The lineage of any artifact in the workspace is traceable to its origin

The workspace memory graph IS the replay archive from the IDE's perspective.
The `AgentMemory` (per-agent working memory) and the `WorkspaceMemoryGraph`
(cross-agent provenance record) are complementary: agents write to their own memory,
and the coordinator writes to the shared provenance graph.
