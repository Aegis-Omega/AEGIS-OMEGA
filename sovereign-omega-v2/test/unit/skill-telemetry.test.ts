// Gate 158 — Skill Harness Phase 2: Telemetry Engine Tests
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import {
  processEvidence,
  SkillTelemetryError,
  SKILL_TELEMETRY_SCHEMA_VERSION,
} from '../../src/skill-harness/telemetry-engine.js'
import type { SkillEvidence } from '../../src/skill-harness/telemetry-engine.js'
import type { SequenceNumber } from '../../src/core/types.js'

// Fixed timestamps from epoch constant per testing.md rule.
const BASE_TS = 1_600_000_000_000
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function makeEvidence(overrides: Partial<SkillEvidence> = {}): SkillEvidence {
  return {
    skill_id: 'test_skill',
    agent_id: 'agent-001',
    is_success: true,
    loop_hash: 'a'.repeat(64) as ReturnType<typeof String>,
    sequence: seq(1),
    timestamp_ms: BASE_TS,
    ...overrides,
  } as SkillEvidence
}

async function baseSkill() {
  return buildSkillRecord({
    skill_id: 'test_skill',
    name: 'Test Skill',
    confidence: 0.5,
    validated_runs: 4,
    failure_rate: 0.25,
    recency_score: 0.5,
    domain_affinity: ['test'],
    dependencies: [],
    evidence_refs: [],
    last_validated: '2026-01-01T00:00:00.000Z',
    epistemic_tier: 'T2',
    primitive_mapping: 'SEQUENCE',
  })
}

describe('SkillTelemetryEngine — schema version', () => {
  it('exports correct schema version', () => {
    expect(SKILL_TELEMETRY_SCHEMA_VERSION).toBe('1.0.0')
  })
})

describe('SkillTelemetryEngine — skill_id mismatch', () => {
  it('throws SkillTelemetryError on mismatched skill_id', async () => {
    const skill = await baseSkill()
    const evidence = makeEvidence({ skill_id: 'other_skill' })
    await expect(processEvidence(skill, evidence)).rejects.toBeInstanceOf(SkillTelemetryError)
  })

  it('SkillTelemetryError is Error subclass', () => {
    expect(new SkillTelemetryError('x')).toBeInstanceOf(Error)
    expect(new SkillTelemetryError('x').name).toBe('SkillTelemetryError')
  })
})

describe('SkillTelemetryEngine — success path', () => {
  it('confidence increases on success', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ is_success: true }))
    expect(result.updated_record.confidence).toBeGreaterThan(skill.confidence)
    expect(result.confidence_delta).toBeGreaterThan(0)
  })

  it('validated_runs increments by 1', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence())
    expect(result.updated_record.validated_runs).toBe(skill.validated_runs + 1)
  })

  it('failure_rate decreases on success', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ is_success: true }))
    expect(result.updated_record.failure_rate).toBeLessThan(skill.failure_rate)
  })

  it('recency_score increases on success', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ is_success: true }))
    expect(result.updated_record.recency_score).toBeGreaterThan(skill.recency_score)
  })

  it('last_validated updates to evidence timestamp on success', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ timestamp_ms: BASE_TS }))
    expect(result.updated_record.last_validated).toBe(new Date(BASE_TS).toISOString())
  })

  it('event_type is SKILL_VALIDATED when confidence < 0.8', async () => {
    const skill = await baseSkill() // confidence = 0.5
    const result = await processEvidence(skill, makeEvidence({ is_success: true }))
    expect(result.event_type).toBe('SKILL_VALIDATED')
  })

  it('event_type is SKILL_REINFORCED when confidence >= 0.8', async () => {
    const highConfSkill = await buildSkillRecord({
      skill_id: 'test_skill',
      name: 'High Conf',
      confidence: 0.85,
      validated_runs: 20,
      failure_rate: 0.05,
      recency_score: 0.9,
      domain_affinity: [],
      dependencies: [],
      evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z',
      epistemic_tier: 'T1',
      primitive_mapping: 'VERIFY',
    })
    const result = await processEvidence(highConfSkill, makeEvidence({ is_success: true }))
    expect(result.event_type).toBe('SKILL_REINFORCED')
  })

  it('loop_hash appended to evidence_refs', async () => {
    const skill = await baseSkill()
    const loop_hash = 'b'.repeat(64) as ReturnType<typeof String>
    const result = await processEvidence(skill, makeEvidence({ loop_hash: loop_hash as any }))
    expect(result.updated_record.evidence_refs).toContain(loop_hash)
  })
})

