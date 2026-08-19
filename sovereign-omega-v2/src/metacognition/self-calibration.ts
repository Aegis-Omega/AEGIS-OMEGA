// ============================================================
// SOVEREIGN OMEGA — Evidence-Bound Self-Model Calibration
// EPISTEMIC TIER: T2 · evidence only
//
// Prediction, observation, and calibration artifacts from this
// module never grant authority and are never effect-truth evidence.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const SELF_CALIBRATION_SCHEMA_VERSION = '1.0.0' as const

export interface SelfPredictionInput {
  readonly action_digest: SHA256Hex
  readonly predicted_success_bps: number
}

export interface SelfPredictionRecordV1 {
  readonly receipt_kind: 'SELF_PREDICTION_RECORD_V1'
  readonly schema_version: typeof SELF_CALIBRATION_SCHEMA_VERSION
  readonly action_digest: SHA256Hex
  readonly predicted_success_bps: number
  readonly prediction_hash: SHA256Hex
  readonly authority: 'NONE'
  readonly acceptable_for_effect_truth: false
}

export interface SelfOutcomeObservationInput {
  readonly prediction_hash: SHA256Hex
  readonly action_digest: SHA256Hex
  readonly observation_evidence_digest: SHA256Hex
  readonly observed_success: boolean
}

export interface SelfOutcomeObservationV1 {
  readonly receipt_kind: 'SELF_OUTCOME_OBSERVATION_V1'
  readonly schema_version: typeof SELF_CALIBRATION_SCHEMA_VERSION
  readonly prediction_hash: SHA256Hex
  readonly action_digest: SHA256Hex
  readonly observation_evidence_digest: SHA256Hex
  readonly observed_success: boolean
  readonly authority: 'NONE'
  readonly acceptable_for_effect_truth: false
}

export interface SelfCalibrationRecordV1 {
  readonly receipt_kind: 'SELF_CALIBRATION_RECORD_V1'
  readonly schema_version: typeof SELF_CALIBRATION_SCHEMA_VERSION
  readonly prediction_hash: SHA256Hex
  readonly action_digest: SHA256Hex
  readonly observation_evidence_digest: SHA256Hex
  readonly predicted_success_bps: number
  readonly observed_success: boolean
  readonly absolute_error_bps: number
  readonly calibration_hash: SHA256Hex
  readonly authority: 'NONE'
  readonly acceptable_for_effect_truth: false
}

export class SelfCalibrationError extends Error {
  override readonly name = 'SelfCalibrationError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function assertBasisPoints(value: number): void {
  if (!Number.isInteger(value) || value < 0 || value > 10_000) {
    throw new SelfCalibrationError(
      `predicted_success_bps must be an integer in [0, 10000], got ${value}`,
    )
  }
}

function predictionBody(input: SelfPredictionInput) {
  return {
    receipt_kind: 'SELF_PREDICTION_RECORD_V1' as const,
    schema_version: SELF_CALIBRATION_SCHEMA_VERSION,
    action_digest: input.action_digest,
    predicted_success_bps: input.predicted_success_bps,
    authority: 'NONE' as const,
    acceptable_for_effect_truth: false as const,
  }
}

export async function createSelfPrediction(
  input: SelfPredictionInput,
): Promise<SelfPredictionRecordV1> {
  assertBasisPoints(input.predicted_success_bps)
  const body = predictionBody(input)
  const prediction_hash = await hashValue(body)

  return deepFreeze<SelfPredictionRecordV1>({
    ...body,
    prediction_hash,
  })
}

export function createSelfOutcomeObservation(
  input: SelfOutcomeObservationInput,
): SelfOutcomeObservationV1 {
  if (input.observation_evidence_digest === input.prediction_hash) {
    throw new SelfCalibrationError(
      'prediction_hash cannot serve as its own observation evidence',
    )
  }

  return deepFreeze<SelfOutcomeObservationV1>({
    receipt_kind: 'SELF_OUTCOME_OBSERVATION_V1',
    schema_version: SELF_CALIBRATION_SCHEMA_VERSION,
    prediction_hash: input.prediction_hash,
    action_digest: input.action_digest,
    observation_evidence_digest: input.observation_evidence_digest,
    observed_success: input.observed_success,
    authority: 'NONE',
    acceptable_for_effect_truth: false,
  })
}

async function assertPredictionIntegrity(
  prediction: SelfPredictionRecordV1,
): Promise<void> {
  assertBasisPoints(prediction.predicted_success_bps)
  if (
    prediction.receipt_kind !== 'SELF_PREDICTION_RECORD_V1' ||
    prediction.schema_version !== SELF_CALIBRATION_SCHEMA_VERSION ||
    prediction.authority !== 'NONE' ||
    prediction.acceptable_for_effect_truth !== false
  ) {
    throw new SelfCalibrationError('prediction record semantics are invalid')
  }

  const expected = await hashValue(predictionBody(prediction))
  if (expected !== prediction.prediction_hash) {
    throw new SelfCalibrationError('prediction body does not match prediction_hash')
  }
}

function assertObservationSemantics(observation: SelfOutcomeObservationV1): void {
  if (
    observation.receipt_kind !== 'SELF_OUTCOME_OBSERVATION_V1' ||
    observation.schema_version !== SELF_CALIBRATION_SCHEMA_VERSION ||
    observation.authority !== 'NONE' ||
    observation.acceptable_for_effect_truth !== false
  ) {
    throw new SelfCalibrationError('outcome observation semantics are invalid')
  }
  if (observation.observation_evidence_digest === observation.prediction_hash) {
    throw new SelfCalibrationError(
      'prediction_hash cannot serve as its own observation evidence',
    )
  }
}

export async function createSelfCalibration(
  prediction: SelfPredictionRecordV1,
  observation: SelfOutcomeObservationV1,
): Promise<SelfCalibrationRecordV1> {
  await assertPredictionIntegrity(prediction)
  assertObservationSemantics(observation)

  if (observation.prediction_hash !== prediction.prediction_hash) {
    throw new SelfCalibrationError('observation prediction_hash does not match prediction')
  }
  if (observation.action_digest !== prediction.action_digest) {
    throw new SelfCalibrationError('observation action_digest does not match prediction')
  }

  const observed_target_bps = observation.observed_success ? 10_000 : 0
  const absolute_error_bps = Math.abs(
    prediction.predicted_success_bps - observed_target_bps,
  )

  const body = {
    receipt_kind: 'SELF_CALIBRATION_RECORD_V1' as const,
    schema_version: SELF_CALIBRATION_SCHEMA_VERSION,
    prediction_hash: prediction.prediction_hash,
    action_digest: prediction.action_digest,
    observation_evidence_digest: observation.observation_evidence_digest,
    predicted_success_bps: prediction.predicted_success_bps,
    observed_success: observation.observed_success,
    absolute_error_bps,
    authority: 'NONE' as const,
    acceptable_for_effect_truth: false as const,
  }
  const calibration_hash = await hashValue(body)

  return deepFreeze<SelfCalibrationRecordV1>({
    ...body,
    calibration_hash,
  })
}
