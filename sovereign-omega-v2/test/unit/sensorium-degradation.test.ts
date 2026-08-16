import { describe, expect, it } from 'vitest'
import { createSensoriumObservation } from '../../src/sensorium/sensorium-observation.js'
import {
  applyConsequenceCap,
  recommendSensoriumDegradation,
  type SensoriumRecommendation,
} from '../../src/sensorium/sensorium-degradation.js'

const baseInput = {
  sourceKind: 'runtime' as const,
  sourceIdentityDigest: 'a'.repeat(64),
  subjectResourceDigest: 'b'.repeat(64),
  observationSequence: 7,
  expectedParentStateRoot: 'c'.repeat(64),
  topologyDigest: 'd'.repeat(64),
  activeLoad: 40n,
  carryingCapacity: 100n,
  growthRateBps: 1000,
  retentionBps: 8000,
  decayBps: 0,
  reinforcementBps: 0,
  observationQualityBps: 9000,
  evidenceReferences: ['receipt://a'],
}

async function recommendation(overrides: Partial<typeof baseInput>): Promise<SensoriumRecommendation> {
  const observation = await createSensoriumObservation({ ...baseInput, ...overrides })
  return recommendSensoriumDegradation(observation).recommendation
}

describe('Sensorium contractive degradation', () => {
  it('never increases an admitted consequence class', () => {
    const degraded = { recommendation: 'DEGRADED' as const, maxConsequenceClass: 'D1' as const }

    expect(applyConsequenceCap('D0', degraded)).toBe('D0')
    expect(applyConsequenceCap('D1', degraded)).toBe('D1')
    expect(applyConsequenceCap('D3', degraded)).toBe('D1')
  })

  it('suspension caps at D0 and repeated application is idempotent', () => {
    const suspended = { recommendation: 'SUSPENDED' as const, maxConsequenceClass: 'D0' as const }
    const once = applyConsequenceCap('D3', suspended)
    const twice = applyConsequenceCap(once, suspended)

    expect(once).toBe('D0')
    expect(twice).toBe(once)
  })

  it('leaves an admitted class unchanged only when no degradation is recommended', () => {
    const unchanged = { recommendation: 'UNCHANGED' as const, maxConsequenceClass: null }
    expect(applyConsequenceCap('D2', unchanged)).toBe('D2')
  })

  it('applies observation quality thresholds', async () => {
    expect(await recommendation({ observationQualityBps: 8000 })).toBe('UNCHANGED')
    expect(await recommendation({ observationQualityBps: 7999 })).toBe('DEGRADED')
    expect(await recommendation({ observationQualityBps: 4999 })).toBe('SUSPENDED')
  })

  it('applies capacity pressure thresholds', async () => {
    expect(await recommendation({ activeLoad: 79n })).toBe('UNCHANGED')
    expect(await recommendation({ activeLoad: 80n })).toBe('DEGRADED')
    expect(await recommendation({ activeLoad: 95n })).toBe('SUSPENDED')
  })

  it('applies predicted retention thresholds', async () => {
    expect(await recommendation({ retentionBps: 7000 })).toBe('UNCHANGED')
    expect(await recommendation({ retentionBps: 6999 })).toBe('DEGRADED')
    expect(await recommendation({ retentionBps: 3999 })).toBe('SUSPENDED')
  })

  it('chooses the most restrictive signal and binds freshness fields', async () => {
    const observation = await createSensoriumObservation({
      ...baseInput,
      observationQualityBps: 7999,
      activeLoad: 96n,
    })
    const degradation = recommendSensoriumDegradation(observation)

    expect(degradation.recommendation).toBe('SUSPENDED')
    expect(degradation.maxConsequenceClass).toBe('D0')
    expect(degradation.authorityEffect).toBe('OBSERVATION_ONLY')
    expect(degradation.observationDigest).toBe(observation.observationDigest)
    expect(degradation.validForObservationSequence).toBe(observation.observationSequence)
    expect(degradation.validForParentStateRoot).toBe(observation.expectedParentStateRoot)
    expect(degradation.validForTopologyDigest).toBe(observation.topologyDigest)
    expect('grantsAuthority' in degradation).toBe(false)
  })
})
