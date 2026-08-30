// ============================================================
// Gate 12 — SITR Constitutional Runtime Defense Tests
// ~20 tests: runtime lifecycle, lattice, intervention log,
//   replay violations, orchestration anomaly detection, telemetry
// ============================================================

import { describe, it, expect } from 'vitest'
import type { CoordinationFrame } from '../../src/agents/types'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types'
import type { AgentTelemetrySnapshot } from '../../src/agents/telemetry/agent-telemetry'
import type { ContainmentDirective, InterventionRecord, ReplayViolation } from '../../src/sitr/types'
import { SITRConstraintError } from '../../src/sitr/types.js'
import {
  SITR_ESCALATION_ORDER,
  stateOrdinal,
  canEscalateTo,
  escalate,
  isTerminalState,
  compareStates,
} from '../../src/sitr/lattice.js'
import { buildSITRTelemetry, computeEscalationRate } from '../../src/sitr/telemetry.js'
import { InterventionLog } from '../../src/sitr/intervention.js'
import { ReplayViolationLog } from '../../src/sitr/replay.js'
import { detectOrchestrationAnomalies, anomalyToRequiredState } from '../../src/sitr/orchestration.js'
import { SITRRuntime } from '../../src/sitr/runtime.js'
import type { SHA256Hex } from '../../src/core/types'

// ─── Test helpers ──────────────────────────────────────────

const mockHash = (s: string) => s.padEnd(64, '0') as SHA256Hex

const CLEAN_TELEMETRY: AgentTelemetrySnapshot = Object.freeze({
  agent_coordination_stability: 1,
  workflow_replay_integrity: 1,
  workspace_memory_density: 0,
  extension_ecology_entropy: 0,
  mutation_chain_depth: 0,
  orchestration_pressure_index: 0,
})

function makeFrame(overrides: Partial<CoordinationFrame> = {}): CoordinationFrame {
  return Object.freeze({
    frame_id: 'f1',
    sequence: 1,
    agent_id: 'a1',
    action_type: 'observe',
    mutation_ids: [],
    replay_safe: true,
    ...overrides,
  })
}

function makeWfFrame(overrides: Partial<WorkflowReplayFrame> = {}): WorkflowReplayFrame {
  return Object.freeze({
    frame_id: 'wf1',
    workflow_id: 'wflow1',
    sequence: 1,
    step_type: 'gather',
    input_hash: mockHash('in'),
    output_hash: mockHash('out'),
    invariant_satisfied: true,
    ...overrides,
  })
}

function makeInterventionRecord(seq: number): InterventionRecord {
  return Object.freeze({
    record_id: `rec-${seq}`,
    sequence: seq,
    prior_state: 'STABLE' as const,
    next_state: 'DEGRADED' as const,
    trigger: 'test',
    directive_ids: [],
    is_replay_reconstructable: true as const,
  })
}

function makeViolation(seq: number): ReplayViolation {
  return Object.freeze({
    violation_id: `viol-${seq}`,
    sequence: seq,
    violation_type: 'invariant_not_satisfied',
  })
}

// ─── Escalation Lattice ────────────────────────────────────

