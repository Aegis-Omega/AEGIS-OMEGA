// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 13
// EPISTEMIC TIER: T0/T1
//
// Covers getter methods and error branches with zero prior coverage:
//   agents/coordination/AgentCoordinator.ts — .frames getter
//   agents/registry/agent-registry.ts       — .manifests getter
//   agents/workflows/workflow-engine.ts     — .frames getter
//   environment/kernel/capability_guard.ts  — .capabilities getter
//   ide/workspace/WorkspaceMemoryGraph.ts   — .nodes, .edges getters
//   ledger/persistence.ts                   — snapshot_sequence invalid BigInt,
//                                             entry.sequence invalid BigInt
//   gate/mutation-governance.ts             — markApplied second call (false branch)
// ============================================================

import { describe, it, expect } from 'vitest'

// ── agents/coordination/AgentCoordinator.ts — .frames getter ──

import { createAgentCoordinator } from '../../src/agents/coordination/AgentCoordinator.js'

describe('AgentCoordinator.frames getter', () => {
  it('returns empty array on fresh coordinator', () => {
    const c = createAgentCoordinator()
    expect(c.frames).toEqual([])
    expect(c.frames.length).toBe(0)
  })

  it('frames array stays empty after scheduling (no record() called)', () => {
    const c = createAgentCoordinator().scheduleAgent('agent-a', 1)
    expect(c.frames.length).toBe(0)
  })
})

// ── agents/registry/agent-registry.ts — .manifests getter ────

import { AgentRegistry } from '../../src/agents/registry/agent-registry.js'
import type { AgentManifest } from '../../src/agents/types.js'
import { EpistemicTier } from '../../src/core/types.js'
import { AGENT_MANIFEST_SCHEMA_VERSION } from '../../src/agents/types.js'

function makeManifest(overrides: Partial<AgentManifest> = {}): AgentManifest {
  return {
    schema_version: AGENT_MANIFEST_SCHEMA_VERSION,
    agent_id: 'agent-cov13',
    name: 'CoverageTestAgent',
    agent_type: 'ResearchAgent',
    epistemic_tier: EpistemicTier.T1,
    status: 'registered',
    registered_at_sequence: 1,
    is_replay_safe: true,
    entropy_budget_fixed: 0,
    workspace_boundary: [],
    capability_manifest: {
      capability_ids: [],
      invariant_bindings: [],
      telemetry_schema_version: '1.0.0',
    },
    ...overrides,
  }
}

describe('AgentRegistry.manifests getter', () => {
  it('returns empty array for empty registry', () => {
    expect(AgentRegistry.empty().manifests).toEqual([])
  })

  it('returns the registered manifest after register()', () => {
    const r = AgentRegistry.empty().register(makeManifest(), 1)
    expect(r.manifests).toHaveLength(1)
    expect(r.manifests[0]!.agent_id).toBe('agent-cov13')
  })
})

// ── agents/workflows/workflow-engine.ts — .frames getter ──────

import { WorkflowEngine } from '../../src/agents/workflows/workflow-engine.js'

describe('WorkflowEngine.frames getter', () => {
  it('returns empty array on empty engine', () => {
    expect(WorkflowEngine.empty().frames).toEqual([])
  })

  it('frames array is empty after startWorkflow (before any frame recorded)', () => {
    const { engine } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-cov13',
      workflow_type: 'research',
      agent_id: 'agent-x',
      sequence: 1,
    })
    expect(engine.frames.length).toBe(0)
  })
})

// ── environment/kernel/capability_guard.ts — .capabilities ───

import { createCapabilityGuard } from '../../src/environment/kernel/capability_guard.js'
import type { HostCapability } from '../../src/environment/types.js'
import { EpistemicTier as ET } from '../../src/core/types.js'

