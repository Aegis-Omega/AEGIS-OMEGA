// Workspace memory continuity regression tests (existing EventStore + graph).
import 'fake-indexeddb/auto'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { EventStore } from '../../src/event/store.js'
import { AgentMemory } from '../../src/agents/memory/agent-memory.js'
import { EventType, RetentionClass } from '../../src/core/types.js'
import type { SHA256Hex, UUIDv7 } from '../../src/core/types.js'
import {
  WorkspaceMemorySpine, WorkspaceMemoryError, WORKSPACE_MEMORY_SCHEMA_VERSION,
} from '../../src/ide/workspace/workspace-memory-spine.js'

const H = '0'.repeat(64) as SHA256Hex
let counter = 0
function streamId(): UUIDv7 {
  counter += 1
  return ('0190abcd-1234-7000-8000-' + String(counter).padStart(12, '0')) as UUIDv7
}
async function newMemory(id = streamId()) {
  const store = new EventStore(id)
  await store.open()
  return { store, memory: new WorkspaceMemorySpine(store, 'agent-coordinator', '1.0.0') }
}
const node = (node_id: string, agent_id = 'research') => ({
  node_id, node_type: 'agent_interaction' as const, payload_hash: H, agent_id,
})
const edge = (edge_id: string, from_node_id: string, to_node_id: string) => ({
  edge_id, from_node_id, to_node_id, relation: 'derived-from',
})
const TS = 1600000000000

describe('WorkspaceMemorySpine', () => {
  afterEach(() => vi.restoreAllMocks())

  it('restores a persisted graph from a newly opened EventStore instance', async () => {
    const id = streamId()
    const a = await newMemory(id)
    const n = await a.memory.recordNode(node('n1'), TS)
    expect(n.sequence).toBe(0)
    const b = await newMemory(id)
    expect((await b.memory.restore()).nodes.map(x => x.node_id)).toEqual(['n1'])
  })

  it('reconstructs cross-agent causal ancestry, not just immediate parents', async () => {
    const { memory } = await newMemory()
    await memory.recordNode(node('source', 'research'), TS)
    await memory.recordNode(node('review', 'verifier'), TS + 1)
    await memory.recordNode(node('outcome', 'builder'), TS + 2)
    await memory.recordEdge(edge('e1', 'source', 'review'), TS + 3)
    await memory.recordEdge(edge('e2', 'review', 'outcome'), TS + 4)
    const lineage = await memory.recallLineage('outcome')
    expect(lineage.nodes.map(n => n.node_id)).toEqual(['source', 'review', 'outcome'])
    expect(lineage.edges.map(e => e.edge_id)).toEqual(['e1', 'e2'])
  })

  it('never writes dangling or cyclic provenance edges', async () => {
    const { store, memory } = await newMemory()
    await memory.recordNode(node('a'), TS)
    await memory.recordNode(node('b'), TS)
    await expect(memory.recordEdge(edge('dangling', 'a', 'ghost'), TS)).rejects.toThrow('Dangling')
    await memory.recordEdge(edge('ok', 'a', 'b'), TS)
    await expect(memory.recordEdge(edge('cycle', 'b', 'a'), TS)).rejects.toThrow('Cyclic')
    await expect(memory.recordEdge(edge('self', 'a', 'a'), TS)).rejects.toThrow('Cyclic')
    expect((await store.getAll())).toHaveLength(3)
  })

  it('rejects duplicate node and edge IDs before persisting', async () => {
    const { memory, store } = await newMemory()
    await memory.recordNode(node('a'), TS)
    await memory.recordNode(node('b'), TS)
    await expect(memory.recordNode(node('a'), TS)).rejects.toThrow('Duplicate')
    await memory.recordEdge(edge('e', 'a', 'b'), TS)
    await expect(memory.recordEdge(edge('e', 'a', 'b'), TS)).rejects.toThrow('Duplicate')
    expect((await store.getAll())).toHaveLength(3)
  })

  it('rejects invalid identifiers and non-hex provenance before writing', async () => {
    const { memory, store } = await newMemory()
    await expect(memory.recordNode({ ...node('bad'), payload_hash: 'z'.repeat(64) as SHA256Hex }, TS)).rejects.toThrow('payload_hash')
    await expect(memory.recordNode(node('  '), TS)).rejects.toThrow('node_id')
    expect((await store.getAll())).toHaveLength(0)
  })

  it('fails closed if an indexed event payload was altered', async () => {
    const { memory, store } = await newMemory()
    await memory.recordNode(node('original'), TS)
    const first = (await store.getAll())[0]!
    vi.spyOn(store, 'getAll').mockResolvedValueOnce([
      { ...first, payload: {
        schema_version: WORKSPACE_MEMORY_SCHEMA_VERSION, node: node('forged'),
      } },
    ])
    await expect(memory.restore()).rejects.toThrow('Corrupt memory chain')
  })

  it('does not admit foreign event types in the memory stream', async () => {
    const { memory, store } = await newMemory()
    await store.append(EventType.SYSTEM_OUTPUT, { text: 'not memory' }, 'agent', '1', '1', RetentionClass.STANDARD, TS)
    await expect(memory.restore()).rejects.toThrow('Unsupported workspace memory schema')
  })

  it('rejects unknown memory schema, not silently reinterpreting it', async () => {
    const { memory, store } = await newMemory()
    await store.append(
      EventType.WORKSPACE_MEMORY_NODE_APPENDED,
      { schema_version: '2.0.0', node: node('a') },
      'agent', '1', '2.0.0', RetentionClass.STANDARD, TS,
    )
    await expect(memory.restore()).rejects.toThrow('Unsupported workspace memory schema')
  })


  it('promotes replayable per-agent memory references into shared durable evidence', async () => {
    const id = streamId()
    const a = await newMemory(id)
    const privateMemory = AgentMemory.empty().store({
      entry_id: 'lesson-001',
      agent_id: 'research',
      sequence: 1,
      content_hash: H,
      memory_type: 'lesson',
      is_replay_reconstructable: true,
    })
    for (const entry of privateMemory.entries) {
      await a.memory.recordAgentMemory(entry, TS)
    }
    const b = await newMemory(id)
    const revived = await b.memory.restore()
    expect(revived.nodes).toHaveLength(1)
    expect(revived.nodes[0]?.node_id).toBe('agent-memory:lesson-001')
    expect(revived.nodes[0]?.agent_id).toBe('research')
    expect(revived.nodes[0]?.payload_hash).toBe(H)
  })

  it('refuses to consolidate un-replayable agent recollections', async () => {
    const { memory, store } = await newMemory()
    await expect(memory.recordAgentMemory({
      entry_id: 'unverifiable',
      agent_id: 'research',
      sequence: 1,
      content_hash: H,
      memory_type: 'opinion',
      is_replay_reconstructable: false,
    }, TS)).rejects.toThrow('not replay-reconstructable')
    expect(await store.getAll()).toHaveLength(0)
  })

  it('rejects missing recall target and preserves an empty memory', async () => {
    const { memory } = await newMemory()
    expect((await memory.restore()).nodeCount).toBe(0)
    await expect(memory.recallLineage('missing')).rejects.toBeInstanceOf(WorkspaceMemoryError)
  })
})
