// ============================================================
// SOVEREIGN OMEGA — REFLEXIVE_SELF_MODEL_V1 Deterministic Evaluator
// EPISTEMIC TIER: T2 · calibration evidence only
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import {
  CALIBRATION_EVIDENCE_ONLY,
  REFLEXIVE_SELF_MODEL_SCHEMA_VERSION,
  validateSelfObservationV1,
  validateSelfPredictionV1,
  type ObservedClauseV1,
  type PredictionClauseScoreV1,
  type PredictionClauseV1,
  type PredictionErrorReceiptV1,
  type SelfObservationV1,
  type SelfPredictionV1,
} from './contracts.js'

const SHA256_RE = /^[0-9a-f]{64}$/

interface ScoreResult {
  readonly correct: boolean
  readonly error_bps: number
}

function sameBindings(
  prediction: SelfPredictionV1,
  observation: SelfObservationV1,
): readonly string[] {
  const diagnostics: string[] = []
  if (observation.cycle_id !== prediction.cycle_id) diagnostics.push('BINDING_MISMATCH:cycle_id')
  if (observation.target_kind !== prediction.target_kind) diagnostics.push('BINDING_MISMATCH:target_kind')
  if (observation.target_id !== prediction.target_id) diagnostics.push('BINDING_MISMATCH:target_id')
  if (observation.policy_digest !== prediction.policy_digest) diagnostics.push('BINDING_MISMATCH:policy_digest')
  if (observation.epoch_id !== prediction.epoch_id) diagnostics.push('BINDING_MISMATCH:epoch_id')
  if (observation.prestate_root !== prediction.prestate_root) diagnostics.push('BINDING_MISMATCH:prestate_root')
  if (observation.prediction_digest !== prediction.prediction_digest) diagnostics.push('BINDING_MISMATCH:prediction_digest')
  return diagnostics
}

function intervalError(value: number, min: number, max: number): ScoreResult {
  if (value >= min && value <= max) return { correct: true, error_bps: 0 }
  const width = max - min
  if (width <= 0) return { correct: false, error_bps: 10_000 }
  const distance = value < min ? min - value : value - max
  return {
    correct: false,
    error_bps: Math.min(10_000, Math.trunc((distance * 10_000) / width)),
  }
}

function scoreClause(
  prediction: PredictionClauseV1,
  observation: ObservedClauseV1,
): ScoreResult | null {
  const value = observation.value

  switch (prediction.kind) {
    case 'BOOLEAN': {
      if (typeof value !== 'boolean') return null
      const correct = value === prediction.expected
      return { correct, error_bps: correct ? 0 : 10_000 }
    }
    case 'EXACT_STRING': {
      if (typeof value !== 'string') return null
      const correct = value === prediction.expected
      return { correct, error_bps: correct ? 0 : 10_000 }
    }
    case 'SHA256_DIGEST': {
      if (typeof value !== 'string' || !SHA256_RE.test(value)) return null
      const correct = value === prediction.expected
      return { correct, error_bps: correct ? 0 : 10_000 }
    }
    case 'INTEGER_RANGE': {
      if (!Number.isSafeInteger(value)) return null
      return intervalError(value as number, prediction.min, prediction.max)
    }
    case 'BPS_INTERVAL': {
      if (!Number.isSafeInteger(value) || (value as number) < 0 || (value as number) > 10_000) {
        return null
      }
      return intervalError(value as number, prediction.min_bps, prediction.max_bps)
    }
  }
}

function receiptBody(
  prediction: SelfPredictionV1,
  observation: SelfObservationV1,
  scoring_status: PredictionErrorReceiptV1['scoring_status'],
  per_clause: PredictionClauseScoreV1[],
  weighted_error_bps: number | null,
  confidence_residual_bps: number | null,
  diagnostics: string[],
): Omit<PredictionErrorReceiptV1, 'receipt_digest'> {
  return {
    record_kind: 'PREDICTION_ERROR_RECEIPT_V1',
    schema_version: REFLEXIVE_SELF_MODEL_SCHEMA_VERSION,
    cycle_id: prediction.cycle_id,
    prediction_digest: prediction.prediction_digest,
    observation_digest: observation.observation_digest,
    target_kind: prediction.target_kind,
    target_id: prediction.target_id,
    policy_digest: prediction.policy_digest,
    epoch_id: prediction.epoch_id,
    prestate_root: prediction.prestate_root,
    per_clause,
    weighted_error_bps,
    confidence_residual_bps,
    scoring_status,
    diagnostics,
    authority: CALIBRATION_EVIDENCE_ONLY,
  }
}