describe('SkillTelemetryEngine — failure path', () => {
  it('confidence decreases on failure', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ is_success: false }))
    expect(result.updated_record.confidence).toBeLessThan(skill.confidence)
    expect(result.confidence_delta).toBeLessThan(0)
  })

  it('failure_rate increases on failure', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ is_success: false }))
    expect(result.updated_record.failure_rate).toBeGreaterThan(skill.failure_rate)
  })

  it('recency_score decreases on failure', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ is_success: false }))
    expect(result.updated_record.recency_score).toBeLessThan(skill.recency_score)
  })

  it('last_validated unchanged on failure', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ is_success: false }))
    expect(result.updated_record.last_validated).toBe(skill.last_validated)
  })

  it('event_type is SKILL_DEGRADED on failure', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence({ is_success: false }))
    expect(result.event_type).toBe('SKILL_DEGRADED')
  })
})

describe('SkillTelemetryEngine — boundary conditions', () => {
  it('confidence stays <= 1.0 even after many successes', async () => {
    let skill = await buildSkillRecord({
      skill_id: 'test_skill', name: 'High', confidence: 0.99,
      validated_runs: 100, failure_rate: 0.0, recency_score: 1.0,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T2', primitive_mapping: 'HASH',
    })
    const result = await processEvidence(skill, makeEvidence({ is_success: true }))
    expect(result.updated_record.confidence).toBeLessThanOrEqual(1.0)
    expect(result.updated_record.failure_rate).toBeGreaterThanOrEqual(0.0)
  })

  it('confidence stays >= 0.0 even after many failures', async () => {
    const skill = await buildSkillRecord({
      skill_id: 'test_skill', name: 'Low', confidence: 0.01,
      validated_runs: 100, failure_rate: 0.99, recency_score: 0.0,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T2', primitive_mapping: 'HASH',
    })
    const result = await processEvidence(skill, makeEvidence({ is_success: false }))
    expect(result.updated_record.confidence).toBeGreaterThanOrEqual(0.0)
  })

  it('first run (validated_runs=0) uses higher learning rate (larger delta)', async () => {
    const fresh = await buildSkillRecord({
      skill_id: 'test_skill', name: 'Fresh', confidence: 0.5,
      validated_runs: 0, failure_rate: 0.0, recency_score: 0.5,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T2', primitive_mapping: 'HASH',
    })
    const veteran = await buildSkillRecord({
      skill_id: 'test_skill', name: 'Veteran', confidence: 0.5,
      validated_runs: 99, failure_rate: 0.0, recency_score: 0.5,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z', epistemic_tier: 'T2', primitive_mapping: 'HASH',
    })
    const r1 = await processEvidence(fresh, makeEvidence({ is_success: true }))
    const r2 = await processEvidence(veteran, makeEvidence({ is_success: true }))
    expect(Math.abs(r1.confidence_delta)).toBeGreaterThan(Math.abs(r2.confidence_delta))
  })
})

describe('SkillTelemetryEngine — determinism', () => {
  it('same evidence produces identical updated_record.skill_hash ×3', async () => {
    const skill = await baseSkill()
    const evidence = makeEvidence({ is_success: true })
    const r1 = await processEvidence(skill, evidence)
    const r2 = await processEvidence(skill, evidence)
    const r3 = await processEvidence(skill, evidence)
    expect(r1.updated_record.skill_hash).toBe(r2.updated_record.skill_hash)
    expect(r2.updated_record.skill_hash).toBe(r3.updated_record.skill_hash)
  })

  it('same evidence produces identical event_hash ×3', async () => {
    const skill = await baseSkill()
    const evidence = makeEvidence({ is_success: false })
    const r1 = await processEvidence(skill, evidence)
    const r2 = await processEvidence(skill, evidence)
    const r3 = await processEvidence(skill, evidence)
    expect(r1.event_hash).toBe(r2.event_hash)
    expect(r2.event_hash).toBe(r3.event_hash)
  })

  it('event_hash is 64-char hex', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence())
    expect(result.event_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(result.event_hash)).toBe(true)
  })

  it('result is frozen', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence())
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.updated_record)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const skill = await baseSkill()
    const result = await processEvidence(skill, makeEvidence())
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('different evidence produces different skill_hash', async () => {
    const skill = await baseSkill()
    const r1 = await processEvidence(skill, makeEvidence({ is_success: true }))
    const r2 = await processEvidence(skill, makeEvidence({ is_success: false }))
    expect(r1.updated_record.skill_hash).not.toBe(r2.updated_record.skill_hash)
  })
})
