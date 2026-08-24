import { readFileSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, test } from 'vitest'
import { hashValue } from '../../src/core/hashing.js'
import type { SequenceNumber } from '../../src/core/types.js'
import { MetacognitiveLoop, certifyMetacognitiveLoop } from '../../src/metacognition/loop.js'
import {
  validateSelfObservationV1,
  validateSelfPredictionV1,
  validateSelfModelUpdateProposalV1,
} from '../../src/reflexive-self-model/contracts.js'
import type {
  ReflexiveCycleReceiptV1,
  SelfModelSnapshotV1,
  SelfObservationV1,
  SelfPredictionV1,
} from '../../src/reflexive-self-model/contracts.js'
import { closeReflexiveCycle } from '../../src/reflexive-self-model/cycle.js'
import { appendReflexiveCycleToMetacognition } from '../../src/reflexive-self-model/metacognition-bridge.js'

const H1 = '1'.repeat(64)
const H2 = '2'.repeat(64)
const H3 = '3'.repeat(64)
const corpusPath = path.resolve(
  process.cwd(),
  '..',
  'test-vectors',
  'reflexive-self-model',
  'reflexive-self-model-v1.json',
)

interface VectorCase {
  readonly id: string
  readonly category: string
  readonly operation: string
  readonly expected: string
}

interface VectorCorpus {
  readonly schema_version: '1.0.0'
  readonly corpus_kind: 'REFLEXIVE_SELF_MODEL_FALSIFICATION_CORPUS_V1'
  readonly vectors: readonly VectorCase[]
}

const corpus = JSON.parse(readFileSync(corpusPath, 'utf8')) as VectorCorpus

const REQUIRED_CATEGORIES = new Set([
  'postdiction',
  'stale_binding',
  'tampered_digest',
  'provider_world_effect_laundering',
  'authority_injection',
  'weight_error',
  'confidence_error',
  'unsupported_kind',
  'float_leakage',
  'replay_divergence',
  'tier_escalation',
  'policy_mutation',
  'capability_escalation',
  'assumption_bearing_formal_laundering',
  'source_only_tla_success_laundering',
  'source_only_c_wasm_success_laundering',
  'contradiction_suppression',
  'provider_agreement_authority',
  'calibration_as_grant',
  'consciousness_label_as_proof',
  'effect_injection',
  'execution_injection',
  'admission_injection',
  'duplicate_clause_id',
])

async function snapshot(): Promise<SelfModelSnapshotV1> {
  const body = {
    record_kind: 'SELF_MODEL_SNAPSHOT_V1' as const,
    schema_version: '1.0.0' as const,
    snapshot_id: 'vector-snapshot',
    created_at: 1,
    source_commit_sha: 'a'.repeat(40),
    policy_digest: H1,
    epoch_id: 'epoch-vector',
    state_root: H2,
    capability_inventory_digest: H1,
    claim_state_digest: H2,
    calibration_state_digest: H3,
    previous_snapshot_digest: null,
    epistemic_ceiling: 'T2' as const,
    authority: 'SELF_MODEL_EVIDENCE_ONLY' as const,
  }
  return { ...body, snapshot_digest: await hashValue(body) }
}

async function prediction(model: SelfModelSnapshotV1): Promise<SelfPredictionV1> {
  const body = {
    record_kind: 'SELF_PREDICTION_V1' as const,
    schema_version: '1.0.0' as const,
    prediction_id: 'vector-prediction',
    cycle_id: 'vector-cycle',
    self_model_snapshot_digest: model.snapshot_digest,
    target_kind: 'WORK_NODE' as const,
    target_id: 'vector-node',
    policy_digest: model.policy_digest,
    epoch_id: model.epoch_id,
    prestate_root: model.state_root,
    clauses: [
      {
        clause_id: 'outcome',
        kind: 'BOOLEAN' as const,
        expected: true,
        weight_bps: 10000,
        confidence_bps: 9000,
      },
    ],
    sealed_at: 10,
    authority: 'PREDICTION_EVIDENCE_ONLY' as const,
  }
  return { ...body, prediction_digest: await hashValue(body) }
}

