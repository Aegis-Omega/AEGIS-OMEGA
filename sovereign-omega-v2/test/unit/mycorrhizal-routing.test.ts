import { describe, expect, it } from 'vitest'
import {
  createMcmNodeObservation,
  type McmNodeObservationInputV1,
} from '../../src/metacognition/mycorrhizal-contracts.js'
import { reduceMycorrhizalCollectiveState } from '../../src/metacognition/mycorrhizal-state.js'
import { deriveMcmVerificationRequests } from '../../src/metacognition/mycorrhizal-routing.js'

const d = (c: string): string => c.repeat(64)

function input(overrides: Partial<McmNodeObservationInputV1> = {}): McmNodeObservationInputV1 {
  return {
    nodeIdentityDigest: d('1'),
    sensoriumObservationDigest: d('2'),
    observationSequence: 1,
    expectedParentStateRoot: d('3'),
    topologyDigest: d('4'),
    calibrationBps: 9000,
    evidenceSupportBps: 9000,
    evidenceFreshnessBps: 9000,
    resourcePressureBps: 1000,
    contradictionPressureBps: 0,
    verificationDemandBps: 0,
    evidenceReferences: ['receipt:z', 'receipt:a'],
    ...overrides,
  }
}

async function route(overrides: Partial<McmNodeObservationInputV1>) {
  const o = await createMcmNodeObservation(input(overrides))
  const s = await reduceMycorrhizalCollectiveState([o])
  return deriveMcmVerificationRequests(s, [o])
}

describe('MCM verification routing', () => {
  it.each([
    [{ calibrationBps: 6999 }, 'LOW_CALIBRATION'],
    [{ evidenceSupportBps: 6999 }, 'LOW_EVIDENCE_SUPPORT'],
    [{ evidenceFreshnessBps: 6999 }, 'STALE_EVIDENCE'],
    [{ resourcePressureBps: 8000 }, 'RESOURCE_PRESSURE'],
    [{ contradictionPressureBps: 6000 }, 'CONTRADICTION_PRESSURE'],
    [{ verificationDemandBps: 7000 }, 'EXPLICIT_VERIFICATION_DEMAND'],
  ] as const)('emits %s at frozen threshold', async (overrides, reason) => {
    const requests = await route(overrides)
    expect(requests).toHaveLength(1)
    expect(requests[0]!.reasonCodes).toContain(reason)
  })

  it('canonicalizes reasons/evidence and carries zero authority', async () => {
    const requests = await route({ calibrationBps: 6500, verificationDemandBps: 7500 })
    const r = requests[0]!
    expect(r.reasonCodes).toEqual(['EXPLICIT_VERIFICATION_DEMAND', 'LOW_CALIBRATION'])
    expect(r.evidenceReferences).toEqual(['receipt:a', 'receipt:z'])
    expect(r.priorityBps).toBe(7500)
    expect(r.authorityEffect).toBe('OBSERVATION_ONLY')
    expect(r.authorityWeight).toBe(0)
    expect(r.mayGroundStateTransition).toBe(false)
    const serialized = JSON.stringify(r)
    for (const forbidden of ['ADMITTED', 'EffectReceipt', 'providerInvocation', 'fencingToken', 'leaseGrant']) {
      expect(serialized).not.toContain(forbidden)
    }
  })

  it('rejects routing observations that are not bound into the supplied state', async () => {
    const a = await createMcmNodeObservation(input())
    const b = await createMcmNodeObservation(input({ nodeIdentityDigest: d('5'), observationSequence: 2 }))
    const state = await reduceMycorrhizalCollectiveState([a])
    await expect(Promise.resolve().then(() => deriveMcmVerificationRequests(state, [b]))).rejects.toThrow()
  })

  it('rejects a forged valid-looking collective state root', async () => {
    const observation = await createMcmNodeObservation(input())
    const state = await reduceMycorrhizalCollectiveState([observation])
    const forged = Object.freeze({ ...state, stateRoot: d('f') })
    await expect(Promise.resolve().then(() => deriveMcmVerificationRequests(forged, [observation]))).rejects.toThrow(/state root/i)
  })

  it('rejects collective metrics changed without rebinding the state root', async () => {
    const observation = await createMcmNodeObservation(input())
    const state = await reduceMycorrhizalCollectiveState([observation])
    const forged = Object.freeze({
      ...state,
      collectiveCalibrationBps: state.collectiveCalibrationBps - 1,
    })
    await expect(Promise.resolve().then(() => deriveMcmVerificationRequests(forged, [observation]))).rejects.toThrow(/state root/i)
  })
})
