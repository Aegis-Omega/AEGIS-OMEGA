// ============================================================
// SOVEREIGN OMEGA — Metacognitive Self-Regulator tests
// ============================================================

import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  hashSelfModelStateRootV1,
  SelfRegulationError,
  regulateSelf,
} from '../../src/metacognition/self-regulator.js'
import type {
  AdaptationProposal,
  KnowledgeGap,
  SelfModelSnapshot,
} from '../../src/metacognition/self-regulator.js'

const H = (character: string) => character.repeat(64) as SHA256Hex

async function snapshot(overrides: Partial<SelfModelSnapshot['health']> = {}): Promise<SelfModelSnapshot> {
  const components = {
    identity_root: H('2'),
    policy_root: H('3'),
    capability_root: H('4'),
    memory_root: H('5'),
    metacognition_root: H('6'),
    verifier_trust_root: H('7'),
    health: {
      t0_verdict: true,
      corruption_count: 0,
      membrane_intact: true,
      entropy_bounded: true,
      ...overrides,
    },
  }
  return { state_root: await hashSelfModelStateRootV1(components), ...components }
}

const GAP: KnowledgeGap = {
  gap_id: 'gap.self-model.001',
  kind: 'CAPABILITY_DEFICIT',
  severity: 'HIGH',
  evidence_refs: [H('8')],
}

function proposal(parentStateRoot: SHA256Hex, overrides: Partial<AdaptationProposal> = {}): AdaptationProposal {
  return {
    proposal_id: 'proposal.self-model.001',
    objective: 'Add a deterministic self-regulation transition.',
    consequence_class: 'D2',
    expected_parent_state_root: parentStateRoot,
    addressed_gap_ids: [GAP.gap_id],
    requested_capabilities: ['repo.file.propose'],
    mutations: [{ path: 'src/metacognition/regulator.ts', operation: 'CREATE' }],
    verification_steps: ['npm test -- self-regulator.test.ts'],
    rollback_reference: 'git:revert-candidate',
    ...overrides,
  }
}

function withoutRollback(candidate: AdaptationProposal): AdaptationProposal {
  const { rollback_reference: _rollbackReference, ...proposalWithoutRollback } = candidate
  return proposalWithoutRollback
}

