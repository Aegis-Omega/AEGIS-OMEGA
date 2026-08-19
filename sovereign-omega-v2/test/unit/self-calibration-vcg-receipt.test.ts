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
  applySelfCalibrationVCGAdmissionReceipt,
  createSelfCalibrationVCGAdmissionReceipt,
} from '../../src/metacognition/self-calibration-vcg.js'
import type {
  SelfCalibrationVCGAdmissionReceiptV1,
} from '../../src/metacognition/self-calibration-vcg.js'
import type { SelfCalibrationRecordV2 } from '../../src/metacognition/self-calibration.js'

const ACTION = '4'.repeat(64) as SHA256Hex
const CLAIM = 'self-calibration-vcg-receipt-claim'
const TS = 2_000

function registerVerifier(
  verifier_id: string,
  trust_class: CalibrationDomain,
  version: string,
): void {
  const verifier: Verifier = {
    definition: {
      verifier_id,
      verifier_class: VerifierClass.V1_DETERMINISTIC,
      trust_class,
      version,
      description: 'self-calibration receipt test verifier',
      max_latency_ms: 1_000,
      is_deterministic: true,
    },
    async verify(): Promise<VerifierOutput> {
      throw new Error('not invoked by receipt tests')
    },
  }
  verifierRegistry.register(verifier)
}

async function makeCalibration(
  verifier_id: string,
): Promise<SelfCalibrationRecordV2> {
  const prediction = await createSelfPredictionV2({
    action_digest: ACTION,
    verifier_claim_id: CLAIM,
    predicted_success_bps: 7_500,
  })
  const raw_confidence = 0.99
  const artifact_hash = await hashValue({
    verifier_id,
    claim_id: CLAIM,
    passed: true,
    raw_confidence,
  })
  const output: VerifierOutput = {
    verifier_id,
    claim_id: CLAIM,
    passed: true,
    raw_confidence,
    evidence_refs: Object.freeze(['receipt-fixture']),
    latency_ms: 1,
    determinism_flag: true,
    verifier_version: 'artifact-version-does-not-control-registry-weight',
    trust_class: CalibrationDomain.ADVISORY_EXCLUDED,
    artifact_hash,
  }
  const observation = await createSelfOutcomeObservationFromVerifier(prediction, output)
  return createSelfCalibrationV2(prediction, observation)
}

describe('self-calibration VCG admission receipt replay', () => {
  it('content-addresses the registry eligibility snapshot and calibration binding', async () => {
    const verifierId = 'self-cal-vcg-receipt-ground-v1'
    registerVerifier(verifierId, CalibrationDomain.GROUND_TRUTH, 'registry-1.0.0')
    const calibration = await makeCalibration(verifierId)

    const receipt = await createSelfCalibrationVCGAdmissionReceipt(calibration, TS)

    expect(receipt.receipt_kind).toBe('SELF_CALIBRATION_VCG_ADMISSION_RECEIPT_V1')
    expect(receipt.schema_version).toBe('1.0.0')
    expect(receipt.calibration_hash).toBe(calibration.calibration_hash)
    expect(receipt.status).toBe('ADMITTED')
    expect(receipt.verifier_snapshot.verifier_id).toBe(verifierId)
    expect(receipt.verifier_snapshot.trust_class).toBe(CalibrationDomain.GROUND_TRUTH)
    expect(receipt.verifier_snapshot.version).toBe('registry-1.0.0')
    expect(receipt.verifier_snapshot.definition_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(receipt.receipt_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(receipt.authority).toBe('NONE')
    expect(receipt.acceptable_for_effect_truth).toBe(false)
  })

  it('replays from the receipt snapshot even after the live registry trust class drifts', async () => {
    const verifierId = 'self-cal-vcg-receipt-drift-v1'
    registerVerifier(verifierId, CalibrationDomain.GROUND_TRUTH, 'registry-1.0.0')
    const calibration = await makeCalibration(verifierId)
    const receipt = await createSelfCalibrationVCGAdmissionReceipt(calibration, TS)

    registerVerifier(verifierId, CalibrationDomain.ADVISORY_EXCLUDED, 'registry-2.0.0')

    const tracker = new VCGTracker('self-calibration-receipt-replay')
    const status = await applySelfCalibrationVCGAdmissionReceipt(
      tracker,
      calibration,
      receipt,
    )
    const metric = tracker.compute(TS)

    expect(status).toBe('ADMITTED')
    expect(metric.sample_count).toBe(1)
    expect(metric.effective_sample_size).toBeCloseTo(1, 12)
    expect(metric.weighted_error).toBeCloseTo(0.25, 12)
  })

  it('rejects a snapshot/status edit that is not reflected in receipt_hash', async () => {
    const verifierId = 'self-cal-vcg-receipt-tamper-v1'
    registerVerifier(verifierId, CalibrationDomain.GROUND_TRUTH, 'registry-1.0.0')
    const calibration = await makeCalibration(verifierId)
    const receipt = await createSelfCalibrationVCGAdmissionReceipt(calibration, TS)
    const forged: SelfCalibrationVCGAdmissionReceiptV1 = {
      ...receipt,
      status: 'EXCLUDED',
      verifier_snapshot: {
        ...receipt.verifier_snapshot,
        trust_class: CalibrationDomain.ADVISORY_EXCLUDED,
      },
    }
    const tracker = new VCGTracker('self-calibration-receipt-tamper')

    await expect(
      applySelfCalibrationVCGAdmissionReceipt(tracker, calibration, forged),
    ).rejects.toThrow(SelfCalibrationVCGAdmissionError)

    expect(tracker.compute(TS).sample_count).toBe(0)
  })
})
