import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  OPERATOR_META_MODEL_SCHEMA_VERSION,
  certifyMetaModelDecision,
  deriveMetaAuthority,
  type MetaEvidence,
  type MetaHypothesis,
  type MetaModelDecision,
} from '../../src/metacognition/operator-model.js'

const utterance: MetaEvidence = {
  id: 'E1',
  kind: 'USER_UTTERANCE',
  summary: 'ambiguous statement about unusual outputs',
  source_ref: 'turn:1',
  content_hash: 'a'.repeat(64) as SHA256Hex,
}

const explicitConfirmation: MetaEvidence = {
  id: 'E2',
  kind: 'EXPLICIT_USER_CONFIRMATION',
  summary: 'user explicitly confirms intended meaning',
  source_ref: 'turn:2',
  content_hash: 'b'.repeat(64) as SHA256Hex,
}

function mapEvidence(...items: MetaEvidence[]): ReadonlyMap<string, MetaEvidence> {
  return new Map(items.map(item => [item.id, item] as const))
}

function decision(
  route: MetaModelDecision['route'],
  routeIds: string[] = [],
  claimIds: string[] = [],
): MetaModelDecision {
  return {
    route,
    route_hypothesis_ids: routeIds,
    response_claim_hypothesis_ids: claimIds,
  }
}

describe('operator meta-model constants', () => {
  it('uses schema version 1.0.0', () => {
    expect(OPERATOR_META_MODEL_SCHEMA_VERSION).toBe('1.0.0')
  })
})

describe('deriveMetaAuthority', () => {
  it('keeps an unconfirmed user-state hypothesis advisory', () => {
    const h: MetaHypothesis = {
      id: 'H1',
      domain: 'USER_STATE',
      proposition: 'user is emotionally distressed',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
      model_confidence_bps: 9900,
    }
    expect(deriveMetaAuthority(h, mapEvidence(utterance))).toBe('ADVISORY')
  })

  it('does not let model confidence elevate authority', () => {
    const h: MetaHypothesis = {
      id: 'H1',
      domain: 'USER_STATE',
      proposition: 'user is emotionally distressed',
      status: 'PROPOSED',
      evidence_refs: ['E1'],
      model_confidence_bps: 10_000,
    }
    expect(deriveMetaAuthority(h, mapEvidence(utterance))).toBe('ADVISORY')
  })

  it('makes supported content risk routing-only', () => {
    const h: MetaHypothesis = {
      id: 'H2',
      domain: 'CONTENT_RISK',
      proposition: 'content matches a safety-sensitive pattern',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
    }
    expect(deriveMetaAuthority(h, mapEvidence(utterance))).toBe('ROUTING_ONLY')
  })

  it('allows explicit user confirmation to make user state assertable', () => {
    const h: MetaHypothesis = {
      id: 'H3',
      domain: 'USER_STATE',
      proposition: 'user explicitly reports distress',
      status: 'SUPPORTED',
      evidence_refs: ['E1', 'E2'],
    }
    expect(deriveMetaAuthority(h, mapEvidence(utterance, explicitConfirmation))).toBe('ASSERTABLE')
  })

  it('gives contradicted hypotheses no authority', () => {
    const h: MetaHypothesis = {
      id: 'H4',
      domain: 'USER_INTENT',
      proposition: 'user wants a psychological interpretation',
      status: 'CONTRADICTED',
      evidence_refs: ['E1'],
    }
    expect(deriveMetaAuthority(h, mapEvidence(utterance))).toBe('NONE')
  })
})

