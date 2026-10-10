// Durable IDE memory bridge: existing EventStore -> WorkspaceMemoryGraph.
// Dedicated stream_id, strict replay validation, no new agent authority.
// This is browser-origin IndexedDB persistence, NOT cloud/global memory.
import { EventStore } from '../../event/store.js'
import { EventType, RetentionClass } from '../../core/types.js'
import type { EventEnvelope, SHA256Hex } from '../../core/types.js'
import {
  WorkspaceMemoryGraph,
} from './WorkspaceMemoryGraph.js'
import type {
  GraphNode, GraphNodeType, GraphEdge,
} from './WorkspaceMemoryGraph.js'

export const WORKSPACE_MEMORY_SCHEMA_VERSION = '1.0.0'

export class WorkspaceMemoryError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'WorkspaceMemoryError'
  }
}

export type MemoryNodeInput = Omit<GraphNode, 'sequence'>
export type MemoryEdgeInput = Omit<GraphEdge, 'sequence'>

const NODE_TYPES: readonly GraphNodeType[] = [
  'file', 'mutation', 'agent_interaction',
  'extension_impact', 'telemetry_transition', 'ontology_reference',
]
const HASH_RE = /^[a-f0-9]{64}$/

function objectOf(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new WorkspaceMemoryError('Memory payload must be an object')
  }
  return value as Record<string, unknown>
}

function identifier(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim().length === 0 || value.length > 256) {
    throw new WorkspaceMemoryError('Invalid ' + field)
  }
  return value
}

function checkedNode(value: unknown): MemoryNodeInput {
  const n = objectOf(value)
  const node_id = identifier(n['node_id'], 'node_id')
  if (!NODE_TYPES.includes(n['node_type'] as GraphNodeType)) {
    throw new WorkspaceMemoryError('Invalid node_type')
  }
  if (typeof n['payload_hash'] !== 'string' || !HASH_RE.test(n['payload_hash'])) {
    throw new WorkspaceMemoryError('Invalid payload_hash')
  }
  const agent = n['agent_id']
  if (agent !== undefined) identifier(agent, 'agent_id')
  return {
    node_id,
    node_type: n['node_type'] as GraphNodeType,
    payload_hash: n['payload_hash'] as SHA256Hex,
    ...(agent !== undefined ? { agent_id: agent as string } : {}),
  }
}

function checkedEdge(value: unknown): MemoryEdgeInput {
  const e = objectOf(value)
  return {
    edge_id: identifier(e['edge_id'], 'edge_id'),
    from_node_id: identifier(e['from_node_id'], 'from_node_id'),
    to_node_id: identifier(e['to_node_id'], 'to_node_id'),
    relation: identifier(e['relation'], 'relation'),
  }
}

function wouldCycle(graph: WorkspaceMemoryGraph, from: string, to: string): boolean {
  if (from === to) return true
  const pending = [to]
  const visited = new Set<string>()
  while (pending.length > 0) {
    const current = pending.pop()!
    if (current === from) return true
    if (visited.has(current)) continue
    visited.add(current)
    for (const edge of graph.edges) {
      if (edge.from_node_id === current) pending.push(edge.to_node_id)
    }
  }
  return false
}

function withNode(graph: WorkspaceMemoryGraph, value: unknown, sequence: number): WorkspaceMemoryGraph {
  const n = checkedNode(value)
  if (graph.nodes.some(existing => existing.node_id === n.node_id)) {
    throw new WorkspaceMemoryError('Duplicate node_id: ' + n.node_id)
  }
  return graph.addNode({ ...n, sequence })
}

function withEdge(graph: WorkspaceMemoryGraph, value: unknown, sequence: number): WorkspaceMemoryGraph {
  const e = checkedEdge(value)
  if (graph.edges.some(existing => existing.edge_id === e.edge_id)) {
    throw new WorkspaceMemoryError('Duplicate edge_id: ' + e.edge_id)
  }
  if (!graph.nodes.some(n => n.node_id === e.from_node_id) ||
      !graph.nodes.some(n => n.node_id === e.to_node_id)) {
    throw new WorkspaceMemoryError('Dangling memory edge: ' + e.edge_id)
  }
  if (wouldCycle(graph, e.from_node_id, e.to_node_id)) {
    throw new WorkspaceMemoryError('Cyclic memory edge: ' + e.edge_id)
  }
  return graph.addEdge({ ...e, sequence })
}

function sequenceOf(event: EventEnvelope): number {
  const seq = Number(event.sequence)
  if (!Number.isSafeInteger(seq) || seq < 0) {
    throw new WorkspaceMemoryError('Invalid event sequence')
  }
  return seq
}