describe('SITR lattice', () => {
  it('escalation order has 6 states', () => {
    expect(SITR_ESCALATION_ORDER).toHaveLength(6)
    expect(SITR_ESCALATION_ORDER[0]).toBe('STABLE')
    expect(SITR_ESCALATION_ORDER[5]).toBe('COMPROMISED')
  })

  it('stateOrdinal is strictly increasing across escalation order', () => {
    for (let i = 1; i < SITR_ESCALATION_ORDER.length; i++) {
      const prev = SITR_ESCALATION_ORDER[i - 1]!
      const curr = SITR_ESCALATION_ORDER[i]!
      expect(stateOrdinal(curr)).toBeGreaterThan(stateOrdinal(prev))
    }
  })

  it('canEscalateTo: lower → higher is true; higher → lower is false', () => {
    expect(canEscalateTo('STABLE', 'DEGRADED')).toBe(true)
    expect(canEscalateTo('COMPROMISED', 'STABLE')).toBe(false)
    expect(canEscalateTo('STABLE', 'STABLE')).toBe(false)
  })

  it('escalate returns higher state', () => {
    expect(escalate('STABLE', 'UNSTABLE')).toBe('UNSTABLE')
    expect(escalate('CONSTITUTIONAL_RISK', 'DEGRADED')).toBe('CONSTITUTIONAL_RISK')
  })

  it('isTerminalState: only COMPROMISED is terminal', () => {
    expect(isTerminalState('COMPROMISED')).toBe(true)
    expect(isTerminalState('CONTAINED')).toBe(false)
    expect(isTerminalState('STABLE')).toBe(false)
  })

  it('compareStates returns correct ordering', () => {
    expect(compareStates('STABLE', 'DEGRADED')).toBe(-1)
    expect(compareStates('DEGRADED', 'STABLE')).toBe(1)
    expect(compareStates('UNSTABLE', 'UNSTABLE')).toBe(0)
  })
})

// ─── Telemetry ─────────────────────────────────────────────

describe('SITR telemetry', () => {
  it('escalation_rate is 0 when no interventions', () => {
    expect(computeEscalationRate(0, 100)).toBe(0)
    expect(computeEscalationRate(0, 0)).toBe(0)
  })

  it('escalation_rate is bounded [0,1]', () => {
    expect(computeEscalationRate(1000, 1)).toBe(1)
    expect(computeEscalationRate(1, 10)).toBeLessThanOrEqual(1)
  })

  it('buildSITRTelemetry returns all fields', () => {
    const t = buildSITRTelemetry({
      currentState: 'DEGRADED',
      interventionCount: 2,
      containmentActionsTaken: 1,
      replayViolationsDetected: 0,
      orchestrationAnomaliesDetected: 0,
      totalSequences: 10,
    })
    expect(t.current_state).toBe('DEGRADED')
    expect(typeof t.escalation_rate).toBe('number')
    expect(t.intervention_count).toBe(2)
  })
})

// ─── InterventionLog ───────────────────────────────────────

describe('InterventionLog', () => {
  it('starts empty', () => {
    expect(InterventionLog.empty().length).toBe(0)
  })

  it('append-only: returns new instance, source unchanged', () => {
    const l0 = InterventionLog.empty()
    const l1 = l0.append(makeInterventionRecord(1))
    expect(l0.length).toBe(0)
    expect(l1.length).toBe(1)
  })

  it('monotonic sequence enforced; throws SITRConstraintError', () => {
    const l = InterventionLog.empty().append(makeInterventionRecord(10))
    expect(() => l.append(makeInterventionRecord(5))).toThrowError(SITRConstraintError)
  })
})

// ─── ReplayViolationLog ────────────────────────────────────

describe('ReplayViolationLog', () => {
  it('starts empty, hasViolations = false', () => {
    const v = ReplayViolationLog.empty()
    expect(v.hasViolations()).toBe(false)
    expect(v.violationCount).toBe(0)
  })

  it('record returns new instance; hasViolations = true', () => {
    const v0 = ReplayViolationLog.empty()
    const v1 = v0.record(makeViolation(1))
    expect(v0.hasViolations()).toBe(false)
    expect(v1.hasViolations()).toBe(true)
    expect(v1.violationCount).toBe(1)
  })

  it('violations are permanent — accumulated across calls', () => {
    const v = ReplayViolationLog.empty()
      .record(makeViolation(1))
      .record(makeViolation(2))
    expect(v.violationCount).toBe(2)
  })
})

// ─── Orchestration Anomaly Detection ───────────────────────