describe('certifyMetaModelDecision', () => {
  it('rejects a safety route based on latent user-state inference', async () => {
    const h: MetaHypothesis = {
      id: 'H1',
      domain: 'USER_STATE',
      proposition: 'user is emotionally distressed',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
    }
    const cert = await certifyMetaModelDecision(
      [utterance],
      [h],
      decision('SAFETY_CONSERVATIVE', ['H1']),
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.violations.some(v => v.includes('must be based on CONTENT_RISK'))).toBe(true)
  })

  it('permits safety routing from supported content-risk evidence', async () => {
    const h: MetaHypothesis = {
      id: 'H2',
      domain: 'CONTENT_RISK',
      proposition: 'content matches a safety-sensitive pattern',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
    }
    const cert = await certifyMetaModelDecision(
      [utterance],
      [h],
      decision('SAFETY_CONSERVATIVE', ['H2']),
    )
    expect(cert.is_valid).toBe(true)
    expect(cert.hypothesis_authority.H2).toBe('ROUTING_ONLY')
  })

  it('rejects surfacing an unconfirmed user-state hypothesis as fact', async () => {
    const h: MetaHypothesis = {
      id: 'H1',
      domain: 'USER_STATE',
      proposition: 'user is emotionally distressed',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
    }
    const cert = await certifyMetaModelDecision(
      [utterance],
      [h],
      decision('CLARIFY', ['H1'], ['H1']),
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.violations).toContain('response claim H1 is not assertable (ADVISORY)')
  })

  it('permits clarification from an advisory hypothesis without asserting it', async () => {
    const h: MetaHypothesis = {
      id: 'H1',
      domain: 'USER_STATE',
      proposition: 'meaning may have been interpreted as distress',
      status: 'PROPOSED',
      evidence_refs: ['E1'],
    }
    const cert = await certifyMetaModelDecision(
      [utterance],
      [h],
      decision('CLARIFY', ['H1']),
    )
    expect(cert.is_valid).toBe(true)
  })

  it('permits a confirmed user-state claim', async () => {
    const h: MetaHypothesis = {
      id: 'H3',
      domain: 'USER_STATE',
      proposition: 'user explicitly reports distress',
      status: 'SUPPORTED',
      evidence_refs: ['E1', 'E2'],
    }
    const cert = await certifyMetaModelDecision(
      [utterance, explicitConfirmation],
      [h],
      decision('DEFAULT', ['H3'], ['H3']),
    )
    expect(cert.is_valid).toBe(true)
    expect(cert.hypothesis_authority.H3).toBe('ASSERTABLE')
  })

  it('rejects a response claim derived from content-risk routing evidence', async () => {
    const h: MetaHypothesis = {
      id: 'H2',
      domain: 'CONTENT_RISK',
      proposition: 'content matches a safety-sensitive pattern',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
    }
    const cert = await certifyMetaModelDecision(
      [utterance],
      [h],
      decision('SAFETY_CONSERVATIVE', ['H2'], ['H2']),
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.violations).toContain('response claim H2 is not assertable (ROUTING_ONLY)')
  })

  it('rejects missing evidence references', async () => {
    const h: MetaHypothesis = {
      id: 'H5',
      domain: 'TASK_CONTEXT',
      proposition: 'task is a technical audit',
      status: 'SUPPORTED',
      evidence_refs: ['MISSING'],
    }
    const cert = await certifyMetaModelDecision([], [h], decision('DEFAULT'))
    expect(cert.is_valid).toBe(false)
    expect(cert.violations).toContain('hypothesis H5 references missing evidence MISSING')
  })

  it('rejects unknown route hypothesis ids', async () => {
    const cert = await certifyMetaModelDecision(
      [utterance],
      [],
      decision('CLARIFY', ['DOES_NOT_EXIST']),
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.violations).toContain('route references unknown hypothesis DOES_NOT_EXIST')
  })

  it('rejects invalid confidence ranges without changing authority semantics', async () => {
    const h: MetaHypothesis = {
      id: 'H6',
      domain: 'USER_STATE',
      proposition: 'some latent state',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
      model_confidence_bps: 10_001,
    }
    const cert = await certifyMetaModelDecision([utterance], [h], decision('CLARIFY', ['H6']))
    expect(cert.is_valid).toBe(false)
    expect(cert.violations).toContain('hypothesis H6 has invalid model_confidence_bps')
    expect(cert.hypothesis_authority.H6).toBe('ADVISORY')
  })

  it('rejects duplicate evidence ids', async () => {
    const cert = await certifyMetaModelDecision(
      [utterance, { ...utterance }],
      [],
      decision('DEFAULT'),
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.violations).toContain('duplicate evidence ids: E1')
  })

  it('is deterministic across three identical certifications', async () => {
    const h: MetaHypothesis = {
      id: 'H2',
      domain: 'CONTENT_RISK',
      proposition: 'content matches a safety-sensitive pattern',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
    }
    const d = decision('SAFETY_CONSERVATIVE', ['H2'])
    const a = await certifyMetaModelDecision([utterance], [h], d)
    const b = await certifyMetaModelDecision([utterance], [h], d)
    const c = await certifyMetaModelDecision([utterance], [h], d)
    expect(a.decision_hash).toBe(b.decision_hash)
    expect(b.decision_hash).toBe(c.decision_hash)
  })

  it('returns a frozen certificate', async () => {
    const cert = await certifyMetaModelDecision([], [], decision('DEFAULT'))
    expect(Object.isFrozen(cert)).toBe(true)
    expect(Object.isFrozen(cert.violations)).toBe(true)
    expect(Object.isFrozen(cert.hypothesis_authority)).toBe(true)
  })
})
