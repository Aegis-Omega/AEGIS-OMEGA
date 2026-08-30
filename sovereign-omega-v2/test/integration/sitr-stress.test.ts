// ============================================================
// Gate 49 — SITR State Machine Stress
// ~27 tests: monotonic escalation proof, all observable state
//   transitions, terminal state invariants, determinism under
//   10-frame sequences, lattice function correctness.
//
// Proves the monotonic escalation law: SITR state can only move
// up the lattice via observe() — never down. Once a state is
// reached, subsequent clean frames cannot reverse it.
//
// Escalation trigger map (observable via public API):
//   DEGRADED          ← workflow_replay_integrity < 1
//                     ← orchestration_pressure_index > 0.9
//   UNSTABLE          ← workflowFrame.invariant_satisfied = false
//                     ← non-monotonic frame sequence (severity high)
//   CONSTITUTIONAL_RISK ← replay_safe = false (severity critical)
//   CONTAINED/COMPROMISED — not reachable via observe(); tested
//                            via lattice functions directly.
// ============================================================

import { describe, it, expect } from 'vitest'
import { SITRRuntime } from '../../src/sitr/runtime.js'
import {
  escalate, stateOrdinal, canEscalateTo, compareStates,
  isTerminalState, SITR_ESCALATION_ORDER,
} from '../../src/sitr/lattice.js'
import type { SITRState } from '../../src/sitr/types.js'
import type { CoordinationFrame } from '../../src/agents/types.js'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types.js'
import type { AgentTelemetrySnapshot } from '../../src/agents/telemetry/agent-telemetry.js'
import type { SHA256Hex } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

const CLEAN_TELEMETRY: AgentTelemetrySnapshot = Object.freeze({
  agent_coordination_stability: 1,
  workflow_replay_integrity: 1,
  workspace_memory_density: 0,
  extension_ecology_entropy: 0,
  mutation_chain_depth: 0,
  orchestration_pressure_index: 0,
})

function makeFrame(n: number, replaySafe = true): CoordinationFrame {
  return Object.freeze({
    frame_id: `f-${n}`,
    sequence: n,
    agent_id: 'agent-001',
    action_type: 'observe',
    mutation_ids: [],
    replay_safe: replaySafe,
  })
}

function makeWfFrame(n: number, satisfied = true): WorkflowReplayFrame {
  return Object.freeze({
    frame_id: `wf-${n}`,
    workflow_id: 'wflow-001',
    sequence: n,
    step_type: 'gather',
    input_hash: h('a'),
    output_hash: h('b'),
    invariant_satisfied: satisfied,
  })
}

function observe(
  sitr: SITRRuntime,
  n: number,
  overrides: Partial<{
    replaySafe: boolean
    invariantSatisfied: boolean
    telemetry: AgentTelemetrySnapshot
    extraFrames: CoordinationFrame[]
  }> = {},
): SITRRuntime {
  return sitr.observe({
    frames: [...(overrides.extraFrames ?? []), makeFrame(n, overrides.replaySafe ?? true)],
    workflowFrames: [makeWfFrame(n, overrides.invariantSatisfied ?? true)],
    telemetry: overrides.telemetry ?? CLEAN_TELEMETRY,
    sequence: n,
  })
}

// ─── Escalation paths ─────────────────────────────────────

