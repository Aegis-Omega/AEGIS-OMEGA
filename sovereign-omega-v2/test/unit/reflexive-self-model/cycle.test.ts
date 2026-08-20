import { describe, expect, it } from 'vitest'
import { hashValue } from '../../../src/core/hashing.js'
import { closeReflexiveCycle } from '../../../src/reflexive-self-model/cycle.js'
import type {
  SelfModelSnapshotV1,
  SelfObservationV1,
  SelfPredictionV1,
} from '../../../src/reflexive-self-model/contracts.js'

const H = 'a'.repeat(64)
const H2 = 'b'.repeat(64)

async function snapshot(): Promise<SelfModelSnapshotV1> {
  const body = {
    record_kind: 'SELF_MODEL_SNAPSHOT_V1' as const,
    schema_version: '1.0.0' as const,
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
    epistemic_ceiling: 'T2' as const,
    authority: 'SELF_MODEL_EVIDENCE_ONLY' as const,
  }
  return { ...body, snapshot_digest: await hashValue(body) }
}

async function prediction(
  model: SelfModelSnapshotV1,
  expected = true,
): Promise<SelfPredictionV1> {
  const body = {
    record_kind: 'SELF_PREDICTION_V1' as const,
    schema_version: '1.0.0' as const,
    prediction_id: 'pred-1',
    cycle_id: 'cycle-1',
    self_model_snapshot_digest: model.snapshot_digest,
    target_kind: 'WORK_NODE' as const,
    target_id: 'node-1',
    policy_digest: H,
    epoch_id: 'epoch-1',
    prestate_root: H,
    clauses: [
      {
        clause_id: 'c1',
        kind: 'BOOLEAN' as const,
        expected,
        weight_bps: 10000,
        confidence_bps: 9000,
      },
    ],
    sealed_at: 10,
    authority: 'PREDICTION_EVIDENCE_ONLY' as const,
  }
  return { ...body, prediction_digest: await hashValue(body) }
}

async function observation(
  pred: SelfPredictionV1,
  value = true,
  source_modality: SelfObservationV1['source_modality'] = 'TEST_RESULT',
): Promise<SelfObservationV1> {
  const body = {
    record_kind: 'SELF_OBSERVATION_V1' as const,
    schema_version: '1.0.0' as const,
    observation_id: `obs-${source_modality.toLowerCase()}`,
    cycle_id: pred.cycle_id,
    target_kind: pred.target_kind,
    target_id: pred.target_id,
    policy_digest: pred.policy_digest,
    epoch_id: pred.epoch_id,
    prestate_root: pred.prestate_root,
    prediction_digest: pred.prediction_digest,
    source_modality,
    clauses: [{ clause_id: 'c1', value }],
    evidence_artifact_digests: [H2],
    verifier_receipt_digests: source_modality === 'PROVIDER_REPORT' ? [] : [H],
    observed_at: 20,
    epistemic_status: 'VERIFIED' as const,
    authority: 'OBSERVATION_EVIDENCE_ONLY' as const,
  }
  return { ...body, observation_digest: await hashValue(body) }
}

async function validCycle() {
  const model = await snapshot()
  const pred = await prediction(model)
  const obs = await observation(pred)
  return {
    snapshot: model,
    prediction: pred,
    execution_reference: {
      execution_id: 'exec-1',
      execution_started_at: 15,
      execution_receipt_digest: H2,
    },
    observation: obs,
    additional_verified_observations: [] as SelfObservationV1[],
  }
}

describe('REFLEXIVE_SELF_MODEL_V1 cycle closure', () => {
  it('closes an exact-bound verified cycle deterministically', async () => {
    const input = await validCycle()
    const a = await closeReflexiveCycle(input)
    const b = await closeReflexiveCycle(input)

    expect(a.cycle_status).toBe('CYCLE_CLOSED')
    expect(a.scorable).toBe(true)
    expect(a.replayable).toBe(true)
    expect(a.contradiction_free).toBe(true)
    expect(a.authority).toBe('REFLEXIVE_EVIDENCE_ONLY')
    expect(a.cycle_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(a).toEqual(b)
  })

  it('returns UNSCORABLE_POSTDICTION when prediction was sealed after execution started', async () => {
    const input = await validCycle()
    input.prediction = { ...input.prediction, sealed_at: 16 }
    const receipt = await closeReflexiveCycle(input)

    expect(receipt.cycle_status).toBe('UNSCORABLE_POSTDICTION')
    expect(receipt.scorable).toBe(false)
  })

  it('returns UNSCORABLE_STALE_BINDING for a cross-cycle observation', async () => {
    const input = await validCycle()
    input.observation = { ...input.observation, cycle_id: 'other-cycle' }
    const receipt = await closeReflexiveCycle(input)

    expect(receipt.cycle_status).toBe('UNSCORABLE_STALE_BINDING')
    expect(receipt.scorable).toBe(false)
  })

  it('does not accept a provider report as verified outcome evidence', async () => {
    const input = await validCycle()
    input.observation = await observation(input.prediction, true, 'PROVIDER_REPORT')
    const receipt = await closeReflexiveCycle(input)

    expect(receipt.cycle_status).toBe('UNSCORABLE_UNVERIFIED_OUTCOME')
    expect(receipt.scorable).toBe(false)
  })

  it('returns TAMPER_DETECTED when a content-addressed observation body is edited', async () => {
    const input = await validCycle()
    input.observation = {
      ...input.observation,
      clauses: [{ clause_id: 'c1', value: false }],
    }
    const receipt = await closeReflexiveCycle(input)

    expect(receipt.cycle_status).toBe('TAMPER_DETECTED')
    expect(receipt.scorable).toBe(false)
  })

  it('preserves contradictory verified observations instead of silently choosing one', async () => {
    const input = await validCycle()
    const conflicting = await observation(input.prediction, false)
    input.additional_verified_observations = [conflicting]
    const receipt = await closeReflexiveCycle(input)

    expect(receipt.cycle_status).toBe('CONTRADICTION_DETECTED')
    expect(receipt.contradiction_free).toBe(false)
    expect(receipt.scorable).toBe(false)
  })
})
