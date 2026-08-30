// ============================================================
// Gate 11 — Agent Habitat Tests
// ~20 tests: registry, coordinator, memory, scheduler, workflow engine, telemetry
// ============================================================

import { describe, it, expect } from 'vitest'
import { EpistemicTier } from '../../src/core/types'
import type { AgentManifest, AgentMemoryEntry, CoordinationFrame } from '../../src/agents/types'
import { AgentRegistrationError, AgentCoordinationError, AGENT_MANIFEST_SCHEMA_VERSION } from '../../src/agents/types'
import { AgentRegistry } from '../../src/agents/registry/agent-registry.js'
import { createAgentCoordinator } from '../../src/agents/coordination/AgentCoordinator.js'
import { AgentMemory } from '../../src/agents/memory/agent-memory.js'
import { buildSchedule, computeSchedulePressure } from '../../src/agents/scheduler/scheduler.js'
import { WorkflowEngine } from '../../src/agents/workflows/workflow-engine.js'
import { buildAgentTelemetry } from '../../src/agents/telemetry/agent-telemetry.js'
import type { SHA256Hex } from '../../src/core/types'

// ─── Test helpers ──────────────────────────────────────────

const mockHash = (s: string) => s.padEnd(64, '0') as SHA256Hex

function makeManifest(overrides: Partial<AgentManifest> = {}): AgentManifest {
  return {
    schema_version: AGENT_MANIFEST_SCHEMA_VERSION,
    agent_id: 'agent-001',
    name: 'Test Agent',
    agent_type: 'ResearchAgent',
    epistemic_tier: EpistemicTier.T2,
    capability_manifest: {
      capability_ids: ['telemetry'],
      invariant_bindings: [],
      telemetry_schema_version: '1.0.0',
    },
    is_replay_safe: true,
    entropy_budget_fixed: 0,
    workspace_boundary: ['/workspace'],
    status: 'registered',
    ...overrides,
  }
}

function makeMemoryEntry(overrides: Partial<AgentMemoryEntry> = {}): AgentMemoryEntry {
  return {
    entry_id: 'entry-001',
    agent_id: 'agent-001',
    sequence: 1,
    content_hash: mockHash('h1'),
    memory_type: 'observation',
    is_replay_reconstructable: true,
    ...overrides,
  }
}

function makeFrame(overrides: Partial<CoordinationFrame> = {}): CoordinationFrame {
  return {
    frame_id: 'frame-001',
    sequence: 1,
    agent_id: 'agent-001',
    action_type: 'observe',
    mutation_ids: [],
    replay_safe: true,
    ...overrides,
  }
}

// ─── Agent Registry ────────────────────────────────────────

describe('AgentRegistry', () => {
  it('starts empty', () => {
    const r = AgentRegistry.empty()
    expect(r.registeredCount()).toBe(0)
    expect(r.getActive()).toHaveLength(0)
  })

  it('admits a T2 agent', () => {
    const r = AgentRegistry.empty().register(makeManifest(), 1)
    expect(r.registeredCount()).toBe(1)
    expect(r.getActive()).toHaveLength(1)
  })

  it('rejects T3 agent', () => {
    const m = makeManifest({ epistemic_tier: EpistemicTier.T3 })
    expect(() => AgentRegistry.empty().register(m, 1)).toThrowError(AgentRegistrationError)
  })

  it('rejects non-replay-safe agent', () => {
    const m = makeManifest({ is_replay_safe: false })
    expect(() => AgentRegistry.empty().register(m, 1)).toThrowError(AgentRegistrationError)
  })

  it('rejects duplicate agent_id', () => {
    const r = AgentRegistry.empty().register(makeManifest(), 1)
    expect(() => r.register(makeManifest(), 2)).toThrowError(AgentRegistrationError)
  })

  it('retire removes agent from active list', () => {
    const r = AgentRegistry.empty().register(makeManifest(), 1).retire('agent-001', 2)
    expect(r.getActive()).toHaveLength(0)
  })
})

// ─── Agent Coordinator ─────────────────────────────────────

