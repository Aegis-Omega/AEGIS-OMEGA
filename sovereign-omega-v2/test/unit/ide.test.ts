// ============================================================
// Gate 11 — IDE Nervous System Tests
// ~20 tests: WorkspaceMemoryGraph, panel states, orchestrator lifecycle, determinism
// ============================================================

import { describe, it, expect } from 'vitest'
import { WorkspaceMemoryGraph } from '../../src/ide/workspace/WorkspaceMemoryGraph.js'
import {
  buildReplayExplorerPanel,
  buildWorkspaceTopologyPanel,
  buildAgentHabitatPanel,
  buildConstitutionalInvariantDashboard,
  buildTelemetryCockpit,
  buildCapabilityGovernanceSurface,
  buildExtensionEcologyView,
  buildMutationTimelinePanel,
  buildReplayIntegrityPanel,
  buildEnvironmentalDriftMonitor,
  buildInitialIDERuntimeState,
} from '../../src/ide/panels/panel-state.js'
import { IDEOrchestrator } from '../../src/ide/orchestration/orchestrator.js'
import { IDE_PANEL_SCHEMA_VERSION } from '../../src/ide/types.js'
import type { SHA256Hex } from '../../src/core/types'
import { buildSchedule } from '../../src/agents/scheduler/scheduler.js'
import type { AgentManifest } from '../../src/agents/types'
import { AGENT_MANIFEST_SCHEMA_VERSION } from '../../src/agents/types'
import { EpistemicTier } from '../../src/core/types'

// ─── Test helpers ──────────────────────────────────────────

const mockHash = (s: string) => s.padEnd(64, '0') as SHA256Hex

const EMPTY_TELEMETRY = Object.freeze({
  agent_coordination_stability: 1,
  workflow_replay_integrity: 1,
  workspace_memory_density: 0,
  extension_ecology_entropy: 0,
  mutation_chain_depth: 0,
  orchestration_pressure_index: 0,
})

function makeManifest(overrides: Partial<AgentManifest> = {}): AgentManifest {
  return {
    schema_version: AGENT_MANIFEST_SCHEMA_VERSION,
    agent_id: 'agent-001',
    name: 'Test Agent',
    agent_type: 'ResearchAgent',
    epistemic_tier: EpistemicTier.T2,
    capability_manifest: {
      capability_ids: [],
      invariant_bindings: [],
      telemetry_schema_version: '1.0.0',
    },
    is_replay_safe: true,
    entropy_budget_fixed: 0,
    workspace_boundary: [],
    status: 'registered',
    ...overrides,
  }
}

// ─── WorkspaceMemoryGraph ───────────────────────────────────

describe('WorkspaceMemoryGraph', () => {
  it('starts empty', () => {
    const g = WorkspaceMemoryGraph.empty()
    expect(g.nodeCount).toBe(0)
    expect(g.edgeCount).toBe(0)
  })

  it('addNode returns new instance; original unchanged', () => {
    const g0 = WorkspaceMemoryGraph.empty()
    const g1 = g0.addNode({
      node_id: 'n1',
      node_type: 'file',
      sequence: 1,
      payload_hash: mockHash('h1'),
    })
    expect(g0.nodeCount).toBe(0)
    expect(g1.nodeCount).toBe(1)
  })

  it('addEdge returns new instance; original unchanged', () => {
    const g0 = WorkspaceMemoryGraph.empty()
    const g1 = g0.addEdge({
      edge_id: 'e1',
      from_node_id: 'n1',
      to_node_id: 'n2',
      relation: 'mutation-of',
      sequence: 2,
    })
    expect(g0.edgeCount).toBe(0)
    expect(g1.edgeCount).toBe(1)
  })

  it('nodesForAgent filters correctly', () => {
    const g = WorkspaceMemoryGraph.empty()
      .addNode({ node_id: 'n1', node_type: 'agent_interaction', sequence: 1, agent_id: 'agent-A', payload_hash: mockHash('h1') })
      .addNode({ node_id: 'n2', node_type: 'file', sequence: 2, agent_id: 'agent-B', payload_hash: mockHash('h2') })
    expect(g.nodesForAgent('agent-A')).toHaveLength(1)
    expect(g.nodesForAgent('agent-B')).toHaveLength(1)
    expect(g.nodesForAgent('agent-C')).toHaveLength(0)
  })

  it('replayLineage returns edges by to_node_id', () => {
    const g = WorkspaceMemoryGraph.empty()
      .addEdge({ edge_id: 'e1', from_node_id: 'n1', to_node_id: 'n3', relation: 'derived-from', sequence: 1 })
      .addEdge({ edge_id: 'e2', from_node_id: 'n2', to_node_id: 'n3', relation: 'derived-from', sequence: 2 })
      .addEdge({ edge_id: 'e3', from_node_id: 'n3', to_node_id: 'n4', relation: 'derived-from', sequence: 3 })
    const lineage = g.replayLineage('n3')
    expect(lineage).toHaveLength(2)
    expect(lineage.every(e => e.to_node_id === 'n3')).toBe(true)
  })
})