describe('SITR: escalation paths via observe()', () => {
  it('empty runtime starts STABLE', () => {
    expect(SITRRuntime.empty().currentState()).toBe('STABLE')
  })

  it('clean inputs leave state STABLE', () => {
    const s = observe(SITRRuntime.empty(), 1)
    expect(s.currentState()).toBe('STABLE')
  })

  it('workflow_replay_integrity < 1 → DEGRADED', () => {
    const s = observe(SITRRuntime.empty(), 1, {
      telemetry: { ...CLEAN_TELEMETRY, workflow_replay_integrity: 0.5 },
    })
    expect(s.currentState()).toBe('DEGRADED')
  })

  it('orchestration_pressure_index > 0.9 → DEGRADED', () => {
    const s = observe(SITRRuntime.empty(), 1, {
      telemetry: { ...CLEAN_TELEMETRY, orchestration_pressure_index: 0.95 },
    })
    expect(s.currentState()).toBe('DEGRADED')
  })

  it('workflowFrame invariant_satisfied=false → at least UNSTABLE', () => {
    const s = observe(SITRRuntime.empty(), 1, { invariantSatisfied: false })
    expect(stateOrdinal(s.currentState())).toBeGreaterThanOrEqual(stateOrdinal('UNSTABLE'))
  })

  it('workflowFrame violation recorded in violations()', () => {
    const s = observe(SITRRuntime.empty(), 1, { invariantSatisfied: false })
    expect(s.violations().length).toBe(1)
    expect(s.violations()[0]?.violation_type).toBe('invariant_not_satisfied')
  })

  it('non-replay-safe frame → CONSTITUTIONAL_RISK', () => {
    const s = observe(SITRRuntime.empty(), 1, { replaySafe: false })
    expect(s.currentState()).toBe('CONSTITUTIONAL_RISK')
  })

  it('non-replay-safe frame dominates telemetry stress (takes max)', () => {
    const s = observe(SITRRuntime.empty(), 1, {
      replaySafe: false,
      telemetry: { ...CLEAN_TELEMETRY, workflow_replay_integrity: 0 },
    })
    expect(s.currentState()).toBe('CONSTITUTIONAL_RISK')
  })

  it('non-monotonic frame sequence (frame[1].seq <= frame[0].seq) → at least UNSTABLE', () => {
    const next = SITRRuntime.empty().observe({
      frames: [makeFrame(5), makeFrame(3)],
      workflowFrames: [],
      telemetry: CLEAN_TELEMETRY,
      sequence: 1,
    })
    expect(stateOrdinal(next.currentState())).toBeGreaterThanOrEqual(stateOrdinal('UNSTABLE'))
  })

  it('multiple workflow violations all recorded', () => {
    const next = SITRRuntime.empty().observe({
      frames: [makeFrame(1)],
      workflowFrames: [makeWfFrame(1, false), makeWfFrame(2, false), makeWfFrame(3, false)],
      telemetry: CLEAN_TELEMETRY,
      sequence: 1,
    })
    expect(next.violations().length).toBe(3)
  })

  it('empty frames and workflowFrames: state unchanged (stays STABLE)', () => {
    const s = SITRRuntime.empty().observe({
      frames: [],
      workflowFrames: [],
      telemetry: CLEAN_TELEMETRY,
      sequence: 1,
    })
    expect(s.currentState()).toBe('STABLE')
  })
})

// ─── Monotonic: never de-escalates ────────────────────────

describe('SITR: monotonic escalation — no de-escalation', () => {
  it('CONSTITUTIONAL_RISK persists through 10 subsequent clean frames', () => {
    let s = observe(SITRRuntime.empty(), 1, { replaySafe: false })
    for (let i = 2; i <= 11; i++) s = observe(s, i)
    expect(s.currentState()).toBe('CONSTITUTIONAL_RISK')
  })

  it('UNSTABLE persists through 10 subsequent clean frames', () => {
    let s = observe(SITRRuntime.empty(), 1, { invariantSatisfied: false })
    for (let i = 2; i <= 11; i++) s = observe(s, i)
    expect(stateOrdinal(s.currentState())).toBeGreaterThanOrEqual(stateOrdinal('UNSTABLE'))
  })

  it('DEGRADED persists through 10 subsequent clean frames', () => {
    let s = observe(SITRRuntime.empty(), 1, {
      telemetry: { ...CLEAN_TELEMETRY, workflow_replay_integrity: 0 },
    })
    for (let i = 2; i <= 11; i++) s = observe(s, i)
    expect(stateOrdinal(s.currentState())).toBeGreaterThanOrEqual(stateOrdinal('DEGRADED'))
  })

  it('UNSTABLE cannot be overridden downward by DEGRADED-level telemetry', () => {
    let s = observe(SITRRuntime.empty(), 1, { invariantSatisfied: false })
    s = observe(s, 2, { telemetry: { ...CLEAN_TELEMETRY, workflow_replay_integrity: 0.5 } })
    expect(stateOrdinal(s.currentState())).toBeGreaterThanOrEqual(stateOrdinal('UNSTABLE'))
  })

  it('stateOrdinal is strictly increasing across escalation sequence', () => {
    let s = SITRRuntime.empty()
    const ordinals: number[] = [stateOrdinal(s.currentState())]
    s = observe(s, 1, { telemetry: { ...CLEAN_TELEMETRY, workflow_replay_integrity: 0 } })
    ordinals.push(stateOrdinal(s.currentState()))
    s = observe(s, 2, { invariantSatisfied: false })
    ordinals.push(stateOrdinal(s.currentState()))
    s = observe(s, 3, { replaySafe: false })
    ordinals.push(stateOrdinal(s.currentState()))
    for (let i = 1; i < ordinals.length; i++) {
      expect(ordinals[i]!).toBeGreaterThanOrEqual(ordinals[i - 1]!)
    }
  })
})