describe('AgentCoordinator', () => {
  it('starts empty — nextAgent returns undefined', () => {
    const c = createAgentCoordinator()
    expect(c.nextAgent(10)).toBeUndefined()
    expect(c.scheduleLength).toBe(0)
  })

  it('nextAgent returns lowest-sequence agent', () => {
    const c = createAgentCoordinator()
      .scheduleAgent('agent-B', 5, 0)
      .scheduleAgent('agent-A', 3, 0)
    expect(c.nextAgent(10)).toBe('agent-A')
  })

  it('nextAgent respects priority when sequences equal', () => {
    const c = createAgentCoordinator()
      .scheduleAgent('agent-X', 1, 5)
      .scheduleAgent('agent-Y', 1, 1)
    expect(c.nextAgent(10)).toBe('agent-Y')
  })

  it('verifyDeterminism passes for strictly monotonic frames', () => {
    const c = createAgentCoordinator()
      .recordFrame(makeFrame({ frame_id: 'f1', sequence: 1 }))
      .recordFrame(makeFrame({ frame_id: 'f2', sequence: 2 }))
    expect(c.verifyDeterminism()).toBe(true)
  })

  it('rejects out-of-order frame', () => {
    const c = createAgentCoordinator()
      .recordFrame(makeFrame({ frame_id: 'f1', sequence: 5 }))
    expect(() => c.recordFrame(makeFrame({ frame_id: 'f2', sequence: 4 }))).toThrowError(AgentCoordinationError)
  })

  it('coordinationStability is 1 with no frames', () => {
    expect(createAgentCoordinator().coordinationStability()).toBe(1)
  })
})

// ─── Agent Memory ──────────────────────────────────────────

describe('AgentMemory', () => {
  it('starts empty', () => {
    const m = AgentMemory.empty()
    expect(m.length).toBe(0)
    expect(m.verifyReplayCompleteness()).toBe(1)
  })

  it('append-only: returns new instance, source unchanged', () => {
    const m0 = AgentMemory.empty()
    const m1 = m0.store(makeMemoryEntry({ sequence: 1 }))
    expect(m0.length).toBe(0)
    expect(m1.length).toBe(1)
  })

  it('recall filters by agent_id and memory_type', () => {
    const m = AgentMemory.empty()
      .store(makeMemoryEntry({ entry_id: 'e1', agent_id: 'agent-A', sequence: 1, memory_type: 'observation' }))
      .store(makeMemoryEntry({ entry_id: 'e2', agent_id: 'agent-B', sequence: 2, memory_type: 'observation' }))
    expect(m.recall('agent-A')).toHaveLength(1)
    expect(m.recall('agent-A', 'observation')).toHaveLength(1)
    expect(m.recall('agent-A', 'decision')).toHaveLength(0)
  })

  it('verifyReplayCompleteness returns correct ratio', () => {
    const m = AgentMemory.empty()
      .store(makeMemoryEntry({ entry_id: 'e1', sequence: 1, is_replay_reconstructable: true }))
      .store(makeMemoryEntry({ entry_id: 'e2', sequence: 2, is_replay_reconstructable: false }))
    expect(m.verifyReplayCompleteness()).toBe(0.5)
  })

  it('out-of-order sequence throws AgentCoordinationError', () => {
    const m = AgentMemory.empty().store(makeMemoryEntry({ sequence: 10 }))
    expect(() => m.store(makeMemoryEntry({ sequence: 5 }))).toThrowError(AgentCoordinationError)
  })
})

// ─── Scheduler ─────────────────────────────────────────────

describe('buildSchedule', () => {
  it('produces byte-identical output across 3 runs (determinism)', () => {
    const agents: AgentManifest[] = [
      makeManifest({ agent_id: 'agent-Z', agent_type: 'ResearchAgent' }),
      makeManifest({ agent_id: 'agent-A', agent_type: 'WorkspaceMappingAgent' }),
    ]
    const r1 = buildSchedule(agents, 100)
    const r2 = buildSchedule(agents, 100)
    const r3 = buildSchedule(agents, 100)
    expect(JSON.stringify(r1)).toBe(JSON.stringify(r2))
    expect(JSON.stringify(r2)).toBe(JSON.stringify(r3))
  })

  it('sorts by agent_type then agent_id', () => {
    const agents: AgentManifest[] = [
      makeManifest({ agent_id: 'z', agent_type: 'ResearchAgent' }),
      makeManifest({ agent_id: 'a', agent_type: 'ResearchAgent' }),
      makeManifest({ agent_id: 'x', agent_type: 'WorkspaceMappingAgent' }),
    ]
    const schedule = buildSchedule(agents, 0)
    expect(schedule[0]?.agent_id).toBe('a')
    expect(schedule[1]?.agent_id).toBe('z')
    expect(schedule[2]?.agent_id).toBe('x')
  })

  it('computeSchedulePressure returns 0 for empty schedule', () => {
    expect(computeSchedulePressure([], 5)).toBe(0)
  })

  it('computeSchedulePressure returns fraction of pending entries', () => {
    const agents = [
      makeManifest({ agent_id: 'a1' }),
      makeManifest({ agent_id: 'a2' }),
    ]
    const schedule = buildSchedule(agents, 10)
    // both entries have sequence >= 10, currentSequence = 5 → both pending
    expect(computeSchedulePressure(schedule, 5)).toBe(1)
    // currentSequence = 100 → none pending
    expect(computeSchedulePressure(schedule, 100)).toBe(0)
  })
})

