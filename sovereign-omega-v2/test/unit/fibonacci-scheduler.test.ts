import { describe, it, expect } from 'vitest'
import {
  fibonacciInterval,
  fibonacciSequence,
  cumulativeFibonacci,
  FIBONACCI_CAP,
  FIBONACCI_SCHEMA_VERSION,
} from '../../src/agents/scheduler/fibonacci.js'
import { buildSchedule } from '../../src/agents/scheduler/scheduler.js'
import type { AgentManifest } from '../../src/agents/types.js'
import { EpistemicTier } from '../../src/core/types.js'

// ============================================================
// Gate 124 — Fibonacci Scheduler Tests
// Verifies: F_n sequence, cap enforcement, cumulative offsets,
// and Fibonacci-spaced buildSchedule output.
// ============================================================

const makeAgent = (agent_id: string, agent_type: AgentManifest['agent_type']): AgentManifest =>
  Object.freeze({
    schema_version: '1.0.0' as const,
    agent_id,
    name: `Agent ${agent_id}`,
    agent_type,
    epistemic_tier: EpistemicTier.T2,
    capability_manifest: { capability_ids: [], invariant_bindings: [], telemetry_schema_version: '1.0.0' },
    is_replay_safe: true,
    entropy_budget_fixed: 0x00010000,
    workspace_boundary: [],
    status: 'registered' as const,
  })

describe('FIBONACCI_SCHEMA_VERSION', () => {
  it('is 1.0.0', () => {
    expect(FIBONACCI_SCHEMA_VERSION).toBe('1.0.0')
  })
})

describe('FIBONACCI_CAP', () => {
  it('is 89 (F_11)', () => {
    expect(FIBONACCI_CAP).toBe(89)
  })
})

describe('fibonacciInterval — Fibonacci sequence values', () => {
  it('n=1 → 1', () => { expect(fibonacciInterval(1)).toBe(1) })
  it('n=2 → 1', () => { expect(fibonacciInterval(2)).toBe(1) })
  it('n=3 → 2', () => { expect(fibonacciInterval(3)).toBe(2) })
  it('n=4 → 3', () => { expect(fibonacciInterval(4)).toBe(3) })
  it('n=5 → 5', () => { expect(fibonacciInterval(5)).toBe(5) })
  it('n=6 → 8', () => { expect(fibonacciInterval(6)).toBe(8) })
  it('n=7 → 13', () => { expect(fibonacciInterval(7)).toBe(13) })
  it('n=8 → 21', () => { expect(fibonacciInterval(8)).toBe(21) })
  it('n=9 → 34', () => { expect(fibonacciInterval(9)).toBe(34) })
  it('n=10 → 55', () => { expect(fibonacciInterval(10)).toBe(55) })
  it('n=11 → 89 (last uncapped)', () => { expect(fibonacciInterval(11)).toBe(89) })
  it('n=12 → 89 (cap applied)', () => { expect(fibonacciInterval(12)).toBe(89) })
  it('n=100 → 89 (cap stable at large n)', () => { expect(fibonacciInterval(100)).toBe(89) })
  it('n=0 → 1 (edge: treated as n<=1)', () => { expect(fibonacciInterval(0)).toBe(1) })
})

describe('fibonacciInterval — determinism', () => {
  it('produces identical output across 3 runs', () => {
    const r1 = [1,2,3,4,5].map(fibonacciInterval)
    const r2 = [1,2,3,4,5].map(fibonacciInterval)
    const r3 = [1,2,3,4,5].map(fibonacciInterval)
    expect(r1).toEqual(r2)
    expect(r2).toEqual(r3)
  })
})

describe('fibonacciSequence', () => {
  it('returns [1,1,2,3,5] for length=5', () => {
    expect(fibonacciSequence(5)).toEqual([1, 1, 2, 3, 5])
  })
  it('returns [] for length=0', () => {
    expect(fibonacciSequence(0)).toEqual([])
  })
  it('returns [1] for length=1', () => {
    expect(fibonacciSequence(1)).toEqual([1])
  })
  it('is frozen', () => {
    const seq = fibonacciSequence(5)
    expect(Object.isFrozen(seq)).toBe(true)
  })
  it('is deterministic ×3', () => {
    const r1 = fibonacciSequence(8)
    const r2 = fibonacciSequence(8)
    const r3 = fibonacciSequence(8)
    expect(r1).toEqual(r2)
    expect(r2).toEqual(r3)
  })
})

describe('cumulativeFibonacci', () => {
  it('returns [0,1,2,4,7] for count=5', () => {
    // Offsets: agent0=0, agent1=F1=1, agent2=F1+F2=2, agent3=+F3=4, agent4=+F4=7
    expect(cumulativeFibonacci(5)).toEqual([0, 1, 2, 4, 7])
  })
  it('returns [] for count=0', () => {
    expect(cumulativeFibonacci(0)).toEqual([])
  })
  it('returns [0] for count=1', () => {
    expect(cumulativeFibonacci(1)).toEqual([0])
  })
  it('is frozen', () => {
    expect(Object.isFrozen(cumulativeFibonacci(3))).toBe(true)
  })
  it('is deterministic ×3', () => {
    const r1 = cumulativeFibonacci(7)
    const r2 = cumulativeFibonacci(7)
    const r3 = cumulativeFibonacci(7)
    expect(r1).toEqual(r2)
    expect(r2).toEqual(r3)
  })
})

describe('buildSchedule — Fibonacci-spaced sequences', () => {
  it('5 agents starting at sequence 0 get Fibonacci-spaced slots', () => {
    const agents: readonly AgentManifest[] = [
      makeAgent('a1', 'ResearchAgent'),
      makeAgent('a2', 'ResearchAgent'),
      makeAgent('a3', 'ResearchAgent'),
      makeAgent('a4', 'ResearchAgent'),
      makeAgent('a5', 'ResearchAgent'),
    ]
    const schedule = buildSchedule(agents, 0)
    const sequences = schedule.map(e => e.sequence)
    expect(sequences).toEqual([0, 1, 2, 4, 7])
  })

  it('startSequence offsets all slots', () => {
    const agents: readonly AgentManifest[] = [
      makeAgent('b1', 'ReplayAuditAgent'),
      makeAgent('b2', 'ReplayAuditAgent'),
      makeAgent('b3', 'ReplayAuditAgent'),
    ]
    const schedule = buildSchedule(agents, 100)
    const sequences = schedule.map(e => e.sequence)
    expect(sequences).toEqual([100, 101, 102])
  })

  it('single agent gets sequence = startSequence', () => {
    const schedule = buildSchedule([makeAgent('c1', 'DocumentationAgent')], 42)
    expect(schedule[0]?.sequence).toBe(42)
  })

  it('output is frozen', () => {
    const schedule = buildSchedule([makeAgent('d1', 'WorkspaceMappingAgent')], 0)
    expect(Object.isFrozen(schedule)).toBe(true)
    expect(Object.isFrozen(schedule[0])).toBe(true)
  })

  it('is deterministic ×3', () => {
    const agents: readonly AgentManifest[] = [
      makeAgent('e1', 'TelemetryAnalysisAgent'),
      makeAgent('e2', 'TelemetryAnalysisAgent'),
    ]
    const r1 = buildSchedule(agents, 0).map(e => e.sequence)
    const r2 = buildSchedule(agents, 0).map(e => e.sequence)
    const r3 = buildSchedule(agents, 0).map(e => e.sequence)
    expect(r1).toEqual(r2)
    expect(r2).toEqual(r3)
  })
})
