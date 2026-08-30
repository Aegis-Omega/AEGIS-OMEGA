// ============================================================
// Gate 50 — Constitutional Runtime Fuzz
// ~22 tests: verdict signal mapping across all valid SITR state /
//   AOIE global state / invariant combinations, decision log
//   accumulation law, telemetry computation, 20-frame determinism.
//
// Verdict lattice (ESCALATE > REJECT > DEFER > PERMIT):
//   SITR COMPROMISED | AOIE COMPROMISED | T0 violation → ESCALATE
//   SITR CONSTITUTIONAL_RISK | CONTAINED              → REJECT
//   SITR UNSTABLE | DEGRADED | AOIE ALERT             → DEFER
//   all clean                                         → PERMIT
//
// ConstitutionalRuntime.evaluate() takes an AOIEClassification
// object (not produced inline); we construct it directly to
// test all verdict branches without running the full AOIE engine.
// ============================================================

import { describe, it, expect } from 'vitest'
import { ConstitutionalRuntime } from '../../src/constitutional/runtime.js'
import { SITRRuntime } from '../../src/sitr/runtime.js'
import type { RuntimeSnapshot as InvariantRuntimeSnapshot } from '../../src/core/invariant-checker.js'
import type { AOIEClassification, GlobalState } from '../../src/aoie/types.js'
import type { CoordinationFrame } from '../../src/agents/types.js'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types.js'
import type { AgentTelemetrySnapshot } from '../../src/agents/telemetry/agent-telemetry.js'
import type { SHA256Hex } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

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

// T0_ABORT via INV-02: corruption_count must equal 0
const T0_SNAPSHOT: InvariantRuntimeSnapshot = Object.freeze({
  ...CLEAN_SNAPSHOT,
  corruption_count: 1,
})

// T0_ABORT via INV-05: gate_sealed must not be false
const T0_GATE_SNAPSHOT: InvariantRuntimeSnapshot = Object.freeze({
  ...CLEAN_SNAPSHOT,
  gate_sealed: false,
})

const CLEAN_TELEMETRY: AgentTelemetrySnapshot = Object.freeze({
  agent_coordination_stability: 1,
  workflow_replay_integrity: 1,
  workspace_memory_density: 0,
  extension_ecology_entropy: 0,
  mutation_chain_depth: 0,
  orchestration_pressure_index: 0,
})

function makeAOIE(globalState: GlobalState, n = 1): AOIEClassification {
  return Object.freeze({
    global_state: globalState,
    arbitration: 'RESOLVED' as const,
    identity_continuity: 'CONTINUOUS' as const,
    constitutional_drift: 'STABLE' as const,
    classified_at_sequence: n,
    is_replay_reconstructable: true as const,
    schema_version: '1.0.0' as const,
  })
}

// Build a SITRRuntime at a specific observable state
function sitrAt(state: 'STABLE' | 'DEGRADED' | 'UNSTABLE' | 'CONSTITUTIONAL_RISK'): SITRRuntime {
  const wfFrame = (n: number, satisfied: boolean): WorkflowReplayFrame => Object.freeze({
    frame_id: `wf-${n}`,
    workflow_id: 'wf-001',
    sequence: n,
    step_type: 'gather',
    input_hash: h('a'),
    output_hash: h('b'),
    invariant_satisfied: satisfied,
  })
  const frame = (n: number, replaySafe: boolean): CoordinationFrame => Object.freeze({
    frame_id: `f-${n}`,
    sequence: n,
    agent_id: 'a-001',
    action_type: 'observe',
    mutation_ids: [],
    replay_safe: replaySafe,
  })
  const degradedTelemetry: AgentTelemetrySnapshot = Object.freeze({
    ...CLEAN_TELEMETRY, workflow_replay_integrity: 0,
  })
  const s = SITRRuntime.empty()
  switch (state) {
    case 'STABLE': return s
    case 'DEGRADED':
      return s.observe({ frames: [frame(1, true)], workflowFrames: [wfFrame(1, true)], telemetry: degradedTelemetry, sequence: 1 })
    case 'UNSTABLE':
      return s.observe({ frames: [frame(1, true)], workflowFrames: [wfFrame(1, false)], telemetry: CLEAN_TELEMETRY, sequence: 1 })
    case 'CONSTITUTIONAL_RISK':
      return s.observe({ frames: [frame(1, false)], workflowFrames: [wfFrame(1, true)], telemetry: CLEAN_TELEMETRY, sequence: 1 })
  }
}

