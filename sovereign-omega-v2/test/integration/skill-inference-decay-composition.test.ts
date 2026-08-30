// Gate 163 — Skill Harness Phase 3+Decay Integration
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import { processEvidence } from '../../src/skill-harness/telemetry-engine.js'
import type { SkillEvidence } from '../../src/skill-harness/telemetry-engine.js'
import { inferSkillConfidence } from '../../src/skill-harness/inference-engine.js'
import { decaySkill } from '../../src/skill-harness/decay.js'
import { RalphExecutor } from '../../src/agents/executor/loop.js'

const EPOCH_TS = 1_600_000_000_000
const DAY_MS = 86_400_000
const FAKE_CTX = 'c'.repeat(64) as SHA256Hex

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function baseSkill() {
  return buildSkillRecord({
    skill_id: 'telemetry_analysis',
    name: 'Telemetry Analysis',
    confidence: 0.7,
    validated_runs: 20,
    failure_rate: 0.15,
    recency_score: 0.8,
    domain_affinity: ['telemetry', 'monitoring'],
    dependencies: [],
    evidence_refs: [],
    last_validated: new Date(EPOCH_TS).toISOString(),
    epistemic_tier: 'T2',
    primitive_mapping: 'SEQUENCE',
  })
}

function makeEvidence(i: number, is_success: boolean, loop_hash: SHA256Hex): SkillEvidence {
  return {
    skill_id: 'telemetry_analysis',
    agent_id: 'agent-compose',
    is_success,
    loop_hash,
    sequence: seq(i),
    timestamp_ms: EPOCH_TS + i * 1000,
  } as SkillEvidence
}

describe('InferenceThenDecay — pipeline ordering', () => {
  it('inference after 3 successes then decay after 30 days lowers confidence', async () => {
    const skill = await baseSkill()
    const lh = FAKE_CTX
    const batch: SkillEvidence[] = [
      makeEvidence(1, true, lh),
      makeEvidence(2, true, lh),
      makeEvidence(3, true, lh),
    ]
    const inferred = await inferSkillConfidence(skill, batch)
    expect(inferred.updated_skill.confidence).toBeGreaterThan(skill.confidence)

    const ts = EPOCH_TS + 30 * DAY_MS
    const decayed = await decaySkill(inferred.updated_skill, ts)
    expect(decayed.was_decayed).toBe(true)
    expect(decayed.updated_skill.confidence).toBeLessThan(inferred.updated_skill.confidence)
  })

  it('inference with 2 failures lowers confidence', async () => {
    const skill = await baseSkill()
    const batch: SkillEvidence[] = [
      makeEvidence(1, false, FAKE_CTX),
      makeEvidence(2, false, FAKE_CTX),
    ]
    const result = await inferSkillConfidence(skill, batch)
    expect(result.updated_skill.confidence).toBeLessThan(skill.confidence)
  })

  it('decay after grace period → decay_hash differs from no-decay hash', async () => {
    const skill = await baseSkill()
    const r1 = await decaySkill(skill, EPOCH_TS)
    const r2 = await decaySkill(skill, EPOCH_TS + 30 * DAY_MS)
    expect(r1.decay_hash).not.toBe(r2.decay_hash)
  })
})

describe('InferenceThenDecay — determinism', () => {
  it('infer then decay same inputs ×3 → identical hashes', async () => {
    const skill = await baseSkill()
    const batch: SkillEvidence[] = [makeEvidence(1, true, FAKE_CTX), makeEvidence(2, false, FAKE_CTX)]
    const ts = EPOCH_TS + 45 * DAY_MS

    const run = async () => {
      const inferred = await inferSkillConfidence(skill, batch)
      return decaySkill(inferred.updated_skill, ts)
    }
    const [d1, d2, d3] = await Promise.all([run(), run(), run()])
    expect(d1.decay_hash).toBe(d2.decay_hash)
    expect(d2.decay_hash).toBe(d3.decay_hash)
    expect(d1.updated_skill.skill_hash).toBe(d2.updated_skill.skill_hash)
  })
})

describe('RalphExecutor + evidence + decay', () => {
  it('RALPH loop_hash feeds evidence_refs and decay preserves evidence_refs', async () => {
    const executor = RalphExecutor.create('agent-loop')
    const { record } = await executor.executeLoop(FAKE_CTX, seq(1))
    const loopHash = record.loop_hash

    const evidence: SkillEvidence = makeEvidence(2, true, loopHash)
    const skill = await baseSkill()
    const telResult = await processEvidence(skill, evidence)
    expect(telResult.updated_record.evidence_refs).toContain(loopHash)

    const decayed = await decaySkill(telResult.updated_record, EPOCH_TS + 60 * DAY_MS)
    expect(decayed.was_decayed).toBe(true)
    expect(decayed.updated_skill.evidence_refs).toContain(loopHash)
  })

  it('inference result is frozen', async () => {
    const skill = await baseSkill()
    const result = await inferSkillConfidence(skill, [])
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.inference)).toBe(true)
  })

  it('decay result is frozen', async () => {
    const skill = await baseSkill()
    const result = await decaySkill(skill, EPOCH_TS + 30 * DAY_MS)
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.updated_skill)).toBe(true)
  })
})

describe('Evidence → inference → decay — confidence bounds', () => {
  it('confidence stays in [0,1] through full pipeline after 365 days', async () => {
    const skill = await buildSkillRecord({
      skill_id: 'telemetry_analysis', name: 'Low', confidence: 0.05,
      validated_runs: 5, failure_rate: 0.8, recency_score: 0.3,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: new Date(EPOCH_TS).toISOString(),
      epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const batch = [makeEvidence(1, false, FAKE_CTX), makeEvidence(2, false, FAKE_CTX), makeEvidence(3, false, FAKE_CTX)]
    const inferred = await inferSkillConfidence(skill, batch)
    const decayed = await decaySkill(inferred.updated_skill, EPOCH_TS + 365 * DAY_MS)
    expect(decayed.updated_skill.confidence).toBeGreaterThanOrEqual(0)
    expect(decayed.updated_skill.confidence).toBeLessThanOrEqual(1)
  })
})
