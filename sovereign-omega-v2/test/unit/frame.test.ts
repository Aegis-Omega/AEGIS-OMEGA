// ============================================================
// Gate 14 — Frame Execution Kernel Tests
// ~20 tests: enforcement engine, snapshot factory, directive
//   generator, kernel composition, determinism, phase trace
// ============================================================

import { describe, it, expect } from 'vitest'
import type { CoordinationFrame } from '../../src/agents/types'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types'
import type { AgentTelemetrySnapshot } from '../../src/agents/telemetry/agent-telemetry'
import type { ContainmentDirective } from '../../src/sitr/types'
import type { RuntimeSnapshot as InvariantRuntimeSnapshot } from '../../src/core/invariant-checker'
import type { PolicyMutation, EpistemicAssertion } from '../../src/aoie/types'
import { SITRRuntime } from '../../src/sitr/runtime.js'
import { ConstitutionalRuntime } from '../../src/constitutional/runtime.js'
import { applyDirectives } from '../../src/enforcement/engine.js'
import { capturePostEnforcementSnapshot } from '../../src/frame/snapshot.js'
import { computeAutoDirectives } from '../../src/frame/directives.js'
import { runFrame } from '../../src/frame/kernel.js'
import { SHP_PHASES, SHP_LOOP, SHP_COMMITMENT_BOUNDARY, toRalphTrace } from '../../src/frame/shp.js'
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

const CLEAN_INVARIANT_SNAPSHOT: InvariantRuntimeSnapshot = {
  vcg_error: 0,
  drift_index: 0,
  corruption_count: 0,
  pgcs_passes: true,
  calibrator_passes: true,
  failsafe_state: 'healthy',
  sequence: 1,
  gate_sealed: true,
}

const PANEL_SEQ = Object.freeze([1, 1, 1, 1, 1, 1, 1, 1, 1, 1])

function makeFrame(overrides: Partial<CoordinationFrame> = {}): CoordinationFrame {
  return Object.freeze({
    frame_id: 'f1',
    sequence: 1,
    agent_id: 'agent-001',
    action_type: 'observe',
    mutation_ids: [],
    replay_safe: true,
    ...overrides,
  })
}

function makeWfFrame(overrides: Partial<WorkflowReplayFrame> = {}): WorkflowReplayFrame {
  return Object.freeze({
    frame_id: 'wf1',
    workflow_id: 'wflow-001',
    sequence: 1,
    step_type: 'gather',
    input_hash: mockHash('in'),
    output_hash: mockHash('out'),
    invariant_satisfied: true,
    ...overrides,
  })
}

function makeDirective(overrides: Partial<ContainmentDirective> = {}): ContainmentDirective {
  return Object.freeze({
    directive_id: 'dir-001',
    sequence: 1,
    action: 'quarantine_agent' as const,
    target_id: 'agent-001',
    reason: 'test',
    is_replay_reconstructable: true as const,
    ...overrides,
  })
}

const BASE_FRAME_INPUT = {
  frames: [makeFrame()],
  workflowFrames: [makeWfFrame()],
  telemetry: CLEAN_TELEMETRY,
  mutations: [] as PolicyMutation[],
  assertions: [] as EpistemicAssertion[],
  invariantSnapshot: CLEAN_INVARIANT_SNAPSHOT,
  activeAgentIds: ['agent-001'],
  activeWorkflowIds: ['wflow-001'],
  panelSequenceNumbers: PANEL_SEQ,
  sequence: 1,
  decision_id: 'd-001',
}

// ─── Enforcement Engine ────────────────────────────────────

describe('applyDirectives', () => {
  it('empty directives → zero applied, empty decisions', () => {
    const r = applyDirectives([], [], [], 1)
    expect(r.directives_applied).toBe(0)
    expect(r.directives_skipped).toBe(0)
    expect(r.decisions).toHaveLength(0)
    expect(r.is_replay_reconstructable).toBe(true)
  })

  it('quarantine_agent: APPLIED when agent is active', () => {
    const r = applyDirectives([makeDirective()], ['agent-001'], [], 1)
    expect(r.decisions[0]?.outcome).toBe('APPLIED')
    expect(r.directives_applied).toBe(1)
  })

  it('quarantine_agent: SKIPPED when agent not in active set', () => {
    const r = applyDirectives([makeDirective({ target_id: 'unknown-agent' })], ['agent-001'], [], 1)
    expect(r.decisions[0]?.outcome).toBe('SKIPPED')
    expect(r.directives_skipped).toBe(1)
  })

  it('freeze_workflow: APPLIED when workflow is active', () => {
    const d = makeDirective({ action: 'freeze_workflow', target_id: 'wflow-001' })
    const r = applyDirectives([d], [], ['wflow-001'], 1)
    expect(r.decisions[0]?.outcome).toBe('APPLIED')
  })

  it('block_frame: unconditionally APPLIED', () => {
    const d = makeDirective({ action: 'block_frame', target_id: 'f1' })
    const r = applyDirectives([d], [], [], 1)
    expect(r.decisions[0]?.outcome).toBe('APPLIED')
  })

  it('invalidate_replay_chain: unconditionally APPLIED', () => {
    const d = makeDirective({ action: 'invalidate_replay_chain', target_id: 'wflow-001' })
    const r = applyDirectives([d], [], [], 1)
    expect(r.decisions[0]?.outcome).toBe('APPLIED')
  })

  it('result is frozen and carries schema_version', () => {
    const r = applyDirectives([], [], [], 1)
    expect(Object.isFrozen(r)).toBe(true)
    expect(r.schema_version).toBe('1.0.0')
  })
})

