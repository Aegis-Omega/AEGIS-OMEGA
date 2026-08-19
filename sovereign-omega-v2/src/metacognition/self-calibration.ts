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

export async function createSelfPrediction(
  input: SelfPredictionInput,
): Promise<SelfPredictionRecordV1> {
  assertBasisPoints(input.predicted_success_bps)

  const body = {
    receipt_kind: 'SELF_PREDICTION_RECORD_V1' as const,
    schema_version: SELF_CALIBRATION_SCHEMA_VERSION,
    action_digest: input.action_digest,
    predicted_success_bps: input.predicted_success_bps,
    authority: 'NONE' as const,
    acceptable_for_effect_truth: false as const,
  }

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
