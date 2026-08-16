import { describe, expect, it } from 'vitest'
import { createSensoriumObservation, SensoriumObservationError } from '../../src/sensorium/sensorium-observation.js'

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
  decayBps: 500,
  reinforcementBps: 200,
  observationQualityBps: 9000,
  evidenceReferences: ['receipt://b', 'receipt://a'],
}

describe('SensoriumObservationV1', () => {
  it('is deterministic, evidence-order invariant, and observation-only', async () => {
    const first = await createSensoriumObservation(baseInput)
    const second = await createSensoriumObservation({ ...baseInput, evidenceReferences: ['receipt://a', 'receipt://b'] })

    expect(first.observationDigest).toBe(second.observationDigest)
    expect(first.observationId).toBe(first.observationDigest)
    expect(first.authorityEffect).toBe('OBSERVATION_ONLY')
    expect('grantsAuthority' in first).toBe(false)
  })

  it('changes digest when an authority-relevant binding changes', async () => {
    const first = await createSensoriumObservation(baseInput)
    const changedIdentity = await createSensoriumObservation({ ...baseInput, sourceIdentityDigest: 'e'.repeat(64) })
    const changedResource = await createSensoriumObservation({ ...baseInput, subjectResourceDigest: 'f'.repeat(64) })
    const changedParent = await createSensoriumObservation({ ...baseInput, expectedParentStateRoot: '1'.repeat(64) })
    const changedTopology = await createSensoriumObservation({ ...baseInput, topologyDigest: '2'.repeat(64) })

    expect(changedIdentity.observationDigest).not.toBe(first.observationDigest)
    expect(changedResource.observationDigest).not.toBe(first.observationDigest)
    expect(changedParent.observationDigest).not.toBe(first.observationDigest)
    expect(changedTopology.observationDigest).not.toBe(first.observationDigest)
  })

  it('does not hash audit-only wall-clock metadata', async () => {
    const first = await createSensoriumObservation({ ...baseInput, auditObservedAt: '2026-08-16T05:00:00Z' })
    const second = await createSensoriumObservation({ ...baseInput, auditObservedAt: '2026-08-16T06:00:00Z' })

    expect(second.observationDigest).toBe(first.observationDigest)
  })

  it('fails closed on invalid capacity, BPS, digest, or duplicate evidence', async () => {
    await expect(createSensoriumObservation({ ...baseInput, carryingCapacity: 0n })).rejects.toBeInstanceOf(SensoriumObservationError)
    await expect(createSensoriumObservation({ ...baseInput, growthRateBps: 10_001 })).rejects.toBeInstanceOf(SensoriumObservationError)
    await expect(createSensoriumObservation({ ...baseInput, topologyDigest: 'not-a-digest' })).rejects.toBeInstanceOf(SensoriumObservationError)
    await expect(createSensoriumObservation({ ...baseInput, evidenceReferences: ['receipt://a', 'receipt://a'] })).rejects.toBeInstanceOf(SensoriumObservationError)
  })
})
