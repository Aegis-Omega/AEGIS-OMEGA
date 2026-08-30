// ============================================================
// Gate 53 — Enforcement Engine Adversarial
// ~22 tests: applyDirectives() for all 5 ContainmentAction types
//   including gaps vs unit tests (freeze_workflow SKIPPED,
//   elevate_state unconditional), mixed APPLIED/SKIPPED count
//   accuracy, 20-directive batches, capturePostEnforcementSnapshot
//   hash sensitivity matrix, computeAutoDirectives edge cases.
//
// Gaps filled vs test/unit/frame.test.ts:
//   - freeze_workflow with workflow NOT in active set → SKIPPED
//   - elevate_state → unconditionally APPLIED (not tested in unit)
//   - directives_applied + directives_skipped === decisions.length
//   - 20-directive all-APPLIED and all-SKIPPED batches
//   - capturePostEnforcementSnapshot: directives_applied change →
//     different state_hash; sequence change → different state_hash
//   - computeAutoDirectives: multiple violations → directive count
//     equals violation count; empty inputs → empty array
// ============================================================

import { describe, it, expect } from 'vitest'
import { applyDirectives } from '../../src/enforcement/engine.js'
import { capturePostEnforcementSnapshot } from '../../src/frame/snapshot.js'
import { computeAutoDirectives } from '../../src/frame/directives.js'
import type { ContainmentDirective } from '../../src/sitr/types.js'
import type { CoordinationFrame } from '../../src/agents/types.js'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types.js'
import type { SHA256Hex } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

function makeDirective(
  n: number,
  action: ContainmentDirective['action'],
  targetId: string,
): ContainmentDirective {
  return Object.freeze({
    directive_id: `dir-${n}`,
    sequence: n,
    action,
    target_id: targetId,
    reason: `test directive ${n}`,
    is_replay_reconstructable: true as const,
  })
}

function makeFrame(n: number, replaySafe = true): CoordinationFrame {
  return Object.freeze({
    frame_id: `f-${n}`,
    sequence: n,
    agent_id: `agent-${n}`,
    action_type: 'observe',
    mutation_ids: [],
    replay_safe: replaySafe,
  })
}

function makeWfFrame(n: number, satisfied = true): WorkflowReplayFrame {
  return Object.freeze({
    frame_id: `wf-${n}`,
    workflow_id: `wflow-${n}`,
    sequence: n,
    step_type: 'gather',
    input_hash: h('a'),
    output_hash: h('b'),
    invariant_satisfied: satisfied,
  })
}

const ACTIVE_AGENTS = Object.freeze(['agent-001', 'agent-002'])
const ACTIVE_WORKFLOWS = Object.freeze(['wflow-001', 'wflow-002'])
const PANEL = Object.freeze([1, 1, 1, 1, 1, 1, 1, 1, 1, 1])

// ─── applyDirectives: all 5 action types ─────────────────

describe('applyDirectives: all ContainmentAction outcomes', () => {
  it('freeze_workflow: APPLIED when workflow is in active set', () => {
    const result = applyDirectives(
      [makeDirective(1, 'freeze_workflow', 'wflow-001')],
      ACTIVE_AGENTS, ACTIVE_WORKFLOWS, 1,
    )
    expect(result.decisions[0]?.outcome).toBe('APPLIED')
    expect(result.directives_applied).toBe(1)
  })

  it('freeze_workflow: SKIPPED when workflow not in active set', () => {
    const result = applyDirectives(
      [makeDirective(1, 'freeze_workflow', 'wflow-unknown')],
      ACTIVE_AGENTS, ACTIVE_WORKFLOWS, 1,
    )
    expect(result.decisions[0]?.outcome).toBe('SKIPPED')
    expect(result.directives_skipped).toBe(1)
    expect(result.directives_applied).toBe(0)
  })

  it('elevate_state: unconditionally APPLIED (no target lookup)', () => {
    const result = applyDirectives(
      [makeDirective(1, 'elevate_state', 'nonexistent-target')],
      [], [], 1,
    )
    expect(result.decisions[0]?.outcome).toBe('APPLIED')
    expect(result.directives_applied).toBe(1)
  })

  it('block_frame: unconditionally APPLIED even with empty active sets', () => {
    const result = applyDirectives(
      [makeDirective(1, 'block_frame', 'any-target')],
      [], [], 1,
    )
    expect(result.decisions[0]?.outcome).toBe('APPLIED')
  })

  it('invalidate_replay_chain: unconditionally APPLIED', () => {
    const result = applyDirectives(
      [makeDirective(1, 'invalidate_replay_chain', 'any-workflow')],
      [], [], 1,
    )
    expect(result.decisions[0]?.outcome).toBe('APPLIED')
  })
})