// ─── Panel States ──────────────────────────────────────────

describe('Panel states', () => {
  it('all panels have is_replay_reconstructable=true', () => {
    const state = buildInitialIDERuntimeState(1)
    expect(state.replayExplorer.is_replay_reconstructable).toBe(true)
    expect(state.workspaceTopology.is_replay_reconstructable).toBe(true)
    expect(state.agentHabitat.is_replay_reconstructable).toBe(true)
    expect(state.constitutionalInvariants.is_replay_reconstructable).toBe(true)
    expect(state.telemetryCockpit.is_replay_reconstructable).toBe(true)
    expect(state.capabilityGovernance.is_replay_reconstructable).toBe(true)
    expect(state.extensionEcology.is_replay_reconstructable).toBe(true)
    expect(state.mutationTimeline.is_replay_reconstructable).toBe(true)
    expect(state.replayIntegrity.is_replay_reconstructable).toBe(true)
    expect(state.environmentalDrift.is_replay_reconstructable).toBe(true)
  })

  it('all panels have correct schema_version', () => {
    const state = buildInitialIDERuntimeState(1)
    const panels = Object.values(state)
    for (const panel of panels) {
      expect((panel as { schema_version: string }).schema_version).toBe(IDE_PANEL_SCHEMA_VERSION)
    }
  })

  it('buildInitialIDERuntimeState: all 10 panels populated with given sequence', () => {
    const state = buildInitialIDERuntimeState(42)
    expect(state.replayExplorer.last_updated_sequence).toBe(42)
    expect(state.workspaceTopology.last_updated_sequence).toBe(42)
    expect(state.agentHabitat.last_updated_sequence).toBe(42)
    expect(state.constitutionalInvariants.last_updated_sequence).toBe(42)
    expect(state.telemetryCockpit.last_updated_sequence).toBe(42)
    expect(state.capabilityGovernance.last_updated_sequence).toBe(42)
    expect(state.extensionEcology.last_updated_sequence).toBe(42)
    expect(state.mutationTimeline.last_updated_sequence).toBe(42)
    expect(state.replayIntegrity.last_updated_sequence).toBe(42)
    expect(state.environmentalDrift.last_updated_sequence).toBe(42)
  })

  it('individual panel factories use correct panel_id', () => {
    expect(buildReplayExplorerPanel(1).panel_id).toBe('replay-explorer')
    expect(buildWorkspaceTopologyPanel(1).panel_id).toBe('workspace-topology')
    expect(buildAgentHabitatPanel(1).panel_id).toBe('agent-habitat')
    expect(buildConstitutionalInvariantDashboard(1).panel_id).toBe('constitutional-invariants')
    expect(buildTelemetryCockpit(1).panel_id).toBe('telemetry-cockpit')
    expect(buildCapabilityGovernanceSurface(1).panel_id).toBe('capability-governance')
    expect(buildExtensionEcologyView(1).panel_id).toBe('extension-ecology')
    expect(buildMutationTimelinePanel(1).panel_id).toBe('mutation-timeline')
    expect(buildReplayIntegrityPanel(1).panel_id).toBe('replay-integrity')
    expect(buildEnvironmentalDriftMonitor(1).panel_id).toBe('environmental-drift')
  })
})

