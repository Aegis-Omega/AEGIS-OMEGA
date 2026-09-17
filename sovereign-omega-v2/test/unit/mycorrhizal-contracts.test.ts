import { describe, expect, it } from 'vitest'
import {
  createMcmNodeObservation,
  type McmNodeObservationInputV1,
} from '../../src/metacognition/mycorrhizal-contracts.js'

const d = (c: string): string => c.repeat(64)

const base: McmNodeObservationInputV1 = {
  nodeIdentityDigest: d('1'),
  sensoriumObservationDigest: d('2'),
  observationSequence: 7,
  expectedParentStateRoot: d('3'),
  topologyDigest: d('4'),
  calibrationBps: 9000,
  evidenceSupportBps: 9000,
  evidenceFreshnessBps: 9000,
  resourcePressureBps: 1000,
  contradictionPressureBps: 0,
  verificationDemandBps: 0,
  evidenceReferences: ['receipt:beta', 'receipt:alpha'],
}

describe('MCM observation contracts', () => {
  it('carries explicit zero-authority constants and freezes output', async () => {
    const o = await createMcmNodeObservation(base)
    expect(o.authorityEffect).toBe('OBSERVATION_ONLY')
    expect(o.observationTier).toBe('T2')
    expect(o.authorityWeight).toBe(0)
    expect(o.mayGroundStateTransition).toBe(false)
    expect(o.evidenceReferences).toEqual(['receipt:alpha', 'receipt:beta'])
    expect(Object.isFrozen(o)).toBe(true)
    expect(Object.isFrozen(o.evidenceReferences)).toBe(true)
  })

  it('is deterministic for evidence reference ordering', async () => {
    const a = await createMcmNodeObservation(base)
    const b = await createMcmNodeObservation({
      ...base,
      evidenceReferences: ['receipt:alpha', 'receipt:beta'],
    })
    expect(a.observationDigest).toBe(b.observationDigest)
  })

  it('rejects malformed digests and invalid BPS', async () => {
    await expect(createMcmNodeObservation({ ...base, topologyDigest: 'bad' })).rejects.toThrow()
    await expect(createMcmNodeObservation({ ...base, calibrationBps: -1 })).rejects.toThrow()
    await expect(createMcmNodeObservation({ ...base, calibrationBps: 10001 })).rejects.toThrow()
  })

  it('rejects duplicate evidence and unsafe sequence', async () => {
    await expect(createMcmNodeObservation({
      ...base,
      evidenceReferences: ['receipt:alpha', 'receipt:alpha'],
    })).rejects.toThrow()
    await expect(createMcmNodeObservation({ ...base, observationSequence: -1 })).rejects.toThrow()
    await expect(createMcmNodeObservation({ ...base, observationSequence: Number.MAX_SAFE_INTEGER + 1 })).rejects.toThrow()
  })

  it('rejects attempted authority-bearing overrides at runtime', async () => {
    const hostile = {
      ...base,
      authorityEffect: 'AUTHORIZE',
      authorityWeight: 10000,
      mayGroundStateTransition: true,
    } as unknown as McmNodeObservationInputV1
    await expect(createMcmNodeObservation(hostile)).rejects.toThrow()
  })
})
