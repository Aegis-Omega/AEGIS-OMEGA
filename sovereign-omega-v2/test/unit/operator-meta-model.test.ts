import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  OPERATOR_META_MODEL_SCHEMA_VERSION,
  certifyMetaModelDecision,
  computeMetaModelHallucinationDelta,
  deriveMetaAuthority,
  type MetaEvidence,
  type MetaHypothesis,
  type MetaModelDecision,
  type MetaPolicyThresholds,
} from '../../src/metacognition/operator-model.js'

const utterance: MetaEvidence = {
  id: 'E1',
  kind: 'USER_UTTERANCE',
  surface: 'EXTERNAL',
  summary: 'ambiguous statement about unusual outputs',
  source_ref: 'turn:1',
  independence_key: 'utterance:1',
  content_hash: 'a'.repeat(64) as SHA256Hex,
}

const explicitConfirmation: MetaEvidence = {
  id: 'E2',
  kind: 'EXPLICIT_USER_CONFIRMATION',
  surface: 'USER_REPORTED',
  summary: 'user explicitly confirms intended meaning',
  source_ref: 'turn:2',
  independence_key: 'confirmation:2',
  content_hash: 'b'.repeat(64) as SHA256Hex,
}

const repeatedConfirmation: MetaEvidence = {
  id: 'E3',
  kind: 'EXPLICIT_USER_CONFIRMATION',
  surface: 'USER_REPORTED',
  summary: 'user independently reconfirms the state in a later observation',
  source_ref: 'turn:9',
  independence_key: 'confirmation:9',
  content_hash: 'c'.repeat(64) as SHA256Hex,
}

function mapEvidence(...items: MetaEvidence[]): ReadonlyMap<string, MetaEvidence> {
  return new Map(items.map(item => [item.id, item] as const))
}

function decision(
  route: MetaModelDecision['route'],
  routeIds: string[] = [],
  claimIds: string[] = [],
  policyIds: string[] = [],
): MetaModelDecision {
  return {
    route,
    route_hypothesis_ids: routeIds,
    response_claim_hypothesis_ids: claimIds,
    policy_change_hypothesis_ids: policyIds,
  }
}

const strictPolicy: MetaPolicyThresholds = {
  min_evidence_count: 2,
  min_independent_signal_count: 2,
  max_mean_hd_bps: 1500,
}

describe('operator meta-model constants', () => {
  it('uses schema version 1.1.0', () => {
    expect(OPERATOR_META_MODEL_SCHEMA_VERSION).toBe('1.1.0')
  })
})