async function rehashPrediction(
  input: SelfPredictionV1,
  changes: Record<string, unknown>,
): Promise<SelfPredictionV1> {
  const { prediction_digest: _digest, ...body } = input
  const next = { ...body, ...changes }
  return { ...next, prediction_digest: await hashValue(next) } as SelfPredictionV1
}

async function observation(
  pred: SelfPredictionV1,
  value = true,
  modality: SelfObservationV1['source_modality'] = 'TEST_RESULT',
): Promise<SelfObservationV1> {
  const body = {
    record_kind: 'SELF_OBSERVATION_V1' as const,
    schema_version: '1.0.0' as const,
    observation_id: `vector-observation-${modality.toLowerCase()}`,
    cycle_id: pred.cycle_id,
    target_kind: pred.target_kind,
    target_id: pred.target_id,
    policy_digest: pred.policy_digest,
    epoch_id: pred.epoch_id,
    prestate_root: pred.prestate_root,
    prediction_digest: pred.prediction_digest,
    source_modality: modality,
    clauses: [{ clause_id: 'outcome', value }],
    evidence_artifact_digests: [H2],
    verifier_receipt_digests: modality === 'PROVIDER_REPORT' ? [] : [H3],
    observed_at: 20,
    epistemic_status: 'VERIFIED' as const,
    authority: 'OBSERVATION_EVIDENCE_ONLY' as const,
  }
  return { ...body, observation_digest: await hashValue(body) }
}

async function rehashObservation(
  input: SelfObservationV1,
  changes: Record<string, unknown>,
): Promise<SelfObservationV1> {
  const { observation_digest: _digest, ...body } = input
  const next = { ...body, ...changes }
  return { ...next, observation_digest: await hashValue(next) } as SelfObservationV1
}

function proposal() {
  return {
    record_kind: 'SELF_MODEL_UPDATE_PROPOSAL_V1',
    schema_version: '1.0.0',
    proposal_id: 'vector-proposal',
    cycle_id: 'vector-cycle',
    action: 'HOLD',
    supporting_receipt_digests: [H1],
    created_at: 30,
    proposal_digest: H2,
    authority: 'UPDATE_PROPOSAL_ONLY',
  }
}

async function validCycleInput() {
  const model = await snapshot()
  const pred = await prediction(model)
  const obs = await observation(pred)
  return {
    snapshot: model,
    prediction: pred,
    execution_reference: {
      execution_id: 'vector-exec',
      execution_started_at: 15,
      execution_receipt_digest: H3,
    },
    observation: obs,
    additional_verified_observations: [] as SelfObservationV1[],
  }
}

async function closedCycleReceipt(): Promise<ReflexiveCycleReceiptV1> {
  return closeReflexiveCycle(await validCycleInput())
}

function captureThrow(fn: () => unknown): string {
  try {
    fn()
    return 'ACCEPTED'
  } catch (error) {
    return `THREW:${error instanceof Error ? error.name : 'UNKNOWN'}`
  }
}

async function captureAsyncThrow(fn: () => Promise<unknown>): Promise<string> {
  try {
    await fn()
    return 'ACCEPTED'
  } catch (error) {
    return `THREW:${error instanceof Error ? error.name : 'UNKNOWN'}`
  }
}