// ─── IDEOrchestrator ───────────────────────────────────────

describe('IDEOrchestrator', () => {
  const UPDATE_PARAMS = {
    agentTelemetry: EMPTY_TELEMETRY,
    envEntropy: 0.1,
    mutationCount: 5,
    recentMutationTypes: ['refactor'],
    driftRate: 0.02,
    stabilityScore: 0.95,
    pressureIndex: 0.1,
    activeAgents: 2,
    registeredAgents: 4,
    activeAgentTypes: ['ResearchAgent' as const],
    registeredCapabilities: 3,
    activeGrants: 1,
    admittedPlugins: 2,
    evictedPlugins: 0,
    replayFrameCount: 10,
    replayIntegrityRatio: 1,
    governedPathCount: 5,
    checkedInvariants: 12,
    t0Violations: 0,
    t1Alerts: 0,
    sequence: 10,
  }

  it('create builds state at given sequence', () => {
    const orch = IDEOrchestrator.create(1)
    expect(orch.getState().replayExplorer.last_updated_sequence).toBe(1)
    expect(orch.panelSequence()).toBe(1)
  })

  it('update returns new orchestrator, original unchanged', () => {
    const o1 = IDEOrchestrator.create(1)
    const o2 = o1.update(UPDATE_PARAMS)
    expect(o1.panelSequence()).toBe(1)
    expect(o2.panelSequence()).toBe(10)
  })

  it('update propagates all params to state', () => {
    const o = IDEOrchestrator.create(1).update(UPDATE_PARAMS)
    const s = o.getState()
    expect(s.agentHabitat.active_agent_count).toBe(2)
    expect(s.agentHabitat.registered_agent_count).toBe(4)
    expect(s.mutationTimeline.total_mutations).toBe(5)
    expect(s.replayIntegrity.reconstruction_ratio).toBe(1)
    expect(s.environmentalDrift.drift_rate).toBe(0.02)
    expect(s.constitutionalInvariants.t0_violations).toBe(0)
    expect(s.extensionEcology.admitted_plugin_count).toBe(2)
  })

  it('last_updated_sequence increases on update', () => {
    const o1 = IDEOrchestrator.create(1)
    const o2 = o1.update({ ...UPDATE_PARAMS, sequence: 50 })
    expect(o2.panelSequence()).toBe(50)
    expect(o2.panelSequence()).toBeGreaterThan(o1.panelSequence())
  })

  it('getState is consistent across multiple calls', () => {
    const o = IDEOrchestrator.create(5)
    expect(o.getState()).toBe(o.getState())
  })
})

// ─── Determinism (buildSchedule 3× same args) ──────────────

describe('Scheduler determinism', () => {
  it('buildSchedule produces identical results across 3 runs', () => {
    const agents: AgentManifest[] = [
      makeManifest({ agent_id: 'z-agent', agent_type: 'TelemetryAnalysisAgent' }),
      makeManifest({ agent_id: 'a-agent', agent_type: 'ResearchAgent' }),
      makeManifest({ agent_id: 'm-agent', agent_type: 'ResearchAgent' }),
    ]
    const r1 = buildSchedule(agents, 200)
    const r2 = buildSchedule(agents, 200)
    const r3 = buildSchedule(agents, 200)
    expect(JSON.stringify(r1)).toBe(JSON.stringify(r2))
    expect(JSON.stringify(r2)).toBe(JSON.stringify(r3))
    // All three runs produce identical first entry
    expect(r1[0]?.agent_id).toBe(r2[0]?.agent_id)
    expect(r2[0]?.agent_id).toBe(r3[0]?.agent_id)
  })
})