describe('Obsidian HD lineage: posterior calibration', () => {
  it('computes mean absolute calibration delta in basis points', () => {
    const calibration = computeMetaModelHallucinationDelta([
      { predicted_correctness_bps: 9000, actual_correctness_bps: 10_000 },
      { predicted_correctness_bps: 8000, actual_correctness_bps: 7000 },
      { predicted_correctness_bps: 5000, actual_correctness_bps: 5000 },
    ])
    expect(calibration.sample_count).toBe(3)
    expect(calibration.mean_hd_bps).toBe(667)
    expect(Object.isFrozen(calibration)).toBe(true)
  })

  it('rejects an empty calibration set', () => {
    expect(() => computeMetaModelHallucinationDelta([])).toThrow(
      'Meta-model HD requires at least one calibration sample',
    )
  })

  it('rejects out-of-range calibration samples', () => {
    expect(() => computeMetaModelHallucinationDelta([
      { predicted_correctness_bps: 10_001, actual_correctness_bps: 10_000 },
    ])).toThrow('Invalid calibration sample at index 0')
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

describe('Obsidian NO GUESSING translation', () => {
  it('rejects DEFAULT routing from an unresolved latent user-state hypothesis', async () => {
    const h: MetaHypothesis = {
      id: 'H1',
      domain: 'USER_STATE',
      proposition: 'user is emotionally distressed',
      status: 'SUPPORTED',
      evidence_refs: ['E1'],
      model_confidence_bps: 9700,
    }
    const cert = await certifyMetaModelDecision(
      [utterance],
      [h],
      decision('DEFAULT', ['H1']),
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.violations).toContain(
      'NO_GUESSING: default route H1 cannot rely on unresolved USER_STATE; CLARIFY or BLOCK',
    )
  })

  it('permits CLARIFY for the same unresolved hypothesis', async () => {
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

  it('permits BLOCKED for consequential ambiguity without asserting the hypothesis', async () => {
    const h: MetaHypothesis = {
      id: 'H1',
      domain: 'USER_INTENT',
      proposition: 'operator may intend a consequential mutation',
      status: 'PROPOSED',
      evidence_refs: ['E1'],
    }
    const cert = await certifyMetaModelDecision(
      [utterance],
      [h],
      decision('BLOCKED', ['H1']),
    )
    expect(cert.is_valid).toBe(true)
    expect(cert.hypothesis_authority.H1).toBe('ADVISORY')
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
})

describe('persistent policy promotion', () => {
  it('rejects policy change without explicit thresholds', async () => {
    const h: MetaHypothesis = {
      id: 'H7',
      domain: 'USER_PREFERENCE',
      proposition: 'operator prefers terse responses',
      status: 'SUPPORTED',
      evidence_refs: ['E2'],
      calibration: { sample_count: 5, mean_hd_bps: 500 },
    }
    const cert = await certifyMetaModelDecision(
      [explicitConfirmation],
      [h],
      decision('DEFAULT', ['H7'], [], ['H7']),
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.violations).toContain('policy change requested without explicit policy thresholds')
  })

  it('rejects a one-signal policy promotion even when assertable', async () => {
    const h: MetaHypothesis = {
      id: 'H7',
      domain: 'USER_PREFERENCE',
      proposition: 'operator prefers terse responses',
      status: 'SUPPORTED',
      evidence_refs: ['E2'],
      calibration: { sample_count: 5, mean_hd_bps: 500 },
    }
    const cert = await certifyMetaModelDecision(
      [explicitConfirmation],
      [h],
      decision('DEFAULT', ['H7'], [], ['H7']),
      strictPolicy,
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.policy_admissible.H7).toBe(false)
    expect(cert.violations).toContain('policy change H7 has 1 evidence items; requires 2')
    expect(cert.violations).toContain('policy change H7 has 1 established independent signals; requires 2')
  })

  it('rejects persistent policy promotion when calibration error is too high', async () => {
    const h: MetaHypothesis = {
      id: 'H7',
      domain: 'USER_PREFERENCE',
      proposition: 'operator prefers terse responses',
      status: 'SUPPORTED',
      evidence_refs: ['E2', 'E3'],
      calibration: { sample_count: 8, mean_hd_bps: 1800 },
    }
    const cert = await certifyMetaModelDecision(
      [explicitConfirmation, repeatedConfirmation],
      [h],
      decision('DEFAULT', ['H7'], [], ['H7']),
      strictPolicy,
    )
    expect(cert.is_valid).toBe(false)
    expect(cert.policy_admissible.H7).toBe(false)
    expect(cert.violations).toContain('policy change H7 calibration HD 1800 exceeds 1500')
  })

  it('admits persistent policy promotion only with repeated independent calibrated evidence', async () => {
    const h: MetaHypothesis = {
      id: 'H7',
      domain: 'USER_PREFERENCE',
      proposition: 'operator prefers terse responses',
      status: 'SUPPORTED',
      evidence_refs: ['E2', 'E3'],
      calibration: computeMetaModelHallucinationDelta([
        { predicted_correctness_bps: 9400, actual_correctness_bps: 10_000 },
        { predicted_correctness_bps: 9000, actual_correctness_bps: 10_000 },
        { predicted_correctness_bps: 9600, actual_correctness_bps: 10_000 },
      ]),
    }
    const cert = await certifyMetaModelDecision(
      [explicitConfirmation, repeatedConfirmation],
      [h],
      decision('DEFAULT', ['H7'], [], ['H7']),
      strictPolicy,
    )
    expect(cert.is_valid).toBe(true)
    expect(cert.policy_admissible.H7).toBe(true)
  })
})

describe('determinism and immutability', () => {
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
    expect(Object.isFrozen(cert.policy_admissible)).toBe(true)
  })
})