// ─── Mixed APPLIED/SKIPPED count accuracy ─────────────────

describe('applyDirectives: count invariants', () => {
  it('directives_applied + directives_skipped === decisions.length', () => {
    const directives = [
      makeDirective(1, 'quarantine_agent', 'agent-001'),    // APPLIED
      makeDirective(2, 'quarantine_agent', 'agent-missing'), // SKIPPED
      makeDirective(3, 'freeze_workflow', 'wflow-001'),      // APPLIED
      makeDirective(4, 'freeze_workflow', 'wflow-missing'),  // SKIPPED
      makeDirective(5, 'elevate_state', 'any'),              // APPLIED
    ]
    const result = applyDirectives(directives, ACTIVE_AGENTS, ACTIVE_WORKFLOWS, 1)
    expect(result.directives_applied + result.directives_skipped).toBe(result.decisions.length)
    expect(result.directives_applied).toBe(3)
    expect(result.directives_skipped).toBe(2)
  })

  it('20 directives all APPLIED: counts correct', () => {
    const directives = Array.from({ length: 20 }, (_, i) =>
      makeDirective(i + 1, 'block_frame', `target-${i}`),
    )
    const result = applyDirectives(directives, [], [], 1)
    expect(result.directives_applied).toBe(20)
    expect(result.directives_skipped).toBe(0)
    expect(result.decisions.length).toBe(20)
  })

  it('20 quarantine_agent directives with no active agents: all SKIPPED', () => {
    const directives = Array.from({ length: 20 }, (_, i) =>
      makeDirective(i + 1, 'quarantine_agent', `agent-${i}`),
    )
    const result = applyDirectives(directives, [], ACTIVE_WORKFLOWS, 1)
    expect(result.directives_skipped).toBe(20)
    expect(result.directives_applied).toBe(0)
  })

  it('result and all decisions are frozen', () => {
    const result = applyDirectives(
      [makeDirective(1, 'block_frame', 'x')],
      [], [], 1,
    )
    expect(Object.isFrozen(result)).toBe(true)
    for (const d of result.decisions) expect(Object.isFrozen(d)).toBe(true)
  })

  it('identical input × 3 → identical result structure', () => {
    const directives = [
      makeDirective(1, 'quarantine_agent', 'agent-001'),
      makeDirective(2, 'elevate_state', 'x'),
    ]
    const r1 = applyDirectives(directives, ACTIVE_AGENTS, ACTIVE_WORKFLOWS, 1)
    const r2 = applyDirectives(directives, ACTIVE_AGENTS, ACTIVE_WORKFLOWS, 1)
    const r3 = applyDirectives(directives, ACTIVE_AGENTS, ACTIVE_WORKFLOWS, 1)
    expect(r1.directives_applied).toBe(r2.directives_applied)
    expect(r2.directives_applied).toBe(r3.directives_applied)
    expect(r1.decisions[0]?.outcome).toBe(r2.decisions[0]?.outcome)
  })
})

// ─── capturePostEnforcementSnapshot hash sensitivity ──────

