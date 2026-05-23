// Gate 161 — Skill Harness Phase 3: Inference Engine Tests
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import {
  inferSkillConfidence,
  InferenceEngineError,
  INFERENCE_SCHEMA_VERSION,
} from '../../src/skill-harness/inference-engine.js'
import type { SkillEvidence } from '../../src/skill-harness/telemetry-engine.js'
import type { SequenceNumber } from '../../src/core/types.js'

const BASE_TS = 1_600_000_000_000
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function baseSkill() {
  return buildSkillRecord({
    skill_id: 'replay_audit',
    name: 'Replay Audit',
    confidence: 0.7,
    validated_runs: 20,
    failure_rate: 0.15,
    recency_score: 0.8,
    domain_affinity: ['audit', 'replay'],
    dependencies: [],
    evidence_refs: [],
    last_validated: '2026-01-01T00:00:00.000Z',
    epistemic_tier: 'T1',
    primitive_mapping: 'VERIFY',
  })
}

function makeEvidence(i: number, is_success: boolean): SkillEvidence {
  return {
    skill_id: 'replay_audit',
    agent_id: 'agent-inf',
    is_success,
    loop_hash: (i.toString(16).padStart(2, '0').repeat(32)) as ReturnType<typeof String>,
    sequence: seq(i),
    timestamp_ms: BASE_TS + i * 1000,
  } as SkillEvidence
}

describe('InferenceEngine — schema version', () => {
  it('exports correct schema version', () => {
    expect(INFERENCE_SCHEMA_VERSION).toBe('1.0.0')
  })
})

describe('InferenceEngine — empty batch', () => {
  it('empty batch returns inference over existing skill unchanged', async () => {
    const skill = await baseSkill()
    const result = await inferSkillConfidence(skill, [])
    expect(result.updated_skill.skill_id).toBe(skill.skill_id)
    expect(result.updated_skill.validated_runs).toBe(skill.validated_runs)
    expect(result.inference.evidence_count).toBe(0)
  })

  it('inference_hash is 64-char hex', async () => {
    const skill = await baseSkill()
    const result = await inferSkillConfidence(skill, [])
    expect(result.inference.inference_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(result.inference.inference_hash)).toBe(true)
  })
})

describe('InferenceEngine — Beta posterior', () => {
  it('posterior_alpha > 1 for any skill with runs > 0', async () => {
    const skill = await baseSkill()
    const { inference } = await inferSkillConfidence(skill, [])
    expect(inference.posterior_alpha).toBeGreaterThan(1)
  })

  it('posterior_beta > 1 for any skill with failure_rate > 0', async () => {
    const skill = await baseSkill()
    const { inference } = await inferSkillConfidence(skill, [])
    expect(inference.posterior_beta).toBeGreaterThan(1)
  })

  it('confidence_mean stays in [0, 1]', async () => {
    const skill = await baseSkill()
    const { inference } = await inferSkillConfidence(skill, [])
    expect(inference.confidence_mean).toBeGreaterThanOrEqual(0)
    expect(inference.confidence_mean).toBeLessThanOrEqual(1)
  })

  it('perfect skill: alpha >> beta → confidence_mean near 1', async () => {
    const perfect = await buildSkillRecord({
      skill_id: 'replay_audit', name: 'Perfect', confidence: 0.99,
      validated_runs: 100, failure_rate: 0.0, recency_score: 1.0,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T1', primitive_mapping: 'VERIFY',
    })
    const { inference } = await inferSkillConfidence(perfect, [])
    expect(inference.confidence_mean).toBeGreaterThan(0.95)
  })

  it('failed skill: beta >> alpha → confidence_mean near 0', async () => {
    const failed = await buildSkillRecord({
      skill_id: 'replay_audit', name: 'Failed', confidence: 0.05,
      validated_runs: 100, failure_rate: 0.95, recency_score: 0.1,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T1', primitive_mapping: 'VERIFY',
    })
    const { inference } = await inferSkillConfidence(failed, [])
    expect(inference.confidence_mean).toBeLessThan(0.1)
  })
})

