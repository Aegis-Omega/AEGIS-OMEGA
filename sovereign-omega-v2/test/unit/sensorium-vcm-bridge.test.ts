import { describe, expect, it } from 'vitest'
import {
  capacityPressureBps,
  nextLogisticLoad,
  nextRetentionBps,
  SensoriumModelError,
} from '../../src/sensorium/vcm-bridge.js'
import { createSensoriumObservation } from '../../src/sensorium/sensorium-observation.js'

describe('VCM bridge', () => {
  it('applies the discrete Verhulst-style step without exceeding carrying capacity', () => {
    expect(nextLogisticLoad(40n, 100n, 1000)).toBe(42n)
    expect(nextLogisticLoad(100n, 100n, 1000)).toBe(100n)
  })

  it('computes bounded capacity pressure', () => {
    expect(capacityPressureBps(40n, 100n)).toBe(4000)
    expect(capacityPressureBps(100n, 100n)).toBe(10000)
    expect(capacityPressureBps(150n, 100n)).toBe(10000)
  })

  it('applies discrete retention decay and reinforcement within BPS bounds', () => {
    expect(nextRetentionBps(8000, 500, 200)).toBe(7800)
    expect(nextRetentionBps(9800, 0, 500)).toBe(10000)
  })

  it('fails closed on invalid model domains', () => {
    expect(() => nextLogisticLoad(1n, 0n, 1000)).toThrow(SensoriumModelError)
    expect(() => nextLogisticLoad(101n, 100n, 1000)).toThrow(SensoriumModelError)
    expect(() => nextRetentionBps(8000, 10_001, 0)).toThrow(SensoriumModelError)
  })

  it('derives VCM fields inside the observation rather than accepting caller predictions', async () => {
    const observation = await createSensoriumObservation({
      sourceKind: 'runtime',
      sourceIdentityDigest: 'a'.repeat(64),
      subjectResourceDigest: 'b'.repeat(64),
      observationSequence: 7,
      expectedParentStateRoot: 'c'.repeat(64),
      topologyDigest: 'd'.repeat(64),
      activeLoad: 40n,
      carryingCapacity: 100n,
      growthRateBps: 1000,
      retentionBps: 8000,
      decayBps: 500,
      reinforcementBps: 200,
      observationQualityBps: 9000,
      evidenceReferences: ['receipt://a'],
    })

    expect(observation.predictedNextLoad).toBe(42n)
    expect(observation.capacityPressureBps).toBe(4000)
    expect(observation.predictedNextRetentionBps).toBe(7800)
    expect(observation.modelStatus).toBe('MODEL_DEFINED')
    expect(observation.empiricalStatus).toBe('NOT_ESTABLISHED')
  })
})
