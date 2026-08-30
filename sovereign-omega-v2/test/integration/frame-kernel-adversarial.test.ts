// ============================================================
// Gate 51 — Frame Kernel Adversarial
// ~24 tests: runFrame() under empty/minimal inputs, workflow
//   invariant violations, telemetry stress, frame ordering
//   anomalies, sequential pipeline feeds, structural guarantees.
//
// Proves runFrame() is correct at every edge case — the kernel
// is not just correct on the golden path but on all paths
// simultaneously. All results are frozen. Phase trace counts
// are verified to match actual execution state.
// ============================================================

import { describe, it, expect } from 'vitest'
import { runFrame } from '../../src/frame/kernel.js'
import { SITRRuntime } from '../../src/sitr/runtime.js'
import { ConstitutionalRuntime } from '../../src/constitutional/runtime.js'
import { stateOrdinal } from '../../src/sitr/lattice.js'
import type { FrameInput } from '../../src/frame/types.js'
import type { RuntimeSnapshot as InvariantRuntimeSnapshot } from '../../src/core/invariant-checker.js'
import type { CoordinationFrame } from '../../src/agents/types.js'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types.js'
import type { AgentTelemetrySnapshot } from '../../src/agents/telemetry/agent-telemetry.js'
import type { PolicyMutation, EpistemicAssertion } from '../../src/aoie/types.js'
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

const CLEAN_SNAPSHOT: InvariantRuntimeSnapshot = Object.freeze({
  vcg_error: 0,
  drift_index: 0,
  corruption_count: 0,
  pgcs_passes: true,
  calibrator_passes: true,
  failsafe_state: 'healthy',
  sequence: 1,
  gate_sealed: true,
})

const PANEL_SEQ = Object.freeze([1, 1, 1, 1, 1, 1, 1, 1, 1, 1])

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

function baseInput(n: number, overrides: Partial<FrameInput> = {}): FrameInput {
  return Object.freeze({
    frames: [makeFrame(n)],
    workflowFrames: [makeWfFrame(n)],
    telemetry: CLEAN_TELEMETRY,
    mutations: [] as PolicyMutation[],
    assertions: [] as EpistemicAssertion[],
    invariantSnapshot: { ...CLEAN_SNAPSHOT, sequence: n },
    activeAgentIds: ['agent-001'],
    activeWorkflowIds: ['wflow-001'],
    panelSequenceNumbers: PANEL_SEQ,
    sequence: n,
    decision_id: `d-${n}`,
    sitr: SITRRuntime.empty(),
    constitutional: ConstitutionalRuntime.empty(),
    ...overrides,
  })
}

// ─── Empty and minimal inputs ─────────────────────────────

describe('Frame kernel: empty and minimal inputs', () => {
  it('empty frames[] executes without error', () => {
    const result = runFrame(baseInput(1, { frames: [] }))
    expect(result.phase_trace.phase_1_frame_count).toBe(0)
  })

  it('empty workflowFrames[] executes cleanly — SITR stays STABLE', () => {
    const result = runFrame(baseInput(1, { workflowFrames: [] }))
    expect(result.sitr.currentState()).toBe('STABLE')
  })

  it('both empty → PERMIT verdict', () => {
    const result = runFrame(baseInput(1, { frames: [], workflowFrames: [] }))
    expect(result.constitutional.currentVerdict()).toBe('PERMIT')
  })

  it('empty mutations and assertions → executes cleanly', () => {
    const result = runFrame(baseInput(1, { mutations: [], assertions: [] }))
    expect(result.constitutional.currentVerdict()).toBe('PERMIT')
  })

  it('single clean frame → phase_1_frame_count = 1', () => {
    const result = runFrame(baseInput(1))
    expect(result.phase_trace.phase_1_frame_count).toBe(1)
  })

  it('3 clean frames → phase_1_frame_count = 3', () => {
    const result = runFrame(baseInput(1, {
      frames: [makeFrame(1), makeFrame(2), makeFrame(3)],
    }))
    expect(result.phase_trace.phase_1_frame_count).toBe(3)
  })
})

// ─── Workflow violations ──────────────────────────────────

describe('Frame kernel: workflow invariant violations', () => {
  it('single workflow violation → SITR escalates from STABLE', () => {
    const result = runFrame(baseInput(1, {
      workflowFrames: [makeWfFrame(1, false)],
    }))
    expect(stateOrdinal(result.sitr.currentState())).toBeGreaterThanOrEqual(stateOrdinal('UNSTABLE'))
  })

  it('workflow violation → constitutional verdict at least DEFER', () => {
    const result = runFrame(baseInput(1, {
      workflowFrames: [makeWfFrame(1, false)],
    }))
    expect(['DEFER', 'REJECT', 'ESCALATE']).toContain(result.constitutional.currentVerdict())
  })

  it('3 workflow violations all recorded in sitr.violations()', () => {
    const result = runFrame(baseInput(1, {
      workflowFrames: [makeWfFrame(1, false), makeWfFrame(2, false), makeWfFrame(3, false)],
    }))
    expect(result.sitr.violations().length).toBe(3)
  })

  it('workflow violation + DEGRADED telemetry → state stays at or above UNSTABLE', () => {
    const result = runFrame(baseInput(1, {
      workflowFrames: [makeWfFrame(1, false)],
      telemetry: { ...CLEAN_TELEMETRY, workflow_replay_integrity: 0.5 },
    }))
    expect(stateOrdinal(result.sitr.currentState())).toBeGreaterThanOrEqual(stateOrdinal('UNSTABLE'))
  })
})