/**
 * Each workspace has one durable EventStore with a stable, dedicated stream ID.
 * Caller must open() that EventStore before constructing this facade.
 * All writes pass the same governance boundaries as EventStore.append.
 * Node hashes are supplied by the producer; this layer verifies format, not
 * the producer's underlying artifact bytes or the truth of a claim.
 */
export class WorkspaceMemorySpine {
  constructor(
    private readonly store: EventStore,
    private readonly producer_id: string,
    private readonly producer_version: string,
  ) {
    identifier(producer_id, 'producer_id')
    identifier(producer_version, 'producer_version')
  }

  async restore(): Promise<WorkspaceMemoryGraph> {
    // One snapshot for BOTH integrity verification and reconstruction;
    // concurrent appends cannot slip between separate reads.
    const events = await this.store.getAll()
    const broken = await this.store.verifyChain(events)
    if (broken !== null) {
      throw new WorkspaceMemoryError(
        'Corrupt memory chain at sequence ' + broken.broken_at_sequence
      )
    }
    let graph = WorkspaceMemoryGraph.empty()
    for (const event of events) {
      const payload = objectOf(event.payload)
      if (payload['schema_version'] !== WORKSPACE_MEMORY_SCHEMA_VERSION ||
          event.payload_schema_version !== WORKSPACE_MEMORY_SCHEMA_VERSION) {
        throw new WorkspaceMemoryError('Unsupported workspace memory schema')
      }
      const seq = sequenceOf(event)
      if (event.event_type === EventType.WORKSPACE_MEMORY_NODE_APPENDED) {
        graph = withNode(graph, payload['node'], seq)
      } else if (event.event_type === EventType.WORKSPACE_MEMORY_EDGE_APPENDED) {
        graph = withEdge(graph, payload['edge'], seq)
      } else {
        throw new WorkspaceMemoryError('Unexpected event in dedicated memory stream')
      }
    }
    return graph
  }

  async recordNode(node: MemoryNodeInput, timestamp_ms: number): Promise<GraphNode> {
    const clean = checkedNode(node)
    const graph = await this.restore()
    if (graph.nodes.some(n => n.node_id === clean.node_id)) {
      throw new WorkspaceMemoryError('Duplicate node_id: ' + clean.node_id)
    }
    const event = await this.store.append(
      EventType.WORKSPACE_MEMORY_NODE_APPENDED,
      { schema_version: WORKSPACE_MEMORY_SCHEMA_VERSION, node: clean },
      this.producer_id,
      this.producer_version,
      WORKSPACE_MEMORY_SCHEMA_VERSION,
      RetentionClass.STANDARD,
      timestamp_ms,
    )
    return { ...clean, sequence: sequenceOf(event) }
  }

  async recordEdge(edge: MemoryEdgeInput, timestamp_ms: number): Promise<GraphEdge> {
    const clean = checkedEdge(edge)
    const graph = await this.restore()
    // Fail before the durable write; reapply exactly the replay validation.
    withEdge(graph, clean, graph.nodes.length + graph.edges.length)
    const event = await this.store.append(
      EventType.WORKSPACE_MEMORY_EDGE_APPENDED,
      { schema_version: WORKSPACE_MEMORY_SCHEMA_VERSION, edge: clean },
      this.producer_id,
      this.producer_version,
      WORKSPACE_MEMORY_SCHEMA_VERSION,
      RetentionClass.STANDARD,
      timestamp_ms,
    )
    return { ...clean, sequence: sequenceOf(event) }
  }

  async recallLineage(target_node_id: string): Promise<{
    readonly nodes: readonly GraphNode[]
    readonly edges: readonly GraphEdge[]
  }> {
    const graph = await this.restore()
    if (!graph.nodes.some(n => n.node_id === target_node_id)) {
      throw new WorkspaceMemoryError('Unknown memory node: ' + target_node_id)
    }
    const visited = new Set<string>()
    const edges = new Set<string>()
    const pending = [target_node_id]
    while (pending.length > 0) {
      const current = pending.pop()!
      if (visited.has(current)) continue
      visited.add(current)
      for (const edge of graph.replayLineage(current)) {
        edges.add(edge.edge_id)
        pending.push(edge.from_node_id)
      }
    }
    return {
      nodes: graph.nodes.filter(node => visited.has(node.node_id)),
      edges: graph.edges.filter(edge => edges.has(edge.edge_id)),
    }
  }
}
