import { describe, expect, it } from 'vitest'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  SELF_CALIBRATION_GENESIS_HASH,
  SelfCalibrationError,
  SelfCalibrationLedger,
  calibrationToMetacognitiveObservation,
  certifySelfCalibrationLedger,
  createSelfCalibration,
  createSelfOutcomeObservation,
  createSelfPrediction,
} from '../../src/metacognition/self-calibration.js'
import type {
  SelfCalibrationLedgerEntry,
  SelfCalibrationRecordV1,
} from '../../src/metacognition/self-calibration.js'

const ACTION = '1'.repeat(64) as SHA256Hex
const EVIDENCE = '2'.repeat(64) as SHA256Hex
const FORGED = 'f'.repeat(64) as SHA256Hex
const MALFORMED = 'not-a-sha256' as SHA256Hex
const UPPERCASE = 'A'.repeat(64) as SHA256Hex
const SEQ1 = 1n as SequenceNumber
const NEGATIVE_SEQ = -1n as SequenceNumber

async function makeCalibration(): Promise<SelfCalibrationRecordV1> {
  const prediction = await createSelfPrediction({
    action_digest: ACTION,
    predicted_success_bps: 7500,
  })
  const observation = createSelfOutcomeObservation({
    prediction_hash: prediction.prediction_hash,
    action_digest: ACTION,
    observation_evidence_digest: EVIDENCE,
    observed_success: true,
  })
  return createSelfCalibration(prediction, observation)
}

async function rehashCalibration(
  calibration: SelfCalibrationRecordV1,
  overrides: Partial<SelfCalibrationRecordV1>,
): Promise<SelfCalibrationRecordV1> {
  const candidate = { ...calibration, ...overrides }
  const calibration_hash = await hashValue({
    receipt_kind: candidate.receipt_kind,
    schema_version: candidate.schema_version,
    prediction_hash: candidate.prediction_hash,
    action_digest: candidate.action_digest,
    observation_evidence_digest: candidate.observation_evidence_digest,
    predicted_success_bps: candidate.predicted_success_bps,
    observed_success: candidate.observed_success,
    absolute_error_bps: candidate.absolute_error_bps,
    authority: candidate.authority,
    acceptable_for_effect_truth: candidate.acceptable_for_effect_truth,
  })
  return { ...candidate, calibration_hash }
}

describe('self-calibration adversarial integrity', () => {
  it('rejects a rehashed calibration whose prediction_hash is detached from its prediction body', async () => {
    const valid = await makeCalibration()
    const forged = await rehashCalibration(valid, { prediction_hash: FORGED })

    await expect(
      SelfCalibrationLedger.empty().append(forged, SEQ1),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('rejects a rehashed calibration that recycles prediction_hash as observation evidence', async () => {
    const valid = await makeCalibration()
    const forged = await rehashCalibration(valid, {
      observation_evidence_digest: valid.prediction_hash,
    })

    await expect(
      SelfCalibrationLedger.empty().append(forged, SEQ1),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('rejects forged calibration before it can enter SELF_MODEL observation', async () => {
    const valid = await makeCalibration()
    const forged = await rehashCalibration(valid, { prediction_hash: FORGED })

    await expect(
      calibrationToMetacognitiveObservation(forged),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('rejects malformed or non-lowercase SHA-256 digests at public construction boundaries', async () => {
    await expect(
      createSelfPrediction({
        action_digest: MALFORMED,
        predicted_success_bps: 7500,
      }),
    ).rejects.toThrow(SelfCalibrationError)

    const prediction = await createSelfPrediction({
      action_digest: ACTION,
      predicted_success_bps: 7500,
    })

    expect(() =>
      createSelfOutcomeObservation({
        prediction_hash: prediction.prediction_hash,
        action_digest: ACTION,
        observation_evidence_digest: UPPERCASE,
        observed_success: true,
      }),
    ).toThrow(SelfCalibrationError)

    expect(() =>
      createSelfOutcomeObservation({
        prediction_hash: MALFORMED,
        action_digest: ACTION,
        observation_evidence_digest: EVIDENCE,
        observed_success: true,
      }),
    ).toThrow(SelfCalibrationError)
  })

  it('rejects a negative genesis sequence on append', async () => {
    const calibration = await makeCalibration()

    await expect(
      SelfCalibrationLedger.empty().append(calibration, NEGATIVE_SEQ),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('rejects a cryptographically self-consistent replay whose first sequence is negative', async () => {
    const calibration = await makeCalibration()
    const entry_hash = await hashValue({
      calibration,
      previous_entry_hash: SELF_CALIBRATION_GENESIS_HASH,
      sequence: NEGATIVE_SEQ.toString(),
    })
    const forgedEntry: SelfCalibrationLedgerEntry = {
      calibration,
      previous_entry_hash: SELF_CALIBRATION_GENESIS_HASH,
      sequence: NEGATIVE_SEQ,
      entry_hash,
      schema_version: '1.0.0',
      is_replay_reconstructable: true,
    }

    const certificate = await certifySelfCalibrationLedger([forgedEntry])
    expect(certificate.is_valid).toBe(false)
  })
})