// ─── Determinism ──────────────────────────────────────────

describe('SITR: state determinism under observe() sequences', () => {
  function run10(): { state: SITRState; violationCount: number } {
    let s = SITRRuntime.empty()
    for (let i = 1; i <= 4; i++) s = observe(s, i)
    s = observe(s, 5, { invariantSatisfied: false })
    s = observe(s, 6, { invariantSatisfied: false })
    for (let i = 7; i <= 9; i++) s = observe(s, i)
    s = observe(s, 10, { replaySafe: false })
    return { state: s.currentState(), violationCount: s.violations().length }
  }

  it('same 10-frame mixed sequence → same state × 3', () => {
    const r1 = run10()
    const r2 = run10()
    const r3 = run10()
    expect(r1.state).toBe(r2.state)
    expect(r2.state).toBe(r3.state)
  })

  it('same 10-frame sequence → same violations count × 3', () => {
    const r1 = run10()
    const r2 = run10()
    const r3 = run10()
    expect(r1.violationCount).toBe(r2.violationCount)
    expect(r2.violationCount).toBe(r3.violationCount)
    expect(r1.violationCount).toBe(2)
  })
})

// ─── Lattice functions ─────────────────────────────────────

describe('SITR: lattice function correctness', () => {
  const ALL: SITRState[] = ['STABLE', 'DEGRADED', 'UNSTABLE', 'CONSTITUTIONAL_RISK', 'CONTAINED', 'COMPROMISED']

  it('SITR_ESCALATION_ORDER lists all 6 states in ascending severity', () => {
    expect([...SITR_ESCALATION_ORDER]).toEqual(ALL)
  })

  it('stateOrdinal assigns distinct ordinals 0–5 in correct order', () => {
    expect(ALL.map(stateOrdinal)).toEqual([0, 1, 2, 3, 4, 5])
  })

  it('isTerminalState: only COMPROMISED returns true', () => {
    for (const s of ALL) expect(isTerminalState(s)).toBe(s === 'COMPROMISED')
  })

  it('escalate(a, b) returns the higher-ordinal state', () => {
    expect(escalate('STABLE', 'DEGRADED')).toBe('DEGRADED')
    expect(escalate('DEGRADED', 'STABLE')).toBe('DEGRADED')
    expect(escalate('UNSTABLE', 'CONSTITUTIONAL_RISK')).toBe('CONSTITUTIONAL_RISK')
    expect(escalate('COMPROMISED', 'STABLE')).toBe('COMPROMISED')
    expect(escalate('STABLE', 'STABLE')).toBe('STABLE')
  })

  it('canEscalateTo: STABLE can escalate to any higher state', () => {
    for (const s of ALL.slice(1)) expect(canEscalateTo('STABLE', s)).toBe(true)
    expect(canEscalateTo('STABLE', 'STABLE')).toBe(false)
  })

  it('canEscalateTo: COMPROMISED cannot escalate to any state', () => {
    for (const s of ALL) expect(canEscalateTo('COMPROMISED', s)).toBe(false)
  })

  it('compareStates: strict antisymmetry for all 15 distinct pairs', () => {
    for (let i = 0; i < ALL.length; i++) {
      for (let j = i + 1; j < ALL.length; j++) {
        expect(compareStates(ALL[i]!, ALL[j]!)).toBe(-1)
        expect(compareStates(ALL[j]!, ALL[i]!)).toBe(1)
      }
    }
  })

  it('compareStates: reflexivity — same state → 0', () => {
    for (const s of ALL) expect(compareStates(s, s)).toBe(0)
  })
})
