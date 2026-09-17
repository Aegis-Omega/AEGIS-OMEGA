import { describe, expect, it } from 'vitest'
import { createMcmNodeObservation } from '../../src/metacognition/mycorrhizal-contracts.js'
import { reduceMycorrhizalCollectiveState } from '../../src/metacognition/mycorrhizal-state.js'
import { deriveMcmVerificationRequests } from '../../src/metacognition/mycorrhizal-routing.js'
import {
  ONE_BNA_SOURCE_SHA256,
  ONE_BNA_V3_BENCHMARK_DIGEST,
  ONE_BNA_V4_CROSS_RUNTIME_DIGEST,
  create1BnaMcmObservationInput,
} from '../../src/metacognition/mycorrhizal-1bna.js'

const d = (c: string): string => c.repeat(64)

const base = {
  sourceSha256: ONE_BNA_SOURCE_SHA256,
  v3BenchmarkDigest: ONE_BNA_V3_BENCHMARK_DIGEST,
  v4CrossRuntimeDigest: ONE_BNA_V4_CROSS_RUNTIME_DIGEST,
  nodeIdentityDigest: d('7'),
  sensoriumObservationDigest: d('8'),
  observationSequence: 1,
  expectedParentStateRoot: d('9'),
  topologyDigest: d('a'),
}

describe('1BNA -> Mycorrhizal evidence synchronization', () => {
  it('pins exact source and benchmark identities', () => {
    expect(ONE_BNA_SOURCE_SHA256).toBe('df42f1506792f191b957227b061360652adcf6f813eb69d9ec553067ea584670')
    expect(ONE_BNA_V3_BENCHMARK_DIGEST).toBe('0d23a1449c4110c11fe99809df1fd9bb55216d8b14eee75cdcff81f21f794276')
    expect(ONE_BNA_V4_CROSS_RUNTIME_DIGEST).toBe('f8197fa4ee9d37fd81bd4f3d1d9391d8eff153aefc3d0ff5e0ecce2ade1d053a')
  })

  it('creates the conservative model-defined MCM profile', () => {
    const input = create1BnaMcmObservationInput(base)
    expect(input.calibrationBps).toBe(6500)
    expect(input.evidenceSupportBps).toBe(9000)
    expect(input.evidenceFreshnessBps).toBe(8000)
    expect(input.resourcePressureBps).toBe(1000)
    expect(input.contradictionPressureBps).toBe(0)
    expect(input.verificationDemandBps).toBe(7500)
    expect(Object.isFrozen(input)).toBe(true)
  })

  it('fails closed on source or cross-runtime digest drift', () => {
    expect(() => create1BnaMcmObservationInput({ ...base, sourceSha256: d('0') })).toThrow()
    expect(() => create1BnaMcmObservationInput({ ...base, v4CrossRuntimeDigest: d('1') })).toThrow()
  })

  it('rejects truth or authority promotion fields', () => {
    expect(() => create1BnaMcmObservationInput({
      ...base,
      biologicalMechanismEstablished: true,
    } as never)).toThrow()
    expect(() => create1BnaMcmObservationInput({
      ...base,
      standard3dnaVerified: true,
    } as never)).toThrow()
    expect(() => create1BnaMcmObservationInput({
      ...base,
      authorityEffect: 'AUTHORIZE',
    } as never)).toThrow()
  })

  it('synchronizes as verification demand without admission/effect authority', async () => {
    const input = create1BnaMcmObservationInput(base)
    const observation = await createMcmNodeObservation(input)
    const state = await reduceMycorrhizalCollectiveState([observation])
    const requests = deriveMcmVerificationRequests(state, [observation])
    expect(requests).toHaveLength(1)
    expect(requests[0]!.reasonCodes).toEqual(['EXPLICIT_VERIFICATION_DEMAND', 'LOW_CALIBRATION'])
    expect(observation.authorityEffect).toBe('OBSERVATION_ONLY')
    expect(observation.authorityWeight).toBe(0)
    expect(observation.mayGroundStateTransition).toBe(false)
    const serialized = JSON.stringify({ observation, state, requests })
    for (const forbidden of ['ADMITTED', 'EffectReceipt', 'providerInvocation', 'leaseGrant', 'fencingToken']) {
      expect(serialized).not.toContain(forbidden)
    }
  })
})
