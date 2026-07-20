// ============================================================
// SOVEREIGN OMEGA — Metacognitive Self-Regulator tests
// ============================================================

import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  SelfRegulationError,
  regulateSelf,
} from '../../src/metacognition/self-regulator.js'
import type {
  AdaptationProposal,
  KnowledgeGap,
  SelfModelSnapshot,
} from '../../src/metacognition/self-regulator.js'

const H = (character: string) => character.repeat(64) as SHA256Hex

function snapshot(overrides: Partial<SelfModelSnapshot['health']> = {}): SelfModelSnapshot {
  return {
    state_root: H('1'),
    identity_root: H('2'),
    policy_root: H('3'),
    capability_root: H('4'),
    memory_root: H('5'),
    metacognition_root: H('6'),
    health: {
      t0_verdict: true,
      corruption_count: 0,
      membrane_intact: true,
      entropy_bounded: true,
      ...overrides,
    },
  }
}

const GAP: KnowledgeGap = {
  gap_id: 'gap.self-model.001',
  kind: 'CAPABILITY_DEFICIT',
  severity: 'HIGH',
  evidence_refs: ['evidence:unit-test'],
}

function proposal(overrides: Partial<AdaptationProposal> = {}): AdaptationProposal {
  return {
    proposal_id: 'proposal.self-model.001',
    objective: 'Add a deterministic self-regulation transition.',
    consequence_class: 'D2',
    expected_parent_state_root: H('1'),
    addressed_gap_ids: [GAP.gap_id],
    requested_capabilities: ['repo.file.propose'],
    mutations: [{ path: 'src/metacognition/regulator.ts', operation: 'CREATE' }],
    verification_steps: ['npm test -- self-regulator.test.ts'],
    rollback_reference: 'git:revert-candidate',
    ...overrides,
  }
}

describe('regulateSelf', () => {
  it('returns NO_CHANGE when no verified gap exists', async () => {
    const decision = await regulateSelf({ snapshot: snapshot(), gaps: [] })
    expect(decision.mode).toBe('NO_CHANGE')
    expect(decision.required_next_gate).toBe('NONE')
    expect(decision.grants_authority).toBe(false)
  })

  it('requires a proposal when verified gaps exist', async () => {
    const decision = await regulateSelf({ snapshot: snapshot(), gaps: [GAP] })
    expect(decision.mode).toBe('PROPOSAL_REQUIRED')
    expect(decision.required_next_gate).toBe('OPERATOR_REVIEW')
  })

  it('halts on a membrane breach', async () => {
    const decision = await regulateSelf({
      snapshot: snapshot({ membrane_intact: false }),
      gaps: [GAP],
      proposal: proposal(),
    })
    expect(decision.mode).toBe('HALT')
    expect(decision.reasons).toContain('MEMBRANE_BREACH')
    expect(decision.required_next_gate).toBe('REANCHOR')
  })

  it('enters observation-only mode when adaptation exceeds replay capacity', async () => {
    const decision = await regulateSelf({
      snapshot: snapshot({ entropy_bounded: false }),
      gaps: [GAP],
      proposal: proposal(),
    })
    expect(decision.mode).toBe('OBSERVE_ONLY')
    expect(decision.requires_automaton3).toBe(false)
  })

  it('rejects a stale parent state', async () => {
    const decision = await regulateSelf({
      snapshot: snapshot(),
      gaps: [GAP],
      proposal: proposal({ expected_parent_state_root: H('9') }),
    })
    expect(decision.mode).toBe('REJECTED')
    expect(decision.reasons).toContain('STALE_PARENT_STATE')
  })

  it('rejects capabilities that could bypass authority', async () => {
    const decision = await regulateSelf({
      snapshot: snapshot(),
      gaps: [GAP],
      proposal: proposal({ requested_capabilities: ['authority.grant'] }),
    })
    expect(decision.mode).toBe('REJECTED')
    expect(decision.reasons).toContain('FORBIDDEN_CAPABILITY_REQUEST')
  })

  it('requires explicit approval for D3 proposals', async () => {
    const decision = await regulateSelf({
      snapshot: snapshot(),
      gaps: [GAP],
      proposal: proposal({ consequence_class: 'D3' }),
    })
    expect(decision.mode).toBe('REJECTED')
    expect(decision.reasons).toContain('OPERATOR_APPROVAL_REQUIRED')
    expect(decision.required_next_gate).toBe('OPERATOR_REVIEW')
  })

  it('routes a bounded, replayable proposal to Automaton-3', async () => {
    const decision = await regulateSelf({
      snapshot: snapshot(),
      gaps: [GAP],
      proposal: proposal(),
    })
    expect(decision.mode).toBe('READY_FOR_AUTHORITY')
    expect(decision.required_next_gate).toBe('AUTOMATON_3')
    expect(decision.requires_automaton3).toBe(true)
    expect(decision.grants_authority).toBe(false)
    expect(Object.isFrozen(decision)).toBe(true)
  })

  it('is deterministic for identical self-models and proposals', async () => {
    const input = { snapshot: snapshot(), gaps: [GAP], proposal: proposal() }
    const [first, second] = await Promise.all([regulateSelf(input), regulateSelf(input)])
    expect(first.self_model_digest).toBe(second.self_model_digest)
    expect(first.proposal_digest).toBe(second.proposal_digest)
    expect(first.decision_digest).toBe(second.decision_digest)
  })

  it('fails closed on malformed self-model roots', async () => {
    const malformed = { ...snapshot(), state_root: 'not-a-hash' as SHA256Hex }
    await expect(regulateSelf({ snapshot: malformed, gaps: [] })).rejects.toThrow(SelfRegulationError)
  })
})
