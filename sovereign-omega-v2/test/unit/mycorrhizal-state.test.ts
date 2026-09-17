import { describe, expect, it } from 'vitest'
import {
  createMcmNodeObservation,
  type McmNodeObservationInputV1,
} from '../../src/metacognition/mycorrhizal-contracts.js'
import { reduceMycorrhizalCollectiveState } from '../../src/metacognition/mycorrhizal-state.js'

const d = (c: string): string => c.repeat(64)

function input(node: string, seq: number, calibrationBps = 9000): McmNodeObservationInputV1 {
  return {
    nodeIdentityDigest: d(node),
    sensoriumObservationDigest: d(String((Number(node) + 3) % 10)),
    observationSequence: seq,
    expectedParentStateRoot: d('a'),
    topologyDigest: d('b'),
    calibrationBps,
    evidenceSupportBps: 8000,
    evidenceFreshnessBps: 7000,
    resourcePressureBps: 2000,
    contradictionPressureBps: 1000,
    verificationDemandBps: 3000,
    evidenceReferences: [`receipt:${node}`],
  }
}

async function observation(node: string, seq: number, calibrationBps = 9000) {
  return createMcmNodeObservation(input(node, seq, calibrationBps))
}

describe('Mycorrhizal collective state', () => {
  it('rejects an empty observation set', async () => {
    await expect(reduceMycorrhizalCollectiveState([])).rejects.toThrow()
  })

  it('rejects mixed parent roots and topologies', async () => {
    const a = await observation('1', 1)
    const b = await createMcmNodeObservation({ ...input('2', 2), expectedParentStateRoot: d('c') })
    const c = await createMcmNodeObservation({ ...input('3', 3), topologyDigest: d('d') })
    await expect(reduceMycorrhizalCollectiveState([a, b])).rejects.toThrow()
    await expect(reduceMycorrhizalCollectiveState([a, c])).rejects.toThrow()
  })

  it('is order-insensitive and idempotent', async () => {
    const a = await observation('1', 1, 6000)
    const b = await observation('2', 2, 8000)
    const c = await observation('3', 3, 10000)
    const s1 = await reduceMycorrhizalCollectiveState([a, b, c])
    const s2 = await reduceMycorrhizalCollectiveState([c, a, b])
    const s3 = await reduceMycorrhizalCollectiveState([b, c, a])
    expect(s1.stateRoot).toBe(s2.stateRoot)
    expect(s1.stateRoot).toBe(s3.stateRoot)
    expect(s1.collectiveCalibrationBps).toBe(8000)
    expect(Object.isFrozen(s1)).toBe(true)
    expect(Object.isFrozen(s1.nodeObservationDigests)).toBe(true)
  })

  it('rejects conflicting duplicate node/sequence entries', async () => {
    const a = await observation('1', 7, 9000)
    const b = await createMcmNodeObservation({ ...input('1', 7, 8500), sensoriumObservationDigest: d('9') })
    await expect(reduceMycorrhizalCollectiveState([a, b])).rejects.toThrow()
  })
})
