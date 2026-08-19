import { describe, expect, it } from 'vitest'
import { VCGTracker } from '../../src/calibration/vcg.js'
import { hashValue } from '../../src/core/hashing.js'
import { CalibrationDomain, VerifierClass } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import { verifierRegistry } from '../../src/verifier/registry.js'
import type { Verifier, VerifierOutput } from '../../src/verifier/types.js'
import {
  createSelfCalibrationV2,
  createSelfOutcomeObservationFromVerifier,
  createSelfPredictionV2,
} from '../../src/metacognition/self-calibration.js'
import {
  SelfCalibrationVCGAdmissionError,
  admitSelfCalibrationV2ToVCG,
} from '../../src/metacognition/self-calibration-vcg.js'
import type { SelfCalibrationRecordV2 } from '../../src/metacognition/self-calibration.js'

const ACTION = '3'.repeat(64) as SHA256Hex
const CLAIM = 'self-calibration-vcg-claim'
const TS = 1_000

function registerVerifier(
  verifier_id: string,
  trust_class: CalibrationDomain,
): void {
  const verifier: Verifier = {
    definition: {
      verifier_id,
      verifier_class: VerifierClass.V1_DETERMINISTIC,
      trust_class,
      version: '1.0.0',
      description: 'self-calibration VCG test verifier',
      max_latency_ms: 1_000,
      is_deterministic: true,
    },
    async verify(): Promise<VerifierOutput> {
      throw new Error('not invoked by calibration adapter tests')
    },
  }
  verifierRegistry.register(verifier)
}

async function makeVerifierOutput(
  verifier_id: string,
  passed: boolean,
): Promise<VerifierOutput> {
  const raw_confidence = passed ? 0.99 : 0.01
  const artifact_hash = await hashValue({
    verifier_id,
    claim_id: CLAIM,
    passed,
    raw_confidence,
  })
  return {
    verifier_id,
    claim_id: CLAIM,
    passed,
    raw_confidence,
    evidence_refs: Object.freeze(['vcg-self-model-fixture']),
    latency_ms: 1,
    determinism_flag: true,
    verifier_version: '1.0.0',
    trust_class: CalibrationDomain.ADVISORY_EXCLUDED,
    artifact_hash,
  }
}

async function makeCalibration(
  verifier_id: string,
  predicted_success_bps = 7_500,
  passed = true,
): Promise<SelfCalibrationRecordV2> {
  const prediction = await createSelfPredictionV2({
    action_digest: ACTION,
    verifier_claim_id: CLAIM,
    predicted_success_bps,
  })
  const output = await makeVerifierOutput(verifier_id, passed)
  const observation = await createSelfOutcomeObservationFromVerifier(prediction, output)
  return createSelfCalibrationV2(prediction, observation)
}

describe('self-calibration V2 -> existing VCG adapter', () => {
  it('admits a registry-ground-truth verifier using self prediction confidence', async () => {
    const verifierId = 'self-cal-vcg-ground-truth-v1'
    registerVerifier(verifierId, CalibrationDomain.GROUND_TRUTH)
    const calibration = await makeCalibration(verifierId, 7_500, true)
    const tracker = new VCGTracker('self-calibration-v2-ground-truth')

    const status = await admitSelfCalibrationV2ToVCG(tracker, calibration, TS)
    const metric = tracker.compute(TS)

    expect(status).toBe('ADMITTED')
    expect(metric.sample_count).toBe(1)
    expect(metric.weighted_error).toBeCloseTo(0.25, 12)
    expect(tracker.getBrierScore()).toBeCloseTo(0.0625, 12)
  })

  it('rejects a cryptographically valid calibration from an unregistered verifier', async () => {
    const calibration = await makeCalibration('unregistered-self-cal-vcg-verifier')
    const tracker = new VCGTracker('self-calibration-v2-unknown')

    await expect(
      admitSelfCalibrationV2ToVCG(tracker, calibration, TS),
    ).rejects.toThrow(SelfCalibrationVCGAdmissionError)

    expect(tracker.compute(TS).sample_count).toBe(0)
  })

  it('excludes a registry-advisory verifier instead of admitting it to aggregate calibration', async () => {
    const verifierId = 'self-cal-vcg-advisory-v1'
    registerVerifier(verifierId, CalibrationDomain.ADVISORY_EXCLUDED)
    const calibration = await makeCalibration(verifierId)
    const tracker = new VCGTracker('self-calibration-v2-advisory')

    const status = await admitSelfCalibrationV2ToVCG(tracker, calibration, TS)

    expect(status).toBe('EXCLUDED')
    expect(tracker.compute(TS).sample_count).toBe(0)
  })

  it('rejects invalid event-substrate timestamps before mutating the tracker', async () => {
    const verifierId = 'self-cal-vcg-timestamp-v1'
    registerVerifier(verifierId, CalibrationDomain.GROUND_TRUTH)
    const calibration = await makeCalibration(verifierId)
    const invalidTimestamps = [
      -1,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      1.5,
      Number.MAX_SAFE_INTEGER + 1,
    ]

    for (const timestamp of invalidTimestamps) {
      const tracker = new VCGTracker(`self-calibration-v2-invalid-time-${String(timestamp)}`)

      await expect(
        admitSelfCalibrationV2ToVCG(tracker, calibration, timestamp),
      ).rejects.toThrow(SelfCalibrationVCGAdmissionError)

      expect(tracker.compute(TS).sample_count).toBe(0)
    }
  })
})
