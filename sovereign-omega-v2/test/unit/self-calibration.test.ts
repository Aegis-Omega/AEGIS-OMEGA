import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  SelfCalibrationError,
  createSelfCalibration,
  createSelfOutcomeObservation,
  createSelfPrediction,
} from '../../src/metacognition/self-calibration.js'

const H1 = '1'.repeat(64) as SHA256Hex
const H2 = '2'.repeat(64) as SHA256Hex
const H3 = '3'.repeat(64) as SHA256Hex


describe('self-model prediction evidence', () => {
  it('rejects predicted_success_bps outside the closed [0, 10000] interval', async () => {
    await expect(
      createSelfPrediction({ action_digest: H1, predicted_success_bps: -1 }),
    ).rejects.toThrow(SelfCalibrationError)

    await expect(
      createSelfPrediction({ action_digest: H1, predicted_success_bps: 10001 }),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('hashes identical prediction inputs deterministically and remains evidence-only', async () => {
    const p1 = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })
    const p2 = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })

    expect(p1.prediction_hash).toBe(p2.prediction_hash)
    expect(p1.receipt_kind).toBe('SELF_PREDICTION_RECORD_V1')
    expect(p1.schema_version).toBe('1.0.0')
    expect(p1.authority).toBe('NONE')
    expect(p1.acceptable_for_effect_truth).toBe(false)
    expect(Object.isFrozen(p1)).toBe(true)
  })

  it('rejects a prediction recycled as its own observation evidence', async () => {
    const prediction = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })

    expect(() =>
      createSelfOutcomeObservation({
        prediction_hash: prediction.prediction_hash,
        action_digest: H1,
        observation_evidence_digest: prediction.prediction_hash,
        observed_success: true,
      }),
    ).toThrow(SelfCalibrationError)
  })
})


describe('self-model calibration binding', () => {
  it('rejects prediction-hash and action-digest splicing', async () => {
    const predictionA = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })
    const predictionB = await createSelfPrediction({
      action_digest: H2,
      predicted_success_bps: 7500,
    })

    const observationA = createSelfOutcomeObservation({
      prediction_hash: predictionA.prediction_hash,
      action_digest: H1,
      observation_evidence_digest: H3,
      observed_success: true,
    })

    await expect(
      createSelfCalibration(predictionA, {
        ...observationA,
        prediction_hash: predictionB.prediction_hash,
      }),
    ).rejects.toThrow(SelfCalibrationError)

    await expect(
      createSelfCalibration(predictionA, {
        ...observationA,
        action_digest: H2,
      }),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('computes deterministic integer calibration error and stays evidence-only', async () => {
    const prediction = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })
    const successObservation = createSelfOutcomeObservation({
      prediction_hash: prediction.prediction_hash,
      action_digest: H1,
      observation_evidence_digest: H2,
      observed_success: true,
    })
    const failureObservation = createSelfOutcomeObservation({
      prediction_hash: prediction.prediction_hash,
      action_digest: H1,
      observation_evidence_digest: H3,
      observed_success: false,
    })

    const success1 = await createSelfCalibration(prediction, successObservation)
    const success2 = await createSelfCalibration(prediction, successObservation)
    const failure = await createSelfCalibration(prediction, failureObservation)

    expect(success1.absolute_error_bps).toBe(2500)
    expect(failure.absolute_error_bps).toBe(7500)
    expect(success1.calibration_hash).toBe(success2.calibration_hash)
    expect(success1.receipt_kind).toBe('SELF_CALIBRATION_RECORD_V1')
    expect(success1.authority).toBe('NONE')
    expect(success1.acceptable_for_effect_truth).toBe(false)
    expect(Object.isFrozen(success1)).toBe(true)
  })

  it('rejects a prediction whose body no longer matches its prediction_hash', async () => {
    const prediction = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })
    const observation = createSelfOutcomeObservation({
      prediction_hash: prediction.prediction_hash,
      action_digest: H1,
      observation_evidence_digest: H2,
      observed_success: true,
    })
    const tamperedPrediction = {
      ...prediction,
      predicted_success_bps: 7600,
    }

    await expect(
      createSelfCalibration(tamperedPrediction, observation),
    ).rejects.toThrow(SelfCalibrationError)
  })
})
