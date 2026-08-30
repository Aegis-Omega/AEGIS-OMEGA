// Gate 162 — Skill Harness Decay Engine Tests
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import {
  decaySkill,
  SkillDecayError,
  DECAY_SCHEMA_VERSION,
  HALF_LIFE_DAYS,
  GRACE_PERIOD_DAYS,
  FAILURE_RATE_PENALTY_THRESHOLD,
} from '../../src/skill-harness/decay.js'

// Fixed epoch constant per testing.md rule: 1_600_000_000_000 = 2020-09-13T12:26:40.000Z
const EPOCH_TS = 1_600_000_000_000
const BASE_TS = EPOCH_TS  // alias used throughout test bodies
const EPOCH_ISO = new Date(EPOCH_TS).toISOString()
const DAY_MS = 86_400_000



async function baseSkill(overrides: {
  last_validated?: string
  confidence?: number
  failure_rate?: number
  recency_score?: number
} = {}) {
  return buildSkillRecord({
    skill_id: 'workflow_orchestration',
    name: 'Workflow Orchestration',
    confidence: overrides.confidence ?? 0.8,
    validated_runs: 30,
    failure_rate: overrides.failure_rate ?? 0.1,
    recency_score: overrides.recency_score ?? 0.9,
    domain_affinity: ['workflow'],
    dependencies: [],
    evidence_refs: [],
    last_validated: overrides.last_validated ?? EPOCH_ISO,
    epistemic_tier: 'T2',
    primitive_mapping: 'SEQUENCE',
  })
}

describe('SkillDecay — constants', () => {
  it('exports correct schema version', () => {
    expect(DECAY_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('HALF_LIFE_DAYS is 30', () => {
    expect(HALF_LIFE_DAYS).toBe(30)
  })

  it('GRACE_PERIOD_DAYS is 7', () => {
    expect(GRACE_PERIOD_DAYS).toBe(7)
  })

  it('FAILURE_RATE_PENALTY_THRESHOLD is 0.5', () => {
    expect(FAILURE_RATE_PENALTY_THRESHOLD).toBe(0.5)
  })
})

describe('SkillDecay — within grace period (no decay)', () => {
  it('same timestamp → no decay', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS)
    expect(result.was_decayed).toBe(false)
    expect(result.decay_factor).toBe(1.0)
    expect(result.updated_skill.confidence).toBe(skill.confidence)
  })

  it('3 days inactive → no decay (within 7-day grace)', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS + 3 * DAY_MS)
    expect(result.was_decayed).toBe(false)
    expect(result.decay_factor).toBe(1.0)
  })

  it('exactly grace period days → no decay', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS + GRACE_PERIOD_DAYS * DAY_MS)
    expect(result.was_decayed).toBe(false)
  })
})

describe('SkillDecay — beyond grace period', () => {
  it('30 days inactive → decay_factor = 0.5 (one half-life)', async () => {
    const skill = await baseSkill()
    // 30 inactive days = grace + (30-7) = 23 active decay days
    const ts = BASE_TS + 30 * DAY_MS
    const result = await decaySkill(skill, ts)
    expect(result.was_decayed).toBe(true)
    // active_days = 30 - 7 = 23; factor = 0.5^(23/30) ≈ 0.590
    expect(result.decay_factor).toBeLessThan(1.0)
    expect(result.decay_factor).toBeGreaterThan(0.0)
  })

  it('confidence decreases on decay', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS + 60 * DAY_MS)
    expect(result.updated_skill.confidence).toBeLessThan(skill.confidence)
  })

  it('recency_score decreases on decay', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS + 60 * DAY_MS)
    expect(result.updated_skill.recency_score).toBeLessThan(skill.recency_score)
  })

  it('confidence never goes below 0', async () => {
    const skill = await baseSkill({ confidence: 0.01 })
    const result = await decaySkill(skill, BASE_TS + 365 * DAY_MS)
    expect(result.updated_skill.confidence).toBeGreaterThanOrEqual(0)
  })

  it('last_validated unchanged after decay', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS + 30 * DAY_MS)
    expect(result.updated_skill.last_validated).toBe(skill.last_validated)
  })

  it('validated_runs unchanged after decay', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS + 30 * DAY_MS)
    expect(result.updated_skill.validated_runs).toBe(skill.validated_runs)
  })
})

describe('SkillDecay — failure rate penalty', () => {
  it('high failure_rate applies extra 0.9 penalty', async () => {
    const highFail = await baseSkill({ failure_rate: 0.6, confidence: 0.7 })
    const lowFail = await baseSkill({ failure_rate: 0.2, confidence: 0.7 })
    const ts = BASE_TS + 30 * DAY_MS
    const r1 = await decaySkill(highFail, ts)
    const r2 = await decaySkill(lowFail, ts)
    // High failure rate → additional × 0.9 penalty → lower confidence
    expect(r1.updated_skill.confidence).toBeLessThan(r2.updated_skill.confidence)
  })

  it('exactly at threshold (0.5) triggers penalty', async () => {
    const atThreshold = await baseSkill({ failure_rate: 0.5 })
    const belowThreshold = await baseSkill({ failure_rate: 0.49 })
    const ts = BASE_TS + 30 * DAY_MS
    const r1 = await decaySkill(atThreshold, ts)
    const r2 = await decaySkill(belowThreshold, ts)
    expect(r1.decay_factor).toBeLessThan(r2.decay_factor)
  })
})

describe('SkillDecay — determinism', () => {
  it('same inputs → identical decay_hash ×3', async () => {
    const skill = await baseSkill()
    const ts = BASE_TS + 45 * DAY_MS
    const r1 = await decaySkill(skill, ts)
    const r2 = await decaySkill(skill, ts)
    const r3 = await decaySkill(skill, ts)
    expect(r1.decay_hash).toBe(r2.decay_hash)
    expect(r2.decay_hash).toBe(r3.decay_hash)
  })

  it('decay_hash is 64-char hex', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS + 30 * DAY_MS)
    expect(result.decay_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(result.decay_hash)).toBe(true)
  })

  it('result is frozen', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS)
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, BASE_TS)
    expect(result.is_replay_reconstructable).toBe(true)
  })
})

describe('SkillDecay — error handling', () => {
  it('SkillDecayError is Error subclass', () => {
    expect(new SkillDecayError('x')).toBeInstanceOf(Error)
    expect(new SkillDecayError('x').name).toBe('SkillDecayError')
  })
})