function makeCapability(overrides: Partial<HostCapability> = {}): HostCapability {
  return {
    capability_id: 'cap-cov13',
    class: 'telemetry',
    name: 'Test Capability',
    provenance_tier: ET.T0,
    ontology_term: 'test.capability',
    admissibility_reason: 'test',
    entropy_impact_bounded: true,
    ...overrides,
  }
}

describe('CapabilityGuard.capabilities getter', () => {
  it('returns empty array on fresh guard', () => {
    const guard = createCapabilityGuard()
    expect(guard.capabilities).toEqual([])
    expect(guard.capabilities.length).toBe(0)
  })

  it('returns registered capability after register()', () => {
    const guard = createCapabilityGuard().register(makeCapability())
    expect(guard.capabilities).toHaveLength(1)
    expect(guard.capabilities[0]!.capability_id).toBe('cap-cov13')
  })
})

// ── ide/workspace/WorkspaceMemoryGraph.ts — .nodes, .edges ───

import { WorkspaceMemoryGraph } from '../../src/ide/workspace/WorkspaceMemoryGraph.js'
import type { GraphNode, GraphEdge } from '../../src/ide/workspace/WorkspaceMemoryGraph.js'
import type { SHA256Hex as Sha256Hex } from '../../src/core/types.js'

const ZERO_H = '0'.repeat(64) as Sha256Hex

function makeNode(id: string, seq = 1): GraphNode {
  return { node_id: id, node_type: 'file', sequence: seq, payload_hash: ZERO_H }
}

function makeEdge(from: string, to: string, seq = 1): GraphEdge {
  return { edge_id: `${from}-${to}`, from_node_id: from, to_node_id: to, relation: 'import', sequence: seq }
}

describe('WorkspaceMemoryGraph.nodes getter', () => {
  it('returns empty array on empty graph', () => {
    expect(WorkspaceMemoryGraph.empty().nodes).toEqual([])
  })

  it('returns added nodes', () => {
    const g = WorkspaceMemoryGraph.empty().addNode(makeNode('n1'))
    expect(g.nodes).toHaveLength(1)
    expect(g.nodes[0]!.node_id).toBe('n1')
  })
})

describe('WorkspaceMemoryGraph.edges getter', () => {
  it('returns empty array on empty graph', () => {
    expect(WorkspaceMemoryGraph.empty().edges).toEqual([])
  })

  it('returns added edges', () => {
    const g = WorkspaceMemoryGraph.empty()
      .addNode(makeNode('n1'))
      .addNode(makeNode('n2'))
      .addEdge(makeEdge('n1', 'n2'))
    expect(g.edges).toHaveLength(1)
    expect(g.edges[0]!.from_node_id).toBe('n1')
  })
})

// ── ledger/persistence.ts — BigInt parse failures ─────────────

import { LedgerPersistenceError, deserializeSnapshot } from '../../src/ledger/persistence.js'
import { LEDGER_SCHEMA_VERSION } from '../../src/ledger/types.js'

const GOOD_HASH = '0'.repeat(64)

function snapshotWith(overrides: Record<string, unknown>): string {
  return JSON.stringify({
    schema_version: LEDGER_SCHEMA_VERSION,
    is_replay_reconstructable: true,
    entries: [],
    entry_count: 0,
    merkle_root: GOOD_HASH,
    snapshot_sequence: '0',
    ...overrides,
  })
}

function snapshotWithEntry(entryOverride: Record<string, unknown>): string {
  const entry = {
    sequence: '1',
    previous_hash: GOOD_HASH,
    frame_hash: GOOD_HASH,
    governance_hash: GOOD_HASH,
    timestamp_ms: 1_600_000_000_000,
    ...entryOverride,
  }
  return JSON.stringify({
    schema_version: LEDGER_SCHEMA_VERSION,
    is_replay_reconstructable: true,
    entries: [entry],
    entry_count: 1,
    merkle_root: GOOD_HASH,
    snapshot_sequence: '1',
  })
}