// ─── Snapshot Factory ──────────────────────────────────────

describe('capturePostEnforcementSnapshot', () => {
  const baseEnforcement = applyDirectives([], [], [], 1)

  it('returns snapshot with phase=post_enforcement', () => {
    const s = capturePostEnforcementSnapshot({
      enforcement_result: baseEnforcement,
      sitr_state: 'STABLE',
      panel_sequence_numbers: PANEL_SEQ,
      sequence: 1,
    })
    expect(s.phase).toBe('post_enforcement')
  })

  it('snapshot is frozen with correct schema_version', () => {
    const s = capturePostEnforcementSnapshot({
      enforcement_result: baseEnforcement,
      sitr_state: 'STABLE',
      panel_sequence_numbers: PANEL_SEQ,
      sequence: 1,
    })
    expect(Object.isFrozen(s)).toBe(true)
    expect(s.schema_version).toBe('1.0.0')
  })

  it('state_hash is deterministic for same inputs', () => {
    const params = {
      enforcement_result: baseEnforcement,
      sitr_state: 'STABLE' as const,
      panel_sequence_numbers: PANEL_SEQ,
      sequence: 1,
    }
    const s1 = capturePostEnforcementSnapshot(params)
    const s2 = capturePostEnforcementSnapshot(params)
    expect(s1.state_hash).toBe(s2.state_hash)
  })

  it('different sitr_state produces different state_hash', () => {
    const stable = capturePostEnforcementSnapshot({ enforcement_result: baseEnforcement, sitr_state: 'STABLE', panel_sequence_numbers: PANEL_SEQ, sequence: 1 })
    const degraded = capturePostEnforcementSnapshot({ enforcement_result: baseEnforcement, sitr_state: 'DEGRADED', panel_sequence_numbers: PANEL_SEQ, sequence: 1 })
    expect(stable.state_hash).not.toBe(degraded.state_hash)
  })
})

// ─── Auto-Directive Generator ──────────────────────────────

describe('computeAutoDirectives', () => {
  it('clean frames produce no directives', () => {
    expect(computeAutoDirectives([makeFrame()], [makeWfFrame()], 1)).toHaveLength(0)
  })

  it('non-replay-safe frame generates quarantine_agent directive', () => {
    const ds = computeAutoDirectives([makeFrame({ replay_safe: false, agent_id: 'a1' })], [], 1)
    expect(ds).toHaveLength(1)
    expect(ds[0]?.action).toBe('quarantine_agent')
    expect(ds[0]?.target_id).toBe('a1')
    expect(ds[0]?.is_replay_reconstructable).toBe(true)
  })

  it('workflow invariant failure generates invalidate_replay_chain directive', () => {
    const ds = computeAutoDirectives([], [makeWfFrame({ invariant_satisfied: false, workflow_id: 'wf-x' })], 1)
    expect(ds).toHaveLength(1)
    expect(ds[0]?.action).toBe('invalidate_replay_chain')
    expect(ds[0]?.target_id).toBe('wf-x')
  })

  it('directive IDs are deterministic (3 runs same inputs)', () => {
    const frames = [makeFrame({ replay_safe: false, agent_id: 'a1' })]
    const r1 = computeAutoDirectives(frames, [], 1)
    const r2 = computeAutoDirectives(frames, [], 1)
    const r3 = computeAutoDirectives(frames, [], 1)
    expect(r1[0]?.directive_id).toBe(r2[0]?.directive_id)
    expect(r2[0]?.directive_id).toBe(r3[0]?.directive_id)
  })
})

// ─── runFrame kernel ───────────────────────────────────────

