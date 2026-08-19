import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  SelfCalibrationError,
  createSelfOutcomeObservation,
  createSelfPrediction,
} from '../../src/metacognition/self-calibration.js'

const H1 = '1'.repeat(64) as SHA256Hex


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