describe('deserializeSnapshot: snapshot_sequence invalid BigInt string', () => {
  it('throws LedgerPersistenceError when snapshot_sequence is non-numeric string', () => {
    expect(() => deserializeSnapshot(snapshotWith({ snapshot_sequence: 'not-a-bigint' })))
      .toThrow(LedgerPersistenceError)
  })

  it('error message mentions snapshot_sequence', () => {
    expect(() => deserializeSnapshot(snapshotWith({ snapshot_sequence: 'xyz' })))
      .toThrow(/snapshot_sequence/)
  })
})

describe('deserializeSnapshot: entry.sequence invalid BigInt string', () => {
  it('throws LedgerPersistenceError when entry sequence is non-numeric string', () => {
    expect(() => deserializeSnapshot(snapshotWithEntry({ sequence: 'not-a-number' })))
      .toThrow(LedgerPersistenceError)
  })

  it('error message mentions sequence', () => {
    expect(() => deserializeSnapshot(snapshotWithEntry({ sequence: '0xGG' })))
      .toThrow(/sequence/)
  })
})

// ── gate/mutation-governance.ts — markApplied second call ─────

import { MutationGovernanceRegistry } from '../../src/gate/mutation-governance.js'
import type { MigrationContract } from '../../src/gate/mutation-governance.js'
import { CapabilityClass } from '../../src/core/types.js'
import type { CapacityDeclaration, SHA256Hex as Sha256HexT } from '../../src/core/types.js'

const ZERO_HASH_MG = '0'.repeat(64) as Sha256HexT

function makeMig(id: string): MigrationContract {
  return {
    migration_id: id,
    from_schema_id: 'schema-x',
    from_version: '1.0.0',
    to_schema_id: 'schema-x',
    to_version: '2.0.0',
    transform: (p: unknown) => p,
    transform_source_hash: ZERO_HASH_MG,
    delta_k: 1,
  }
}

function makeCapacity(id: string, kBound = 10): CapacityDeclaration {
  return {
    component_id: id,
    k_bound: kBound,
    mutation_operators: [],
    dependency_graph_hash: ZERO_HASH_MG,
    capability_class: CapabilityClass.INFERENCE,
    epoch_duration_ms: 3600000,
    k_measurement_version: '1.0.0',
  }
}

describe('MutationGovernanceRegistry.markApplied — second call same component', () => {
  it('does not throw when markApplied called twice for the same component', () => {
    const reg = new MutationGovernanceRegistry()
    reg.registerCapacity(makeCapacity('comp-cov13'))
    reg.register(makeMig('mig-a'), { migration_id: 'mig-a', rollback_supported: false })
    reg.register(makeMig('mig-b'), { migration_id: 'mig-b', rollback_supported: false })
    reg.markApplied('comp-cov13', 'mig-a')
    // Second call for same component hits the false branch of the has() check
    expect(() => reg.markApplied('comp-cov13', 'mig-b')).not.toThrow()
  })

  it('second markApplied for same component accumulates K correctly', () => {
    const reg = new MutationGovernanceRegistry()
    reg.registerCapacity(makeCapacity('comp-cov13b'))
    reg.register(makeMig('mig-c'), { migration_id: 'mig-c', rollback_supported: false })
    reg.register(makeMig('mig-d'), { migration_id: 'mig-d', rollback_supported: false })
    reg.markApplied('comp-cov13b', 'mig-c')
    reg.markApplied('comp-cov13b', 'mig-d')
    // 2 migrations × delta_k=1 each = 2 total K applied
    // k_bound = 10, so delta = 7 → total = 9 ≤ 10 → should pass
    expect(() => reg.validateKBound('comp-cov13b', 7)).not.toThrow()
    // delta = 9 → total = 11 > 10 → should throw
    expect(() => reg.validateKBound('comp-cov13b', 9)).toThrow('K_BOUND_EXCEEDED_comp-cov13b')
  })
})
