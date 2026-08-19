import { describe, expect, it } from 'vitest'
import { evaluatePrediction } from '../../../src/reflexive-self-model/evaluate.js'
import type { SelfObservationV1, SelfPredictionV1 } from '../../../src/reflexive-self-model/contracts.js'

const H = 'a'.repeat(64)
const H2 = 'b'.repeat(64)

function prediction(clause: SelfPredictionV1['clauses'][number]): SelfPredictionV1 {
  return {
    record_kind: 'SELF_PREDICTION_V1',
    schema_version: '1.0.0',
    prediction_id: 'pred-1',
    cycle_id: 'cycle-1',
    self_model_snapshot_digest: H,
    target_kind: 'WORK_NODE',
    target_id: 'node-1',
    policy_digest: H,
    epoch_id: 'epoch-1',
    prestate_root: H,
    clauses: [clause],
    sealed_at: 10,
    prediction_digest: H2,
    authority: 'PREDICTION_EVIDENCE_ONLY',
  }
}

function observation(value: unknown, status: SelfObservationV1['epistemic_status'] = 'VERIFIED'): SelfObservationV1 {
  return {
    record_kind: 'SELF_OBSERVATION_V1',
    schema_version: '1.0.0',
    observation_id: 'obs-1',
    cycle_id: 'cycle-1',
    target_kind: 'WORK_NODE',
    target_id: 'node-1',
    policy_digest: H,
    epoch_id: 'epoch-1',
    prestate_root: H,
    prediction_digest: H2,
    source_modality: 'TEST_RESULT',
    clauses: [{ clause_id: 'c1', value }],
    evidence_artifact_digests: [H],
    verifier_receipt_digests: [H2],
    observed_at: 20,
    observation_digest: H,
    epistemic_status: status,
    authority: 'OBSERVATION_EVIDENCE_ONLY',
  }
}

describe('REFLEXIVE_SELF_MODEL_V1 deterministic evaluator', () => {
  it('scores exact boolean match as zero error', async () => {
    const receipt = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'BOOLEAN', expected: true, weight_bps: 10000, confidence_bps: 9000 }),
      observation(true),
    )
    expect(receipt.scoring_status).toBe('SCORED')
    expect(receipt.per_clause[0]!.error_bps).toBe(0)
    expect(receipt.per_clause[0]!.confidence_residual_bps).toBe(1000)
    expect(receipt.weighted_error_bps).toBe(0)
  })

  it('scores exact boolean mismatch as 10000 error', async () => {
    const receipt = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'BOOLEAN', expected: true, weight_bps: 10000, confidence_bps: 9000 }),
      observation(false),
    )
    expect(receipt.per_clause[0]!.error_bps).toBe(10000)
    expect(receipt.per_clause[0]!.confidence_residual_bps).toBe(9000)
    expect(receipt.weighted_error_bps).toBe(10000)
  })

  it('scores exact strings and sha256 digests by exact equality', async () => {
    const stringReceipt = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'EXACT_STRING', expected: 'green', weight_bps: 10000, confidence_bps: 8000 }),
      observation('green'),
    )
    expect(stringReceipt.weighted_error_bps).toBe(0)

    const digestReceipt = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'SHA256_DIGEST', expected: H, weight_bps: 10000, confidence_bps: 8000 }),
      observation(H2),
    )
    expect(digestReceipt.weighted_error_bps).toBe(10000)
  })

  it('scores integer ranges deterministically without floating point output', async () => {
    const inside = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'INTEGER_RANGE', min: 10, max: 20, weight_bps: 10000, confidence_bps: 7000 }),
      observation(15),
    )
    expect(inside.weighted_error_bps).toBe(0)

    const outside = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'INTEGER_RANGE', min: 10, max: 20, weight_bps: 10000, confidence_bps: 7000 }),
      observation(25),
    )
    expect(outside.weighted_error_bps).toBe(5000)
    expect(Number.isInteger(outside.weighted_error_bps)).toBe(true)
  })

  it('scores bps intervals with integer-only canonical values', async () => {
    const receipt = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'BPS_INTERVAL', min_bps: 4000, max_bps: 6000, weight_bps: 10000, confidence_bps: 6000 }),
      observation(7000),
    )
    expect(receipt.weighted_error_bps).toBe(5000)
    expect(Number.isInteger(receipt.weighted_error_bps)).toBe(true)
  })

  it('returns UNSCORABLE for unverified observations instead of fabricating an error score', async () => {
    const receipt = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'BOOLEAN', expected: true, weight_bps: 10000, confidence_bps: 9000 }),
      observation(true, 'CANDIDATE'),
    )
    expect(receipt.scoring_status).toBe('UNSCORABLE')
    expect(receipt.weighted_error_bps).toBeNull()
  })

  it('returns UNSCORABLE when observed clause ids do not exactly match', async () => {
    const obs = observation(true)
    obs.clauses = [{ clause_id: 'other', value: true }]
    const receipt = await evaluatePrediction(
      prediction({ clause_id: 'c1', kind: 'BOOLEAN', expected: true, weight_bps: 10000, confidence_bps: 9000 }),
      obs,
    )
    expect(receipt.scoring_status).toBe('UNSCORABLE')
  })

  it('produces byte-stable receipt digests for identical inputs', async () => {
    const pred = prediction({ clause_id: 'c1', kind: 'BOOLEAN', expected: true, weight_bps: 10000, confidence_bps: 9000 })
    const obs = observation(true)
    const a = await evaluatePrediction(pred, obs)
    const b = await evaluatePrediction(pred, obs)
    expect(a).toEqual(b)
    expect(a.receipt_digest).toMatch(/^[0-9a-f]{64}$/)
  })
})