function evalVerdict(
  sitr: SITRRuntime,
  aoie: AOIEClassification,
  snapshot: InvariantRuntimeSnapshot = CLEAN_SNAPSHOT,
  n = 1,
) {
  return ConstitutionalRuntime.empty()
    .evaluate({ sitr, aoie, invariantSnapshot: { ...snapshot, sequence: n }, sequence: n, decision_id: `d-${n}` })
    .currentVerdict()
}

// ─── Verdict signal mapping ────────────────────────────────

describe('Constitutional verdict: signal mapping', () => {
  it('SITR STABLE + AOIE SECURE + clean → PERMIT', () => {
    expect(evalVerdict(sitrAt('STABLE'), makeAOIE('SECURE'))).toBe('PERMIT')
  })

  it('SITR DEGRADED + AOIE SECURE + clean → DEFER', () => {
    expect(evalVerdict(sitrAt('DEGRADED'), makeAOIE('SECURE'))).toBe('DEFER')
  })

  it('SITR UNSTABLE + AOIE SECURE + clean → DEFER', () => {
    expect(evalVerdict(sitrAt('UNSTABLE'), makeAOIE('SECURE'))).toBe('DEFER')
  })

  it('SITR CONSTITUTIONAL_RISK + AOIE SECURE + clean → REJECT', () => {
    expect(evalVerdict(sitrAt('CONSTITUTIONAL_RISK'), makeAOIE('SECURE'))).toBe('REJECT')
  })

  it('SITR STABLE + AOIE ALERT + clean → DEFER', () => {
    expect(evalVerdict(sitrAt('STABLE'), makeAOIE('ALERT'))).toBe('DEFER')
  })

  it('SITR STABLE + AOIE COMPROMISED + clean → ESCALATE', () => {
    expect(evalVerdict(sitrAt('STABLE'), makeAOIE('COMPROMISED'))).toBe('ESCALATE')
  })

  it('SITR STABLE + AOIE SECURE + T0 violation (corruption_count=1) → ESCALATE', () => {
    expect(evalVerdict(sitrAt('STABLE'), makeAOIE('SECURE'), T0_SNAPSHOT)).toBe('ESCALATE')
  })

  it('SITR STABLE + AOIE SECURE + T0 violation (gate_sealed=false) → ESCALATE', () => {
    expect(evalVerdict(sitrAt('STABLE'), makeAOIE('SECURE'), T0_GATE_SNAPSHOT)).toBe('ESCALATE')
  })

  it('SITR CONSTITUTIONAL_RISK + AOIE COMPROMISED → ESCALATE (ESCALATE > REJECT)', () => {
    expect(evalVerdict(sitrAt('CONSTITUTIONAL_RISK'), makeAOIE('COMPROMISED'))).toBe('ESCALATE')
  })

  it('SITR DEGRADED + AOIE COMPROMISED → ESCALATE (ESCALATE > DEFER)', () => {
    expect(evalVerdict(sitrAt('DEGRADED'), makeAOIE('COMPROMISED'))).toBe('ESCALATE')
  })
})

// ─── Decision log accumulation ─────────────────────────────