async function executeVector(vector: VectorCase): Promise<string> {
  switch (vector.operation) {
    case 'CYCLE_POSTDICTION': {
      const input = await validCycleInput()
      input.prediction = await rehashPrediction(input.prediction, { sealed_at: 16 })
      input.observation = await observation(input.prediction)
      return (await closeReflexiveCycle(input)).cycle_status
    }
    case 'CYCLE_STALE_BINDING': {
      const input = await validCycleInput()
      input.observation = await rehashObservation(input.observation, { cycle_id: 'stale-cycle' })
      return (await closeReflexiveCycle(input)).cycle_status
    }
    case 'CYCLE_TAMPER': {
      const input = await validCycleInput()
      input.observation = { ...input.observation, clauses: [{ clause_id: 'outcome', value: false }] }
      return (await closeReflexiveCycle(input)).cycle_status
    }
    case 'CYCLE_PROVIDER_REPORT': {
      const input = await validCycleInput()
      input.observation = await observation(input.prediction, true, 'PROVIDER_REPORT')
      return (await closeReflexiveCycle(input)).cycle_status
    }
    case 'PRED_AUTHORITY_INJECTION': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({ ...pred, authority: 'EXECUTION_AUTHORITY' }))
    }
    case 'PRED_WEIGHT_SUM': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({
        ...pred,
        clauses: [
          { clause_id: 'a', kind: 'BOOLEAN', expected: true, weight_bps: 4000, confidence_bps: 8000 },
          { clause_id: 'b', kind: 'BOOLEAN', expected: false, weight_bps: 4000, confidence_bps: 8000 },
        ],
      }))
    }
    case 'PRED_CONFIDENCE_OOB': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({
        ...pred,
        clauses: [{ clause_id: 'outcome', kind: 'BOOLEAN', expected: true, weight_bps: 10000, confidence_bps: 10001 }],
      }))
    }
    case 'PRED_KIND_UNKNOWN': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({
        ...pred,
        clauses: [{ clause_id: 'outcome', kind: 'FREE_TEXT', expected: 'x', weight_bps: 10000, confidence_bps: 5000 }],
      }))
    }
    case 'PRED_FLOAT_WEIGHT': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({
        ...pred,
        clauses: [{ clause_id: 'outcome', kind: 'BOOLEAN', expected: true, weight_bps: 9999.5, confidence_bps: 9000 }],
      }))
    }
    case 'BRIDGE_REPLAY': {
      const receipt = await closedCycleReceipt()
      const first = await appendReflexiveCycleToMetacognition(MetacognitiveLoop.empty(), receipt, 100n as SequenceNumber)
      const second = await appendReflexiveCycleToMetacognition(MetacognitiveLoop.empty(), receipt, 100n as SequenceNumber)
      const certA = await certifyMetacognitiveLoop(first.loop.getAll())
      const certB = await certifyMetacognitiveLoop(second.loop.getAll())
      return certA.is_valid && certB.is_valid && certA.certificate_hash === certB.certificate_hash
        ? 'REPLAY_STABLE'
        : 'REPLAY_DIVERGED'
    }
    case 'PROPOSAL_TIER_ESCALATION':
      return captureThrow(() => validateSelfModelUpdateProposalV1({ ...proposal(), tier_promotion: 'T0' }))
    case 'PROPOSAL_POLICY_MUTATION':
      return captureThrow(() => validateSelfModelUpdateProposalV1({ ...proposal(), policy_mutation: true }))
    case 'PROPOSAL_CAPABILITY_GRANT':
      return captureThrow(() => validateSelfModelUpdateProposalV1({ ...proposal(), capability_grant: 'all' }))
    case 'OBS_FORMAL_ASSUMPTION_OVERCLAIM': {
      const model = await snapshot()
      const pred = await prediction(model)
      const obs = await observation(pred, true, 'FORMAL_VERIFIER_RECEIPT')
      return captureThrow(() => validateSelfObservationV1({ ...obs, formal_status: 'AXIOM_FREE', assumptions: ['Hash.sha256'] }))
    }
    case 'OBS_TLA_SOURCE_SUCCESS_OVERCLAIM': {
      const model = await snapshot()
      const pred = await prediction(model)
      const obs = await observation(pred, true, 'FORMAL_VERIFIER_RECEIPT')
      return captureThrow(() => validateSelfObservationV1({ ...obs, tla_status: 'EXECUTED_SUCCESS', source_only: true }))
    }
    case 'OBS_C_WASM_SOURCE_SUCCESS_OVERCLAIM': {
      const model = await snapshot()
      const pred = await prediction(model)
      const obs = await observation(pred, true, 'FORMAL_VERIFIER_RECEIPT')
      return captureThrow(() => validateSelfObservationV1({ ...obs, c_wasm_status: 'EXECUTED_SUCCESS', source_only: true }))
    }
    case 'CYCLE_CONTRADICTION_SUPPRESSION': {
      const input = await validCycleInput()
      input.additional_verified_observations = [await observation(input.prediction, false)]
      return (await closeReflexiveCycle(input)).cycle_status
    }
    case 'OBS_PROVIDER_AGREEMENT_AUTHORITY': {
      const model = await snapshot()
      const pred = await prediction(model)
      const obs = await observation(pred, true, 'PROVIDER_REPORT')
      return captureThrow(() => validateSelfObservationV1({ ...obs, provider_agreement_authority: true }))
    }
    case 'PROPOSAL_CALIBRATION_GRANT':
      return captureThrow(() => validateSelfModelUpdateProposalV1({ ...proposal(), calibration_grant: 'D3' }))
    case 'CYCLE_CONSCIOUSNESS_PROOF': {
      const receipt = await closedCycleReceipt()
      return captureAsyncThrow(() => appendReflexiveCycleToMetacognition(
        MetacognitiveLoop.empty(),
        { ...receipt, consciousness_proved: true } as unknown as ReflexiveCycleReceiptV1,
        200n as SequenceNumber,
      ))
    }
    case 'OBS_EFFECT_INJECTION': {
      const model = await snapshot()
      const pred = await prediction(model)
      const obs = await observation(pred)
      return captureThrow(() => validateSelfObservationV1({ ...obs, effect: true }))
    }
    case 'PRED_EXECUTE_INJECTION': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({ ...pred, execute: true }))
    }
    case 'OBS_ADMISSION_INJECTION': {
      const model = await snapshot()
      const pred = await prediction(model)
      const obs = await observation(pred)
      return captureThrow(() => validateSelfObservationV1({ ...obs, admission: 'PERMIT' }))
    }
    case 'PRED_DUPLICATE_CLAUSE': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({
        ...pred,
        clauses: [
          { clause_id: 'dup', kind: 'BOOLEAN', expected: true, weight_bps: 5000, confidence_bps: 9000 },
          { clause_id: 'dup', kind: 'BOOLEAN', expected: false, weight_bps: 5000, confidence_bps: 9000 },
        ],
      }))
    }
    case 'PRED_MALFORMED_DIGEST': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({ ...pred, policy_digest: 'not-a-digest' }))
    }
    case 'PRED_BPS_OOB': {
      const model = await snapshot()
      const pred = await prediction(model)
      return captureThrow(() => validateSelfPredictionV1({
        ...pred,
        clauses: [{ clause_id: 'outcome', kind: 'BPS_INTERVAL', min_bps: 0, max_bps: 10001, weight_bps: 10000, confidence_bps: 9000 }],
      }))
    }
    default:
      return `UNKNOWN_OPERATION:${vector.operation}`
  }
}

describe('REFLEXIVE_SELF_MODEL_V1 canonical falsification corpus', () => {
  test('corpus is versioned, unique, and covers every required adversarial category', () => {
    expect(corpus.schema_version).toBe('1.0.0')
    expect(corpus.corpus_kind).toBe('REFLEXIVE_SELF_MODEL_FALSIFICATION_CORPUS_V1')
    expect(corpus.vectors.length).toBeGreaterThanOrEqual(24)
    expect(new Set(corpus.vectors.map(vector => vector.id)).size).toBe(corpus.vectors.length)
    const categories = new Set(corpus.vectors.map(vector => vector.category))
    for (const required of REQUIRED_CATEGORIES) expect(categories.has(required)).toBe(true)
  })

  test.each(corpus.vectors)('$id falsifies $category deterministically', async vector => {
    const first = await executeVector(vector)
    const second = await executeVector(vector)
    expect(first).toBe(vector.expected)
    expect(second).toBe(vector.expected)
    expect(JSON.stringify(first)).toBe(JSON.stringify(second))
  })
})