describe('capturePostEnforcementSnapshot: state_hash sensitivity', () => {
  function makeResult(applied: number) {
    return Object.freeze({
      decisions: Object.freeze([]),
      directives_applied: applied,
      directives_skipped: 0,
      sequence: 1,
      is_replay_reconstructable: true as const,
      schema_version: '1.0.0' as const,
    })
  }

  it('different directives_applied → different state_hash', () => {
    const s0 = capturePostEnforcementSnapshot({ enforcement_result: makeResult(0), sitr_state: 'STABLE', panel_sequence_numbers: PANEL, sequence: 1 })
    const s1 = capturePostEnforcementSnapshot({ enforcement_result: makeResult(1), sitr_state: 'STABLE', panel_sequence_numbers: PANEL, sequence: 1 })
    expect(s0.state_hash).not.toBe(s1.state_hash)
  })

  it('different sequence → different state_hash', () => {
    const s1 = capturePostEnforcementSnapshot({ enforcement_result: makeResult(0), sitr_state: 'STABLE', panel_sequence_numbers: PANEL, sequence: 1 })
    const s2 = capturePostEnforcementSnapshot({ enforcement_result: makeResult(0), sitr_state: 'STABLE', panel_sequence_numbers: PANEL, sequence: 2 })
    expect(s1.state_hash).not.toBe(s2.state_hash)
  })

  it('same inputs × 3 → same state_hash', () => {
    const params = { enforcement_result: makeResult(2), sitr_state: 'DEGRADED' as const, panel_sequence_numbers: PANEL, sequence: 5 }
    const s1 = capturePostEnforcementSnapshot(params)
    const s2 = capturePostEnforcementSnapshot(params)
    const s3 = capturePostEnforcementSnapshot(params)
    expect(s1.state_hash).toBe(s2.state_hash)
    expect(s2.state_hash).toBe(s3.state_hash)
  })

  it('phase is always post_enforcement', () => {
    const s = capturePostEnforcementSnapshot({ enforcement_result: makeResult(0), sitr_state: 'STABLE', panel_sequence_numbers: PANEL, sequence: 1 })
    expect(s.phase).toBe('post_enforcement')
  })
})

// ─── computeAutoDirectives edge cases ─────────────────────

describe('computeAutoDirectives: edge cases', () => {
  it('empty frames and workflowFrames → empty directives', () => {
    expect(computeAutoDirectives([], [], 1)).toHaveLength(0)
  })

  it('3 non-replay-safe frames → 3 quarantine_agent directives', () => {
    const frames = [makeFrame(1, false), makeFrame(2, false), makeFrame(3, false)]
    const directives = computeAutoDirectives(frames, [], 1)
    expect(directives).toHaveLength(3)
    for (const d of directives) expect(d.action).toBe('quarantine_agent')
  })

  it('3 workflow violations → 3 invalidate_replay_chain directives', () => {
    const wfFrames = [makeWfFrame(1, false), makeWfFrame(2, false), makeWfFrame(3, false)]
    const directives = computeAutoDirectives([], wfFrames, 1)
    expect(directives).toHaveLength(3)
    for (const d of directives) expect(d.action).toBe('invalidate_replay_chain')
  })

  it('mixed violations: 2 non-replay-safe + 2 workflow → 4 directives total', () => {
    const frames = [makeFrame(1, false), makeFrame(2, false)]
    const wfFrames = [makeWfFrame(1, false), makeWfFrame(2, false)]
    const directives = computeAutoDirectives(frames, wfFrames, 1)
    expect(directives).toHaveLength(4)
  })

  it('directive IDs deterministic × 3 (FNV-1a of sequence:action:target_id)', () => {
    const frames = [makeFrame(1, false)]
    const wfFrames = [makeWfFrame(1, false)]
    const d1 = computeAutoDirectives(frames, wfFrames, 1)
    const d2 = computeAutoDirectives(frames, wfFrames, 1)
    const d3 = computeAutoDirectives(frames, wfFrames, 1)
    expect(d1[0]?.directive_id).toBe(d2[0]?.directive_id)
    expect(d2[0]?.directive_id).toBe(d3[0]?.directive_id)
  })

  it('different sequence → different directive IDs', () => {
    const frames = [makeFrame(1, false)]
    const d1 = computeAutoDirectives(frames, [], 1)
    const d2 = computeAutoDirectives(frames, [], 2)
    expect(d1[0]?.directive_id).not.toBe(d2[0]?.directive_id)
  })
})