async function finalizeReceipt(
  body: Omit<PredictionErrorReceiptV1, 'receipt_digest'>,
): Promise<PredictionErrorReceiptV1> {
  const receipt_digest = await hashValue(body)
  return deepFreeze<PredictionErrorReceiptV1>({ ...body, receipt_digest })
}

function clauseIdDiagnostics(
  prediction: SelfPredictionV1,
  observation: SelfObservationV1,
): readonly string[] {
  const predicted = prediction.clauses.map(clause => clause.clause_id)
  const observed = observation.clauses.map(clause => clause.clause_id)
  if (predicted.length !== observed.length) return ['CLAUSE_ID_MISMATCH']
  for (let index = 0; index < predicted.length; index += 1) {
    if (predicted[index] !== observed[index]) return ['CLAUSE_ID_MISMATCH']
  }
  return []
}

/**
 * Compare a sealed prediction with a verified observation using only
 * deterministic integer arithmetic. Contract-invalid inputs throw; valid but
 * non-scorable evidence returns a content-addressed UNSCORABLE receipt.
 */
export async function evaluatePrediction(
  predictionInput: SelfPredictionV1,
  observationInput: SelfObservationV1,
): Promise<PredictionErrorReceiptV1> {
  const prediction = validateSelfPredictionV1(predictionInput)
  const observation = validateSelfObservationV1(observationInput)

  const diagnostics: string[] = []
  diagnostics.push(...sameBindings(prediction, observation))
  if (observation.epistemic_status !== 'VERIFIED') {
    diagnostics.push('UNVERIFIED_OBSERVATION')
  }
  diagnostics.push(...clauseIdDiagnostics(prediction, observation))

  if (diagnostics.length > 0) {
    const body = receiptBody(
      prediction,
      observation,
      'UNSCORABLE',
      [],
      null,
      null,
      [...new Set(diagnostics)].sort(),
    )
    return finalizeReceipt(body)
  }

  const per_clause: PredictionClauseScoreV1[] = []
  let weightedErrorNumerator = 0
  let weightedConfidenceResidualNumerator = 0

  for (let index = 0; index < prediction.clauses.length; index += 1) {
    const predictedClause = prediction.clauses[index]!
    const observedClause = observation.clauses[index]!
    const score = scoreClause(predictedClause, observedClause)
    if (score === null) {
      const body = receiptBody(
        prediction,
        observation,
        'UNSCORABLE',
        [],
        null,
        null,
        [`INVALID_OBSERVED_VALUE:${predictedClause.clause_id}`],
      )
      return finalizeReceipt(body)
    }

    const confidenceTarget = score.correct ? 10_000 : 0
    const confidence_residual_bps = Math.abs(
      predictedClause.confidence_bps - confidenceTarget,
    )
    per_clause.push({
      clause_id: predictedClause.clause_id,
      correct: score.correct,
      error_bps: score.error_bps,
      confidence_residual_bps,
    })
    weightedErrorNumerator += score.error_bps * predictedClause.weight_bps
    weightedConfidenceResidualNumerator +=
      confidence_residual_bps * predictedClause.weight_bps
  }

  const weighted_error_bps = Math.trunc(weightedErrorNumerator / 10_000)
  const confidence_residual_bps = Math.trunc(
    weightedConfidenceResidualNumerator / 10_000,
  )
  const body = receiptBody(
    prediction,
    observation,
    'SCORED',
    per_clause,
    weighted_error_bps,
    confidence_residual_bps,
    [],
  )
  return finalizeReceipt(body)
}