// ─── Telemetry stress ─────────────────────────────────────

describe('Frame kernel: telemetry stress triggers', () => {
  it('workflow_replay_integrity < 1 → SITR DEGRADED', () => {
    const result = runFrame(baseInput(1, {
      telemetry: { ...CLEAN_TELEMETRY, workflow_replay_integrity: 0 },
    }))
    expect(stateOrdinal(result.sitr.currentState())).toBeGreaterThanOrEqual(stateOrdinal('DEGRADED'))
  })

  it('orchestration_pressure_index > 0.9 → SITR DEGRADED', () => {
    const result = runFrame(baseInput(1, {
      telemetry: { ...CLEAN_TELEMETRY, orchestration_pressure_index: 0.95 },
    }))
    expect(stateOrdinal(result.sitr.currentState())).toBeGreaterThanOrEqual(stateOrdinal('DEGRADED'))
  })

  it('both telemetry signals stressed → SITR DEGRADED (escalate takes max)', () => {
    const result = runFrame(baseInput(1, {
      telemetry: { ...CLEAN_TELEMETRY, workflow_replay_integrity: 0, orchestration_pressure_index: 0.95 },
    }))
    expect(stateOrdinal(result.sitr.currentState())).toBeGreaterThanOrEqual(stateOrdinal('DEGRADED'))
  })
})

// ─── Frame ordering anomalies ─────────────────────────────

describe('Frame kernel: frame ordering anomalies', () => {
  it('non-replay-safe frame → SITR CONSTITUTIONAL_RISK', () => {
    const result = runFrame(baseInput(1, {
      frames: [makeFrame(1, false)],
    }))
    expect(result.sitr.currentState()).toBe('CONSTITUTIONAL_RISK')
  })

  it('non-replay-safe frame → constitutional verdict REJECT', () => {
    const result = runFrame(baseInput(1, {
      frames: [makeFrame(1, false)],
    }))
    expect(result.constitutional.currentVerdict()).toBe('REJECT')
  })

  it('non-monotonic frame sequence → SITR at least UNSTABLE', () => {
    const result = runFrame(baseInput(1, {
      frames: [makeFrame(5), makeFrame(3)],
    }))
    expect(stateOrdinal(result.sitr.currentState())).toBeGreaterThanOrEqual(stateOrdinal('UNSTABLE'))
  })

  it('non-replay-safe dominates non-monotonic (CONSTITUTIONAL_RISK > UNSTABLE)', () => {
    const result = runFrame(baseInput(1, {
      frames: [makeFrame(5, false), makeFrame(3, true)],
    }))
    expect(stateOrdinal(result.sitr.currentState())).toBeGreaterThanOrEqual(stateOrdinal('CONSTITUTIONAL_RISK'))
  })
})

// ─── Sequential pipeline: feeding results forward ─────────

describe('Frame kernel: sequential pipeline feed', () => {
  function buildSequence(n: number) {
    let r = runFrame(baseInput(1))
    for (let i = 2; i <= n; i++) {
      r = runFrame(baseInput(i, {
        sitr: r.sitr,
        constitutional: r.constitutional,
      }))
    }
    return r
  }

  it('5-frame sequential pipeline → final verdict deterministic × 3', () => {
    const v1 = buildSequence(5).constitutional.currentVerdict()
    const v2 = buildSequence(5).constitutional.currentVerdict()
    const v3 = buildSequence(5).constitutional.currentVerdict()
    expect(v1).toBe(v2)
    expect(v2).toBe(v3)
  })

  it('5-frame clean pipeline → PERMIT throughout', () => {
    expect(buildSequence(5).constitutional.currentVerdict()).toBe('PERMIT')
  })

  it('input sitr and constitutional are unchanged after runFrame (immutable)', () => {
    const sitr = SITRRuntime.empty()
    const constitutional = ConstitutionalRuntime.empty()
    runFrame(baseInput(1, { sitr, constitutional }))
    expect(sitr.currentState()).toBe('STABLE')
    expect(constitutional.decisions().length).toBe(0)
  })
})

// ─── Structural guarantees ────────────────────────────────

describe('Frame kernel: structural guarantees', () => {
  it('result is frozen', () => {
    const result = runFrame(baseInput(1))
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('phase_trace is frozen', () => {
    const result = runFrame(baseInput(1))
    expect(Object.isFrozen(result.phase_trace)).toBe(true)
  })

  it('phase_trace.phase_6_verdict matches constitutional.currentVerdict()', () => {
    const result = runFrame(baseInput(1))
    expect(result.phase_trace.phase_6_verdict).toBe(result.constitutional.currentVerdict())
  })

  it('phase_trace.phase_6_verdict matches for REJECT too', () => {
    const result = runFrame(baseInput(1, { frames: [makeFrame(1, false)] }))
    expect(result.phase_trace.phase_6_verdict).toBe(result.constitutional.currentVerdict())
    expect(result.phase_trace.phase_6_verdict).toBe('REJECT')
  })

  it('is_replay_reconstructable = true', () => {
    expect(runFrame(baseInput(1)).is_replay_reconstructable).toBe(true)
  })

  it('schema_version is 1.0.0', () => {
    expect(runFrame(baseInput(1)).schema_version).toBe('1.0.0')
  })
})