describe('Constitutional decision log: accumulation law', () => {
  it('5 evaluate calls → 5 decisions', () => {
    let runtime = ConstitutionalRuntime.empty()
    const sitr = sitrAt('STABLE')
    const aoie = makeAOIE('SECURE')
    for (let i = 1; i <= 5; i++) {
      runtime = runtime.evaluate({ sitr, aoie, invariantSnapshot: { ...CLEAN_SNAPSHOT, sequence: i }, sequence: i, decision_id: `d-${i}` })
    }
    expect(runtime.decisions().length).toBe(5)
  })

  it('reject_count tracks REJECT decisions correctly', () => {
    let runtime = ConstitutionalRuntime.empty()
    const sitrReject = sitrAt('CONSTITUTIONAL_RISK')
    const sitrClean = sitrAt('STABLE')
    const aoie = makeAOIE('SECURE')
    for (let i = 1; i <= 3; i++) {
      runtime = runtime.evaluate({ sitr: sitrReject, aoie, invariantSnapshot: { ...CLEAN_SNAPSHOT, sequence: i }, sequence: i, decision_id: `d-${i}` })
    }
    for (let i = 4; i <= 6; i++) {
      runtime = runtime.evaluate({ sitr: sitrClean, aoie, invariantSnapshot: { ...CLEAN_SNAPSHOT, sequence: i }, sequence: i, decision_id: `d-${i}` })
    }
    const state = runtime.decisions()
    const rejectCount = state.filter(d => d.verdict === 'REJECT').length
    expect(rejectCount).toBe(3)
  })

  it('escalation_count tracks ESCALATE decisions correctly', () => {
    let runtime = ConstitutionalRuntime.empty()
    const sitr = sitrAt('STABLE')
    for (let i = 1; i <= 4; i++) {
      const aoie = i <= 2 ? makeAOIE('COMPROMISED', i) : makeAOIE('SECURE', i)
      runtime = runtime.evaluate({ sitr, aoie, invariantSnapshot: { ...CLEAN_SNAPSHOT, sequence: i }, sequence: i, decision_id: `d-${i}` })
    }
    const escalationCount = runtime.decisions().filter(d => d.verdict === 'ESCALATE').length
    expect(escalationCount).toBe(2)
  })

  it('source ConstitutionalRuntime is unchanged after evaluate (immutable)', () => {
    const original = ConstitutionalRuntime.empty()
    const sitr = sitrAt('STABLE')
    const aoie = makeAOIE('SECURE')
    original.evaluate({ sitr, aoie, invariantSnapshot: CLEAN_SNAPSHOT, sequence: 1, decision_id: 'd-1' })
    expect(original.decisions().length).toBe(0)
    expect(original.currentVerdict()).toBe('PERMIT')
  })

  it('decisions() entries carry is_replay_reconstructable=true', () => {
    let runtime = ConstitutionalRuntime.empty()
    runtime = runtime.evaluate({ sitr: sitrAt('STABLE'), aoie: makeAOIE('SECURE'), invariantSnapshot: CLEAN_SNAPSHOT, sequence: 1, decision_id: 'd-1' })
    expect(runtime.decisions()[0]?.is_replay_reconstructable).toBe(true)
  })
})

// ─── Telemetry ─────────────────────────────────────────────

describe('Constitutional telemetry', () => {
  it('governance_throughput is non-negative', () => {
    let runtime = ConstitutionalRuntime.empty(1)
    const sitr = sitrAt('STABLE')
    const aoie = makeAOIE('SECURE')
    for (let i = 1; i <= 5; i++) {
      runtime = runtime.evaluate({ sitr, aoie, invariantSnapshot: { ...CLEAN_SNAPSHOT, sequence: i }, sequence: i, decision_id: `d-${i}` })
    }
    const tel = runtime.telemetry(6)
    expect(tel.governance_throughput).toBeGreaterThanOrEqual(0)
    expect(tel.decision_count).toBe(5)
  })

  it('convergenceDepth is non-negative', () => {
    let runtime = ConstitutionalRuntime.empty()
    const sitr = sitrAt('STABLE')
    const aoie = makeAOIE('SECURE')
    for (let i = 1; i <= 3; i++) {
      runtime = runtime.evaluate({ sitr, aoie, invariantSnapshot: { ...CLEAN_SNAPSHOT, sequence: i }, sequence: i, decision_id: `d-${i}` })
    }
    expect(runtime.convergenceDepth()).toBeGreaterThanOrEqual(0)
  })
})

// ─── Determinism ──────────────────────────────────────────

describe('Constitutional verdict: determinism', () => {
  function run20(): string {
    let runtime = ConstitutionalRuntime.empty()
    const sitrClean = sitrAt('STABLE')
    const sitrStress = sitrAt('CONSTITUTIONAL_RISK')
    for (let i = 1; i <= 20; i++) {
      const sitr = i % 5 === 0 ? sitrStress : sitrClean
      const aoie = i % 7 === 0 ? makeAOIE('ALERT', i) : makeAOIE('SECURE', i)
      runtime = runtime.evaluate({ sitr, aoie, invariantSnapshot: { ...CLEAN_SNAPSHOT, sequence: i }, sequence: i, decision_id: `d-${i}` })
    }
    return runtime.decisions().map(d => d.verdict).join(',')
  }

  it('20-frame alternating stress sequence → same verdict sequence × 3', () => {
    const r1 = run20()
    const r2 = run20()
    const r3 = run20()
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
  })

  it('20-frame sequence contains expected mix of verdicts', () => {
    const verdicts = run20().split(',')
    expect(verdicts.filter(v => v === 'PERMIT').length).toBeGreaterThan(0)
    expect(verdicts.filter(v => v === 'REJECT').length).toBeGreaterThan(0)
  })
})
