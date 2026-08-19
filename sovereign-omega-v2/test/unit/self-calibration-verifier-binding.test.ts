import { describe, expect, it } from 'vitest'
import { hashValue } from '../../src/core/hashing.js'
import { CalibrationDomain } from '../../src/core/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import type { VerifierOutput } from '../../src/verifier/types.js'
import {
  SelfCalibrationError,
  SelfCalibrationLedgerV2,
  certifySelfCalibrationLedgerV2,
  createSelfCalibrationV2,
  createSelfOutcomeObservationFromVerifier,
  createSelfPredictionV2,
} from '../../src/metacognition/self-calibration.js'
import type {
  SelfCalibrationRecordV2,
} from '../../src/metacognition/self-calibration.js'

const ACTION = '1'.repeat(64) as SHA256Hex
const CLAIM_A = 'self-action-claim-a'
const CLAIM_B = 'self-action-claim-b'
const SEQ1 = 1n as SequenceNumber

async function makeVerifierOutput(
  claim_id: string,
  passed: boolean,
): Promise<VerifierOutput> {
  const verifier_id = 'self-model-execution-verifier-v1'
  const raw_confidence = passed ? 0.99 : 0.01
  const artifact_hash = await hashValue({
    verifier_id,
    claim_id,
    passed,
    raw_confidence,
  })

  return {
    verifier_id,
    claim_id,
    passed,
    raw_confidence,
    evidence_refs: Object.freeze(['self-model-fixture']),
    latency_ms: 1,
    determinism_flag: true,
    verifier_version: '1.0.0',
    trust_class: CalibrationDomain.GROUND_TRUTH,
    artifact_hash,
  }
}

async function makeV2Calibration(): Promise<SelfCalibrationRecordV2> {
  const prediction = await createSelfPredictionV2({
    action_digest: ACTION,
    verifier_claim_id: CLAIM_A,
    predicted_success_bps: 7500,
  })
  const verifier = await makeVerifierOutput(CLAIM_A, true)
  const observation = await createSelfOutcomeObservationFromVerifier(
    prediction,
    verifier,
  )
  return createSelfCalibrationV2(prediction, observation)
}

async function rehashV2Calibration(
  calibration: SelfCalibrationRecordV2,
  overrides: Partial<SelfCalibrationRecordV2>,
): Promise<SelfCalibrationRecordV2> {
  const candidate = { ...calibration, ...overrides }
  const calibration_hash = await hashValue({
    receipt_kind: candidate.receipt_kind,
    schema_version: candidate.schema_version,
    prediction_hash: candidate.prediction_hash,
    action_digest: candidate.action_digest,
    verifier_claim_id: candidate.verifier_claim_id,
    verifier_id: candidate.verifier_id,
    verifier_raw_confidence: candidate.verifier_raw_confidence,
    observation_evidence_digest: candidate.observation_evidence_digest,
    predicted_success_bps: candidate.predicted_success_bps,
    observed_success: candidate.observed_success,
    absolute_error_bps: candidate.absolute_error_bps,
    authority: candidate.authority,
    acceptable_for_effect_truth: candidate.acceptable_for_effect_truth,
  })
  return { ...candidate, calibration_hash }
}

describe('verifier-bound self-calibration V2', () => {
  it('derives observed outcome from a verifier artifact and remains evidence-only', async () => {
    const prediction = await createSelfPredictionV2({
      action_digest: ACTION,
      verifier_claim_id: CLAIM_A,
      predicted_success_bps: 7500,
    })
    const verifier = await makeVerifierOutput(CLAIM_A, true)

    const observation = await createSelfOutcomeObservationFromVerifier(
      prediction,
      verifier,
    )
    const calibration = await createSelfCalibrationV2(prediction, observation)

    expect(observation.observed_success).toBe(true)
    expect(observation.observation_evidence_digest).toBe(verifier.artifact_hash)
    expect(observation.verifier_claim_id).toBe(CLAIM_A)
    expect(observation.authority).toBe('NONE')
    expect(observation.acceptable_for_effect_truth).toBe(false)
    expect(calibration.absolute_error_bps).toBe(2500)
    expect(calibration.authority).toBe('NONE')
    expect(calibration.acceptable_for_effect_truth).toBe(false)
  })

  it('rejects a verifier verdict changed without recomputing its artifact hash', async () => {
    const prediction = await createSelfPredictionV2({
      action_digest: ACTION,
      verifier_claim_id: CLAIM_A,
      predicted_success_bps: 7500,
    })
    const verifier = await makeVerifierOutput(CLAIM_A, true)
    const forged: VerifierOutput = { ...verifier, passed: false }

    await expect(
      createSelfOutcomeObservationFromVerifier(prediction, forged),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('rejects a valid verifier artifact produced for another claim', async () => {
    const prediction = await createSelfPredictionV2({
      action_digest: ACTION,
      verifier_claim_id: CLAIM_A,
      predicted_success_bps: 7500,
    })
    const verifierForOtherClaim = await makeVerifierOutput(CLAIM_B, true)

    await expect(
      createSelfOutcomeObservationFromVerifier(prediction, verifierForOtherClaim),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('replays a valid V2 calibration with evidence-only authority', async () => {
    const calibration = await makeV2Calibration()
    const { ledger } = await SelfCalibrationLedgerV2.empty().append(
      calibration,
      SEQ1,
    )
    const certificate = await certifySelfCalibrationLedgerV2(ledger.getAll())

    expect(certificate.is_valid).toBe(true)
    expect(certificate.entry_count).toBe(1)
    expect(certificate.authority).toBe('NONE')
    expect(certificate.acceptable_for_effect_truth).toBe(false)
  })

  it('rejects a rehashed V2 calibration whose outcome contradicts the verifier artifact', async () => {
    const calibration = await makeV2Calibration()
    const forged = await rehashV2Calibration(calibration, {
      observed_success: false,
      absolute_error_bps: 7500,
    })

    await expect(
      SelfCalibrationLedgerV2.empty().append(forged, SEQ1),
    ).rejects.toThrow(SelfCalibrationError)
  })
})