// ─── Workflow Engine ───────────────────────────────────────

describe('WorkflowEngine', () => {
  it('starts empty', () => {
    const e = WorkflowEngine.empty()
    expect(e.executions).toHaveLength(0)
    expect(e.replayIntegrity()).toBe(1)
  })

  it('start → recordFrame → complete lifecycle', () => {
    const { engine: e1, execution } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-001',
      workflow_type: 'research',
      agent_id: 'agent-001',
      sequence: 1,
    })
    expect(execution.status).toBe('active')

    const e2 = e1.recordFrame('wf-001', {
      frame_id: 'rf-001',
      workflow_id: 'wf-001',
      sequence: 2,
      step_type: 'gather',
      input_hash: mockHash('in'),
      output_hash: mockHash('out'),
      invariant_satisfied: true,
    })
    expect(e2.getExecution('wf-001')?.replay_frame_count).toBe(1)

    const e3 = e2.completeWorkflow('wf-001', 3)
    expect(e3.getExecution('wf-001')?.status).toBe('completed')
    expect(e3.replayIntegrity()).toBe(1)
  })

  it('abortWorkflow sets status=aborted', () => {
    const { engine } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-X',
      workflow_type: 'refactor',
      agent_id: 'agent-001',
      sequence: 1,
    })
    const aborted = engine.abortWorkflow('wf-X', 2)
    expect(aborted.getExecution('wf-X')?.status).toBe('aborted')
  })

  it('rejects unknown workflow type', () => {
    expect(() =>
      WorkflowEngine.empty().startWorkflow({
        workflow_id: 'wf-bad',
        workflow_type: 'unknown-type' as never,
        agent_id: 'agent-001',
        sequence: 1,
      })
    ).toThrowError(AgentCoordinationError)
  })
})

// ─── Telemetry ─────────────────────────────────────────────

describe('buildAgentTelemetry', () => {
  it('all 6 fields present', () => {
    const t = buildAgentTelemetry({
      coordinationStability: 0.9,
      completedWorkflows: 5,
      totalWorkflows: 10,
      memoryEntries: 20,
      governedPathCount: 4,
      admittedPlugins: 4,
      totalMutations: 15,
      activeAgents: 3,
      activeWorkflows: 2,
    })
    expect(typeof t.agent_coordination_stability).toBe('number')
    expect(typeof t.workflow_replay_integrity).toBe('number')
    expect(typeof t.workspace_memory_density).toBe('number')
    expect(typeof t.extension_ecology_entropy).toBe('number')
    expect(typeof t.mutation_chain_depth).toBe('number')
    expect(typeof t.orchestration_pressure_index).toBe('number')
  })

  it('orchestration_pressure_index is bounded [0,1]', () => {
    const t = buildAgentTelemetry({
      coordinationStability: 1,
      completedWorkflows: 0,
      totalWorkflows: 0,
      memoryEntries: 1000,
      governedPathCount: 1,
      admittedPlugins: 100,
      totalMutations: 1000,
      activeAgents: 100,
      activeWorkflows: 100,
    })
    expect(t.orchestration_pressure_index).toBeGreaterThanOrEqual(0)
    expect(t.orchestration_pressure_index).toBeLessThanOrEqual(1)
  })

  it('workflow_replay_integrity is 1 when no workflows exist', () => {
    const t = buildAgentTelemetry({
      coordinationStability: 1,
      completedWorkflows: 0,
      totalWorkflows: 0,
      memoryEntries: 0,
      governedPathCount: 0,
      admittedPlugins: 0,
      totalMutations: 0,
      activeAgents: 0,
      activeWorkflows: 0,
    })
    expect(t.workflow_replay_integrity).toBe(1)
  })
})