describe('regulateSelf', () => {
  it('returns NO_CHANGE when no verified gap exists', async () => {
    const decision = await regulateSelf({ snapshot: await snapshot(), gaps: [] })
    expect(decision.mode).toBe('NO_CHANGE')
    expect(decision.required_next_gate).toBe('NONE')
    expect(decision.grants_authority).toBe(false)
  })

  it('requires a proposal when verified gaps exist', async () => {
    const decision = await regulateSelf({ snapshot: await snapshot(), gaps: [GAP] })
    expect(decision.mode).toBe('PROPOSAL_REQUIRED')
    expect(decision.required_next_gate).toBe('OPERATOR_REVIEW')
  })

  it('halts on a membrane breach', async () => {
    const model = await snapshot({ membrane_intact: false })
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root),
    })
    expect(decision.mode).toBe('HALT')
    expect(decision.reasons).toContain('MEMBRANE_BREACH')
    expect(decision.required_next_gate).toBe('REANCHOR')
  })

  it('enters observation-only mode when adaptation exceeds replay capacity', async () => {
    const model = await snapshot({ entropy_bounded: false })
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root),
    })
    expect(decision.mode).toBe('OBSERVE_ONLY')
    expect(decision.requires_automaton3).toBe(false)
  })

  it('rejects a stale parent state', async () => {
    const model = await snapshot()
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, { expected_parent_state_root: H('9') }),
    })
    expect(decision.mode).toBe('REJECTED')
    expect(decision.reasons).toContain('STALE_PARENT_STATE')
  })

  it('rejects capabilities that could bypass authority', async () => {
    const model = await snapshot()
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, { requested_capabilities: ['authority.grant'] }),
    })
    expect(decision.mode).toBe('REJECTED')
    expect(decision.reasons).toContain('FORBIDDEN_CAPABILITY_REQUEST')
  })

  it.each([
    '',
    '   ',
    '.',
    '..',
    '/src/absolute.ts',
    './src/dot.ts',
    'src/./dot.ts',
    'src/../escape.ts',
    'src//duplicate-separator.ts',
    'src/trailing/',
    'C:/repo/file.ts',
    'C:\\repo\\file.ts',
    'file:src/file.ts',
    'https://example.test/file.ts',
    'src\\windows.ts',
    'src/trailing-dot.',
    'src/trailing-space ',
    'src/CON',
    'src/con.txt',
    'src/PRN.json',
    'src/aux',
    'src/NUL.log',
    'src/com1',
    'src/COM9.txt',
    'src/lpt1',
    'src/LPT9.log',
  ])('rejects a non-canonical repository mutation path: %s', async path => {
    const model = await snapshot()
    await expect(regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, {
        mutations: [{ path, operation: 'CREATE' }],
      }),
    })).rejects.toThrow(SelfRegulationError)
  })

  it('rejects duplicate operations on the same mutation path', async () => {
    const model = await snapshot()
    await expect(regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, {
        mutations: [
          { path: 'src/metacognition/regulator.ts', operation: 'UPDATE' },
          { path: 'src/metacognition/regulator.ts', operation: 'UPDATE' },
        ],
      }),
    })).rejects.toThrow('path has a duplicate operation')
  })

  it('rejects conflicting operations on the same mutation path', async () => {
    const model = await snapshot()
    await expect(regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, {
        mutations: [
          { path: 'src/metacognition/regulator.ts', operation: 'UPDATE' },
          { path: 'src/metacognition/regulator.ts', operation: 'DELETE' },
        ],
      }),
    })).rejects.toThrow('path has a conflicting operation')
  })

  it('rejects mutation targets that collide under Windows case folding', async () => {
    const model = await snapshot()
    await expect(regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, {
        mutations: [
          { path: 'src/metacognition/Regulator.ts', operation: 'UPDATE' },
          { path: 'SRC/METACOGNITION/regulator.ts', operation: 'UPDATE' },
        ],
      }),
    })).rejects.toThrow('path collides after Windows case folding')
  })

  it.each([
    'src/com10.ts',
    'src/lpt0.ts',
    'src/conifer.ts',
  ])('accepts non-device names adjacent to Windows reserved names: %s', async path => {
    const model = await snapshot()
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, {
        mutations: [{ path, operation: 'CREATE' }],
      }),
    })
    expect(decision.mode).toBe('READY_FOR_AUTHORITY')
  })

  it('rejects every D0 proposal that attempts repository mutation', async () => {
    const model = await snapshot()
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: withoutRollback(proposal(model.state_root, {
        consequence_class: 'D0',
      })),
    })
    expect(decision.mode).toBe('REJECTED')
    expect(decision.reasons).toContain('D0_MUTATION_FORBIDDEN')
    expect(decision.requires_automaton3).toBe(false)
  })

  it('requires rollback evidence for D1 repository mutation', async () => {
    const model = await snapshot()
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: withoutRollback(proposal(model.state_root, {
        consequence_class: 'D1',
      })),
    })
    expect(decision.mode).toBe('REJECTED')
    expect(decision.reasons).toContain('ROLLBACK_REFERENCE_REQUIRED')
  })

  it('routes a D1 mutation with rollback evidence to authority evaluation', async () => {
    const model = await snapshot()
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, { consequence_class: 'D1' }),
    })
    expect(decision.mode).toBe('READY_FOR_AUTHORITY')
    expect(decision.required_next_gate).toBe('AUTOMATON_3')
  })

  it('requires explicit approval for D3 proposals', async () => {
    const model = await snapshot()
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, { consequence_class: 'D3' }),
    })
    expect(decision.mode).toBe('REJECTED')
    expect(decision.reasons).toContain('OPERATOR_APPROVAL_REQUIRED')
    expect(decision.required_next_gate).toBe('OPERATOR_REVIEW')
  })

  it('fails closed on whitespace-only rollback and approval references', async () => {
    const model = await snapshot()
    await expect(regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, {
        consequence_class: 'D3',
        rollback_reference: '   ',
        operator_approval_reference: '\t',
      }),
    })).rejects.toThrow(SelfRegulationError)
  })

  it('fails closed on a whitespace-only constitutional change reference', async () => {
    const model = await snapshot()
    await expect(regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root, {
        consequence_class: 'D4',
        operator_approval_reference: 'approval:operator',
        constitutional_change_reference: '   ',
      }),
    })).rejects.toThrow(SelfRegulationError)
  })

  it('does not treat an evidence-free gap as verified', async () => {
    await expect(regulateSelf({
      snapshot: await snapshot(),
      gaps: [{ ...GAP, evidence_refs: [] }],
    })).rejects.toThrow(SelfRegulationError)
  })

  it('routes a bounded, replayable proposal to Automaton-3', async () => {
    const model = await snapshot()
    const decision = await regulateSelf({
      snapshot: model,
      gaps: [GAP],
      proposal: proposal(model.state_root),
    })
    expect(decision.mode).toBe('READY_FOR_AUTHORITY')
    expect(decision.required_next_gate).toBe('AUTOMATON_3')
    expect(decision.requires_automaton3).toBe(true)
    expect(decision.grants_authority).toBe(false)
    expect(Object.isFrozen(decision)).toBe(true)
  })

  it('is deterministic for identical self-models and proposals', async () => {
    const model = await snapshot()
    const input = { snapshot: model, gaps: [GAP], proposal: proposal(model.state_root) }
    const [first, second] = await Promise.all([regulateSelf(input), regulateSelf(input)])
    expect(first.self_model_digest).toBe(second.self_model_digest)
    expect(first.proposal_digest).toBe(second.proposal_digest)
    expect(first.decision_digest).toBe(second.decision_digest)
  })

  it('fails closed on malformed self-model roots', async () => {
    const malformed = { ...await snapshot(), state_root: 'not-a-hash' as SHA256Hex }
    await expect(regulateSelf({ snapshot: malformed, gaps: [] })).rejects.toThrow(SelfRegulationError)
  })

  it('fails closed when state_root does not bind the component roots', async () => {
    const model = await snapshot()
    const forged = { ...model, capability_root: H('a') }
    await expect(regulateSelf({ snapshot: forged, gaps: [] })).rejects.toThrow(
      'snapshot.state_root does not bind the self-model components',
    )
  })
})