describe('detectOrchestrationAnomalies', () => {
  it('returns empty for clean frames', () => {
    const frames = [makeFrame({ frame_id: 'f1', sequence: 1 }), makeFrame({ frame_id: 'f2', sequence: 2 })]
    expect(detectOrchestrationAnomalies(frames, 2)).toHaveLength(0)
  })

  it('detects non-replay-safe frame as critical anomaly', () => {
    const frames = [makeFrame({ replay_safe: false })]
    const anomalies = detectOrchestrationAnomalies(frames, 1)
    expect(anomalies.length).toBeGreaterThan(0)
    expect(anomalies[0]?.severity).toBe('critical')
  })

  it('detects non-monotonic frame sequence as high anomaly', () => {
    const frames = [
      makeFrame({ frame_id: 'f1', sequence: 5 }),
      makeFrame({ frame_id: 'f2', sequence: 3 }),
    ]
    const anomalies = detectOrchestrationAnomalies(frames, 10)
    expect(anomalies.some(a => a.anomaly_type === 'non_monotonic_frame_sequence')).toBe(true)
  })

  it('anomalyToRequiredState maps critical → CONSTITUTIONAL_RISK', () => {
    const anomaly = detectOrchestrationAnomalies([makeFrame({ replay_safe: false })], 1)[0]!
    expect(anomalyToRequiredState(anomaly)).toBe('CONSTITUTIONAL_RISK')
  })
})

// ─── SITRRuntime ───────────────────────────────────────────

describe('SITRRuntime', () => {
  it('starts STABLE', () => {
    expect(SITRRuntime.empty().currentState()).toBe('STABLE')
  })

  it('observe with clean signals stays STABLE', () => {
    const r = SITRRuntime.empty().observe({
      frames: [makeFrame()],
      workflowFrames: [makeWfFrame()],
      telemetry: CLEAN_TELEMETRY,
      sequence: 1,
    })
    expect(r.currentState()).toBe('STABLE')
  })

  it('non-replay-safe frame escalates to CONSTITUTIONAL_RISK', () => {
    const r = SITRRuntime.empty().observe({
      frames: [makeFrame({ replay_safe: false })],
      workflowFrames: [],
      telemetry: CLEAN_TELEMETRY,
      sequence: 1,
    })
    expect(r.currentState()).toBe('CONSTITUTIONAL_RISK')
  })

  it('invariant_satisfied=false in workflow frame escalates to UNSTABLE', () => {
    const r = SITRRuntime.empty().observe({
      frames: [],
      workflowFrames: [makeWfFrame({ invariant_satisfied: false })],
      telemetry: CLEAN_TELEMETRY,
      sequence: 1,
    })
    expect(r.currentState()).toBe('UNSTABLE')
    expect(r.violations()).toHaveLength(1)
  })

  it('high orchestration pressure escalates to DEGRADED', () => {
    const r = SITRRuntime.empty().observe({
      frames: [],
      workflowFrames: [],
      telemetry: { ...CLEAN_TELEMETRY, orchestration_pressure_index: 0.95 },
      sequence: 1,
    })
    expect(r.currentState()).toBe('DEGRADED')
  })

  it('issueDirective appends without changing state; original unchanged', () => {
    const r0 = SITRRuntime.empty()
    const directive: ContainmentDirective = Object.freeze({
      directive_id: 'd1',
      sequence: 1,
      action: 'quarantine_agent' as const,
      target_id: 'agent-001',
      reason: 'test',
      is_replay_reconstructable: true as const,
    })
    const r1 = r0.issueDirective(directive)
    expect(r0.interventions()).toHaveLength(0)
    expect(r1.interventions()).toHaveLength(0)  // directives don't auto-create records
    expect(r1.currentState()).toBe('STABLE')
  })

  it('observe 3× with identical params produces identical state (determinism)', () => {
    const params = {
      frames: [makeFrame({ frame_id: 'x', sequence: 2 })],
      workflowFrames: [makeWfFrame()],
      telemetry: CLEAN_TELEMETRY,
      sequence: 2,
    }
    const r1 = SITRRuntime.empty().observe(params).currentState()
    const r2 = SITRRuntime.empty().observe(params).currentState()
    const r3 = SITRRuntime.empty().observe(params).currentState()
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
  })
})
