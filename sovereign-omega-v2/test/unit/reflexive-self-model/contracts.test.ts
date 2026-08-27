import { describe, expect, it } from 'vitest'
import {
  validateSelfModelSnapshotV1,
  validateSelfObservationV1,
  validateSelfPredictionV1,
  validateSelfModelUpdateProposalV1,
} from '../../../src/reflexive-self-model/contracts.js'

const H = 'a'.repeat(64)
const H2 = 'b'.repeat(64)

function validSnapshot(): Record<string, unknown> {
  return {
    record_kind: 'SELF_MODEL_SNAPSHOT_V1',
    schema_version: '1.0.0',
    snapshot_id: 'snap-1',
    created_at: 1,
    source_commit_sha: H,
    policy_digest: H,
    epoch_id: 'epoch-1',
    state_root: H,
    capability_inventory_digest: H,
    claim_state_digest: H,
    calibration_state_digest: H,
    previous_snapshot_digest: null,
    snapshot_digest: H2,
    epistemic_ceiling: 'T2',
    authority: 'SELF_MODEL_EVIDENCE_ONLY',
  }
}

function validPrediction(): Record<string, unknown> {
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
    clauses: [
      {
        clause_id: 'c1',
        kind: 'BOOLEAN',
        expected: true,
        weight_bps: 10000,
        confidence_bps: 9000,
      },
    ],
    sealed_at: 10,
    prediction_digest: H2,
    authority: 'PREDICTION_EVIDENCE_ONLY',
  }
}

function validObservation(): Record<string, unknown> {
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
    clauses: [{ clause_id: 'c1', value: true }],
    evidence_artifact_digests: [H],
    verifier_receipt_digests: [H2],
    observed_at: 20,
    observation_digest: H,
    epistemic_status: 'VERIFIED',
    authority: 'OBSERVATION_EVIDENCE_ONLY',
  }
}

describe('REFLEXIVE_SELF_MODEL_V1 closed contracts', () => {
  it('accepts a valid self-model snapshot', () => {
    expect(validateSelfModelSnapshotV1(validSnapshot()).snapshot_id).toBe('snap-1')
  })

  it('accepts repo-native Git object ids without weakening content-digest validation', () => {
    const gitSha1 = 'c'.repeat(40)
    expect(
      validateSelfModelSnapshotV1({ ...validSnapshot(), source_commit_sha: gitSha1 })
        .source_commit_sha,
    ).toBe(gitSha1)

    expect(() =>
      validateSelfModelSnapshotV1({ ...validSnapshot(), source_commit_sha: 'c'.repeat(39) }),
    ).toThrow(/source_commit_sha|git/i)
    expect(() =>
      validateSelfModelSnapshotV1({ ...validSnapshot(), source_commit_sha: 'g'.repeat(40) }),
    ).toThrow(/source_commit_sha|git/i)
    expect(() =>
      validateSelfModelSnapshotV1({ ...validSnapshot(), policy_digest: 'd'.repeat(40) }),
    ).toThrow(/policy_digest|sha/i)
  })

  it('rejects unknown fields on the self-model snapshot', () => {
    expect(() => validateSelfModelSnapshotV1({ ...validSnapshot(), execute: true })).toThrow(/execute|unknown/i)
  })

  it('accepts a valid prediction', () => {
    expect(validateSelfPredictionV1(validPrediction()).prediction_id).toBe('pred-1')
  })

  it('rejects injected authority escalation in a prediction', () => {
    expect(() => validateSelfPredictionV1({ ...validPrediction(), authority: 'EXECUTION_AUTHORITY' })).toThrow(/authority/i)
  })

  it('rejects prediction weights whose sum is not 10000 bps', () => {
    const raw = validPrediction()
    raw.clauses = [
      { clause_id: 'a', kind: 'BOOLEAN', expected: true, weight_bps: 6000, confidence_bps: 9000 },
      { clause_id: 'b', kind: 'BOOLEAN', expected: false, weight_bps: 3000, confidence_bps: 8000 },
    ]
    expect(() => validateSelfPredictionV1(raw)).toThrow(/10000/)
  })

  it('rejects duplicate prediction clause ids', () => {
    const raw = validPrediction()
    raw.clauses = [
      { clause_id: 'dup', kind: 'BOOLEAN', expected: true, weight_bps: 5000, confidence_bps: 9000 },
      { clause_id: 'dup', kind: 'BOOLEAN', expected: false, weight_bps: 5000, confidence_bps: 8000 },
    ]
    expect(() => validateSelfPredictionV1(raw)).toThrow(/duplicate/i)
  })

  it('rejects confidence outside basis-point bounds', () => {
    const raw = validPrediction()
    raw.clauses = [{ clause_id: 'c1', kind: 'BOOLEAN', expected: true, weight_bps: 10000, confidence_bps: 10001 }]
    expect(() => validateSelfPredictionV1(raw)).toThrow(/confidence/i)
  })

  it('rejects unsupported prediction kinds', () => {
    const raw = validPrediction()
    raw.clauses = [{ clause_id: 'c1', kind: 'FREE_TEXT', expected: 'x', weight_bps: 10000, confidence_bps: 5000 }]
    expect(() => validateSelfPredictionV1(raw)).toThrow(/kind/i)
  })

  it('rejects non-sha256 binding digests', () => {
    expect(() => validateSelfPredictionV1({ ...validPrediction(), policy_digest: 'abc' })).toThrow(/policy_digest|sha/i)
  })

  it('rejects unknown fields inside prediction clauses', () => {
    const raw = validPrediction()
    raw.clauses = [{ clause_id: 'c1', kind: 'BOOLEAN', expected: true, weight_bps: 10000, confidence_bps: 9000, permit: true }]
    expect(() => validateSelfPredictionV1(raw)).toThrow(/permit|unknown/i)
  })

  it('accepts a valid verified observation', () => {
    expect(validateSelfObservationV1(validObservation()).epistemic_status).toBe('VERIFIED')
  })

  it('rejects effect or receipt injection into an observation', () => {
    expect(() => validateSelfObservationV1({ ...validObservation(), effect: true })).toThrow(/effect|unknown/i)
    expect(() => validateSelfObservationV1({ ...validObservation(), receipt_kind: 'EFFECT_RECEIPT_V1' })).toThrow(/receipt_kind|unknown/i)
  })

  it('rejects automatic tier-promotion or policy-mutation proposals', () => {
    const base = {
      record_kind: 'SELF_MODEL_UPDATE_PROPOSAL_V1',
      schema_version: '1.0.0',
      proposal_id: 'proposal-1',
      cycle_id: 'cycle-1',
      action: 'HOLD',
      supporting_receipt_digests: [H],
      created_at: 30,
      proposal_digest: H2,
      authority: 'UPDATE_PROPOSAL_ONLY',
    }
    expect(validateSelfModelUpdateProposalV1(base).action).toBe('HOLD')
    expect(() => validateSelfModelUpdateProposalV1({ ...base, tier_promotion: 'T0' })).toThrow(/tier_promotion|unknown/i)
    expect(() => validateSelfModelUpdateProposalV1({ ...base, policy_mutation: true })).toThrow(/policy_mutation|unknown/i)
    expect(() => validateSelfModelUpdateProposalV1({ ...base, capability_grant: 'all' })).toThrow(/capability_grant|unknown/i)
  })
})