describe('InferenceEngine — Wilson score CI', () => {
  it('confidence_lower <= confidence_mean <= confidence_upper', async () => {
    const skill = await baseSkill()
    const { inference } = await inferSkillConfidence(skill, [])
    expect(inference.confidence_lower).toBeLessThanOrEqual(inference.confidence_mean)
    expect(inference.confidence_mean).toBeLessThanOrEqual(inference.confidence_upper)
  })

  it('uninformative interval [0,1] for zero runs', async () => {
    const zero = await buildSkillRecord({
      skill_id: 'replay_audit', name: 'Zero', confidence: 0.5,
      validated_runs: 0, failure_rate: 0.0, recency_score: 0.5,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T2', primitive_mapping: 'VERIFY',
    })
    const { inference } = await inferSkillConfidence(zero, [])
    expect(inference.confidence_lower).toBe(0)
    expect(inference.confidence_upper).toBe(1)
  })

  it('narrower CI with more evidence runs', async () => {
    const few = await buildSkillRecord({
      skill_id: 'replay_audit', name: 'Few', confidence: 0.7,
      validated_runs: 5, failure_rate: 0.2, recency_score: 0.7,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T1', primitive_mapping: 'VERIFY',
    })
    const many = await buildSkillRecord({
      skill_id: 'replay_audit', name: 'Many', confidence: 0.7,
      validated_runs: 200, failure_rate: 0.2, recency_score: 0.7,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T1', primitive_mapping: 'VERIFY',
    })
    const r1 = await inferSkillConfidence(few, [])
    const r2 = await inferSkillConfidence(many, [])
    const width1 = r1.inference.confidence_upper - r1.inference.confidence_lower
    const width2 = r2.inference.confidence_upper - r2.inference.confidence_lower
    expect(width2).toBeLessThan(width1) // more runs → narrower interval
  })
})

describe('InferenceEngine — batch processing', () => {
  it('3-success batch: evidence_count = 3, confidence increases', async () => {
    const skill = await baseSkill()
    const batch: SkillEvidence[] = [
      makeEvidence(1, true),
      makeEvidence(2, true),
      makeEvidence(3, true),
    ]
    const result = await inferSkillConfidence(skill, batch)
    expect(result.inference.evidence_count).toBe(3)
    expect(result.updated_skill.confidence).toBeGreaterThan(skill.confidence)
  })

  it('mismatched skill_id in batch throws InferenceEngineError', async () => {
    const skill = await baseSkill()
    const bad: SkillEvidence = { ...makeEvidence(1, true), skill_id: 'wrong_id' }
    await expect(inferSkillConfidence(skill, [bad])).rejects.toBeInstanceOf(InferenceEngineError)
  })

  it('InferenceEngineError is Error subclass', () => {
    expect(new InferenceEngineError('x')).toBeInstanceOf(Error)
    expect(new InferenceEngineError('x').name).toBe('InferenceEngineError')
  })
})

describe('InferenceEngine — determinism', () => {
  it('same skill + same batch → identical inference_hash ×3', async () => {
    const skill = await baseSkill()
    const batch = [makeEvidence(1, true), makeEvidence(2, false)]
    const r1 = await inferSkillConfidence(skill, batch)
    const r2 = await inferSkillConfidence(skill, batch)
    const r3 = await inferSkillConfidence(skill, batch)
    expect(r1.inference.inference_hash).toBe(r2.inference.inference_hash)
    expect(r2.inference.inference_hash).toBe(r3.inference.inference_hash)
  })

  it('result is frozen', async () => {
    const skill = await baseSkill()
    const result = await inferSkillConfidence(skill, [])
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.inference)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const skill = await baseSkill()
    const result = await inferSkillConfidence(skill, [])
    expect(result.is_replay_reconstructable).toBe(true)
    expect(result.inference.is_replay_reconstructable).toBe(true)
  })
})