describe('runFrame', () => {
  it('clean frame → PERMIT verdict, SECURE aoie, STABLE sitr', () => {
    const result = runFrame({
      ...BASE_FRAME_INPUT,
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    expect(result.constitutional.currentVerdict()).toBe('PERMIT')
    expect(result.aoie.global_state).toBe('SECURE')
    expect(result.sitr.currentState()).toBe('STABLE')
  })

  it('non-replay-safe frame escalates to CONSTITUTIONAL_RISK + REJECT verdict', () => {
    const result = runFrame({
      ...BASE_FRAME_INPUT,
      frames: [makeFrame({ replay_safe: false })],
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    expect(result.sitr.currentState()).toBe('CONSTITUTIONAL_RISK')
    expect(result.constitutional.currentVerdict()).toBe('REJECT')
  })

  it('workflow invariant failure escalates to UNSTABLE + DEFER verdict', () => {
    const result = runFrame({
      ...BASE_FRAME_INPUT,
      workflowFrames: [makeWfFrame({ invariant_satisfied: false })],
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    expect(result.sitr.currentState()).toBe('UNSTABLE')
    expect(result.constitutional.currentVerdict()).toBe('DEFER')
  })

  it('T0 invariant violation → ESCALATE verdict', () => {
    const result = runFrame({
      ...BASE_FRAME_INPUT,
      invariantSnapshot: { ...CLEAN_INVARIANT_SNAPSHOT, corruption_count: 1 },
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    expect(result.constitutional.currentVerdict()).toBe('ESCALATE')
  })

  it('phase_trace reflects all phase outcomes', () => {
    const result = runFrame({
      ...BASE_FRAME_INPUT,
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    const t = result.phase_trace
    expect(t.phase_1_frame_count).toBe(1)
    expect(t.phase_5_aoie_global_state).toBe('SECURE')
    expect(t.phase_6_verdict).toBe('PERMIT')
    expect(t.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(t)).toBe(true)
  })

  it('result has is_replay_reconstructable + schema_version', () => {
    const result = runFrame({
      ...BASE_FRAME_INPUT,
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    expect(result.is_replay_reconstructable).toBe(true)
    expect(result.schema_version).toBe('1.0.0')
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('deterministic: 3 runs identical inputs → identical aoie + verdict', () => {
    const make = () => runFrame({
      ...BASE_FRAME_INPUT,
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    const r1 = make()
    const r2 = make()
    const r3 = make()
    expect(JSON.stringify(r1.aoie)).toBe(JSON.stringify(r2.aoie))
    expect(JSON.stringify(r2.aoie)).toBe(JSON.stringify(r3.aoie))
    expect(r1.constitutional.currentVerdict()).toBe(r2.constitutional.currentVerdict())
    expect(r2.constitutional.currentVerdict()).toBe(r3.constitutional.currentVerdict())
  })

  it('enforcement directives flow into phase_trace counts', () => {
    const result = runFrame({
      ...BASE_FRAME_INPUT,
      frames: [makeFrame({ replay_safe: false, agent_id: 'agent-001' })],
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    expect(result.phase_trace.phase_3_directives_emitted).toBe(1)
    expect(result.phase_trace.phase_4_directives_applied).toBe(1)
  })
})

// ─── SHP Identity ──────────────────────────────────────────

describe('SHP execution identity', () => {
  it('SHP_LOOP is the canonical R→A→L→P→H string', () => {
    expect(SHP_LOOP).toBe('R→A→L→P→H')
  })

  it('SHP_COMMITMENT_BOUNDARY is LOCK', () => {
    expect(SHP_COMMITMENT_BOUNDARY).toBe('LOCK')
  })

  it('ASSESS is pre-commit; PROPAGATE is post-commit', () => {
    expect(SHP_PHASES.ASSESS.pre_commit).toBe(true)
    expect(SHP_PHASES.ASSESS.post_commit).toBe(false)
    expect(SHP_PHASES.PROPAGATE.pre_commit).toBe(false)
    expect(SHP_PHASES.PROPAGATE.post_commit).toBe(true)
  })

  it('phase numbers preserve temporal order: READ < ASSESS < LOCK < PROPAGATE < HARMONIZE', () => {
    expect(SHP_PHASES.READ.phase_number).toBeLessThan(SHP_PHASES.ASSESS.phase_number)
    expect(SHP_PHASES.ASSESS.phase_number).toBeLessThan(SHP_PHASES.LOCK.phase_number)
    expect(SHP_PHASES.LOCK.phase_number).toBeLessThan(SHP_PHASES.PROPAGATE.phase_number)
    expect(SHP_PHASES.PROPAGATE.phase_number).toBeLessThan(SHP_PHASES.HARMONIZE.phase_number)
  })

  it('toRalphTrace maps clean runFrame result to correct RALPH fields', () => {
    const result = runFrame({
      ...BASE_FRAME_INPUT,
      sitr: SITRRuntime.empty(),
      constitutional: ConstitutionalRuntime.empty(),
    })
    const trace = toRalphTrace(result)
    expect(trace.loop).toBe(SHP_LOOP)
    expect(trace.READ.frame_count).toBe(1)
    expect(trace.ASSESS.sitr_state).toBe('STABLE')
    expect(trace.PROPAGATE.aoie_global_state).toBe('SECURE')
    expect(trace.HARMONIZE.verdict).toBe('PERMIT')
    expect(trace.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(trace)).toBe(true)
  })
})
