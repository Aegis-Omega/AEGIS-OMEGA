// ============================================================
// SOVEREIGN OMEGA — REFLEXIVE_SELF_MODEL_V1 Cycle Closure
// EPISTEMIC TIER: T2 · evidence only
//
// Closes prediction -> execution -> observation -> calibration cycles.
// Reflexive evidence never grants execution, policy, capability, tier,
// effect-truth, or admission authority.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import {
  CALIBRATION_EVIDENCE_ONLY,
  REFLEXIVE_SELF_MODEL_SCHEMA_VERSION,
  UPDATE_PROPOSAL_ONLY,
  type PredictionErrorReceiptV1,
  type ReflexiveCycleReceiptV1,
  type SelfModelSnapshotV1,
  type SelfModelUpdateAction,
  type SelfModelUpdateProposalV1,
  type SelfObservationV1,
  type SelfPredictionV1,
  validateSelfModelSnapshotV1,
  validateSelfModelUpdateProposalV1,
  validateSelfObservationV1,
  validateSelfPredictionV1,
} from './contracts.js'
import { evaluatePredictionAgainstObservation } from './evaluate.js'

const SHA256_RE = /^[0-9a-f]{64}$/

export type ReflexiveCycleStatus =
  | 'CYCLE_CLOSED'
  | 'UNSCORABLE_POSTDICTION'
  | 'UNSCORABLE_STALE_BINDING'
  | 'UNSCORABLE_UNVERIFIED_OUTCOME'
  | 'CONTRADICTION_DETECTED'
  | 'TAMPER_DETECTED'

export interface ReflexiveExecutionReferenceV1 {
  readonly execution_id: string
  readonly execution_started_at: number
  readonly execution_receipt_digest: string
}

export interface CloseReflexiveCycleInputV1 {
  readonly snapshot: SelfModelSnapshotV1
  readonly prediction: SelfPredictionV1
  readonly execution_reference: ReflexiveExecutionReferenceV1
  readonly observation: SelfObservationV1
  readonly additional_verified_observations?: readonly SelfObservationV1[]
}

export class ReflexiveCycleError extends Error {
  override readonly name = 'ReflexiveCycleError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function assertExecutionReference(value: ReflexiveExecutionReferenceV1): void {
  if (
    typeof value !== 'object' || value === null ||
    Object.keys(value).sort().join(',') !==
      ['execution_id', 'execution_receipt_digest', 'execution_started_at'].sort().join(',')
  ) {
    throw new ReflexiveCycleError('execution_reference must be a closed V1 object')
  }
  if (typeof value.execution_id !== 'string' || value.execution_id.length === 0) {
    throw new ReflexiveCycleError('execution_reference.execution_id must be non-empty')
  }
  if (!Number.isSafeInteger(value.execution_started_at) || value.execution_started_at < 0) {
    throw new ReflexiveCycleError(
      'execution_reference.execution_started_at must be a non-negative safe integer',
    )
  }
  if (!SHA256_RE.test(value.execution_receipt_digest)) {
    throw new ReflexiveCycleError(
      'execution_reference.execution_receipt_digest must be lowercase sha256 hex',
    )
  }
}

function withoutField<T extends Record<string, unknown>>(
  value: T,
  field: keyof T,
): Record<string, unknown> {
  const body = { ...value }
  delete body[field]
  return body
}

async function snapshotDigestMatches(snapshot: SelfModelSnapshotV1): Promise<boolean> {
  return hashValue(withoutField(snapshot as unknown as Record<string, unknown>, 'snapshot_digest'))
    .then(digest => digest === snapshot.snapshot_digest)
}

async function predictionDigestMatches(prediction: SelfPredictionV1): Promise<boolean> {
  return hashValue(withoutField(prediction as unknown as Record<string, unknown>, 'prediction_digest'))
    .then(digest => digest === prediction.prediction_digest)
}

async function observationDigestMatches(observation: SelfObservationV1): Promise<boolean> {
  return hashValue(withoutField(observation as unknown as Record<string, unknown>, 'observation_digest'))
    .then(digest => digest === observation.observation_digest)
}

function hasExactBinding(
  snapshot: SelfModelSnapshotV1,
  prediction: SelfPredictionV1,
  observation: SelfObservationV1,
): boolean {
  return (
    prediction.self_model_snapshot_digest === snapshot.snapshot_digest &&
    prediction.policy_digest === snapshot.policy_digest &&
    prediction.epoch_id === snapshot.epoch_id &&
    prediction.prestate_root === snapshot.state_root &&
    observation.cycle_id === prediction.cycle_id &&
    observation.target_kind === prediction.target_kind &&
    observation.target_id === prediction.target_id &&
    observation.policy_digest === prediction.policy_digest &&
    observation.epoch_id === prediction.epoch_id &&
    observation.prestate_root === prediction.prestate_root &&
    observation.prediction_digest === prediction.prediction_digest
  )
}

function hasVerifiedOutcomeEvidence(observation: SelfObservationV1): boolean {
  return (
    observation.epistemic_status === 'VERIFIED' &&
    observation.source_modality !== 'PROVIDER_REPORT' &&
    observation.verifier_receipt_digests.length > 0 &&
    observation.evidence_artifact_digests.length > 0
  )
}

async function observationsContradict(
  primary: SelfObservationV1,
  additional: readonly SelfObservationV1[],
): Promise<boolean> {
  const primaryByClause = new Map(primary.clauses.map(clause => [clause.clause_id, clause.value]))

  for (const candidate of additional) {
    if (!hasExactObservationBinding(primary, candidate)) continue
    if (!hasVerifiedOutcomeEvidence(candidate)) continue
    for (const clause of candidate.clauses) {
      if (!primaryByClause.has(clause.clause_id)) continue
      const primaryDigest = await hashValue(primaryByClause.get(clause.clause_id))
      const candidateDigest = await hashValue(clause.value)
      if (primaryDigest !== candidateDigest) return true
    }
  }
  return false
}

function hasExactObservationBinding(
  left: SelfObservationV1,
  right: SelfObservationV1,
): boolean {
  return (
    left.cycle_id === right.cycle_id &&
    left.target_kind === right.target_kind &&
    left.target_id === right.target_id &&
    left.policy_digest === right.policy_digest &&
    left.epoch_id === right.epoch_id &&
    left.prestate_root === right.prestate_root &&
    left.prediction_digest === right.prediction_digest
  )
}

async function buildUnscorableErrorReceipt(
  prediction: SelfPredictionV1,
  observation: SelfObservationV1,
  status: ReflexiveCycleStatus,
): Promise<PredictionErrorReceiptV1> {
  const body = {
    record_kind: 'PREDICTION_ERROR_RECEIPT_V1' as const,
    schema_version: REFLEXIVE_SELF_MODEL_SCHEMA_VERSION,
    cycle_id: prediction.cycle_id,
    prediction_digest: prediction.prediction_digest,
    observation_digest: observation.observation_digest,
    target_kind: prediction.target_kind,
    target_id: prediction.target_id,
    policy_digest: prediction.policy_digest,
    epoch_id: prediction.epoch_id,
    prestate_root: prediction.prestate_root,
    per_clause: [],
    weighted_error_bps: null,
    confidence_residual_bps: null,
    scoring_status: 'UNSCORABLE' as const,
    diagnostics: [status],
    authority: CALIBRATION_EVIDENCE_ONLY,
  }
  const receipt_digest = await hashValue(body)
  return deepFreeze({ ...body, receipt_digest })
}

function proposalActionFor(
  status: ReflexiveCycleStatus,
  errorReceipt: PredictionErrorReceiptV1,
): SelfModelUpdateAction {
  if (status === 'CONTRADICTION_DETECTED') return 'MARK_CONTRADICTION'
  if (status !== 'CYCLE_CLOSED') return 'REQUEST_REVIEW'
  if ((errorReceipt.weighted_error_bps ?? 0) > 0) return 'DEMOTE_CONFIDENCE'
  return 'HOLD'
}

async function buildUpdateProposal(
  prediction: SelfPredictionV1,
  observation: SelfObservationV1,
  status: ReflexiveCycleStatus,
  errorReceipt: PredictionErrorReceiptV1,
): Promise<SelfModelUpdateProposalV1> {
  const body = {
    record_kind: 'SELF_MODEL_UPDATE_PROPOSAL_V1' as const,
    schema_version: REFLEXIVE_SELF_MODEL_SCHEMA_VERSION,
    proposal_id: `reflexive:${prediction.cycle_id}:${status}`,
    cycle_id: prediction.cycle_id,
    action: proposalActionFor(status, errorReceipt),
    supporting_receipt_digests: [errorReceipt.receipt_digest],
    created_at: observation.observed_at,
    authority: UPDATE_PROPOSAL_ONLY,
  }
  const proposal_digest = await hashValue(body)
  const proposal = deepFreeze({ ...body, proposal_digest })
  validateSelfModelUpdateProposalV1(proposal)
  return proposal
}

async function buildCycleReceipt(
  snapshot: SelfModelSnapshotV1,
  prediction: SelfPredictionV1,
  observation: SelfObservationV1,
  status: ReflexiveCycleStatus,
  errorReceipt: PredictionErrorReceiptV1,
  proposal: SelfModelUpdateProposalV1,
): Promise<ReflexiveCycleReceiptV1> {
  const replayable = status !== 'TAMPER_DETECTED'
  const scorable = status === 'CYCLE_CLOSED' && errorReceipt.scoring_status === 'SCORED'
  const contradiction_free = status !== 'CONTRADICTION_DETECTED'
  const body = {
    record_kind: 'REFLEXIVE_CYCLE_RECEIPT_V1' as const,
    schema_version: REFLEXIVE_SELF_MODEL_SCHEMA_VERSION,
    cycle_id: prediction.cycle_id,
    snapshot_digest: snapshot.snapshot_digest,
    prediction_digest: prediction.prediction_digest,
    observation_digest: observation.observation_digest,
    prediction_error_receipt_digest: errorReceipt.receipt_digest,
    update_proposal_digest: proposal.proposal_digest,
    replayable,
    scorable,
    contradiction_free,
    cycle_status: status,
    authority: 'REFLEXIVE_EVIDENCE_ONLY' as const,
  }
  const cycle_digest = await hashValue(body)
  return deepFreeze({ ...body, cycle_digest })
}

export async function closeReflexiveCycle(
  input: CloseReflexiveCycleInputV1,
): Promise<ReflexiveCycleReceiptV1> {
  const snapshot = validateSelfModelSnapshotV1(input.snapshot)
  const prediction = validateSelfPredictionV1(input.prediction)
  const observation = validateSelfObservationV1(input.observation)
  assertExecutionReference(input.execution_reference)

  const additional = input.additional_verified_observations ?? []
  const validatedAdditional = additional.map(validateSelfObservationV1)

  const baseDigestsValid =
    await snapshotDigestMatches(snapshot) &&
    await predictionDigestMatches(prediction) &&
    await observationDigestMatches(observation)
  let additionalDigestsValid = true
  for (const candidate of validatedAdditional) {
    if (!await observationDigestMatches(candidate)) {
      additionalDigestsValid = false
      break
    }
  }

  let status: ReflexiveCycleStatus
  if (!baseDigestsValid || !additionalDigestsValid) {
    status = 'TAMPER_DETECTED'
  } else if (!hasExactBinding(snapshot, prediction, observation)) {
    status = 'UNSCORABLE_STALE_BINDING'
  } else if (prediction.sealed_at >= input.execution_reference.execution_started_at) {
    status = 'UNSCORABLE_POSTDICTION'
  } else if (!hasVerifiedOutcomeEvidence(observation)) {
    status = 'UNSCORABLE_UNVERIFIED_OUTCOME'
  } else if (await observationsContradict(observation, validatedAdditional)) {
    status = 'CONTRADICTION_DETECTED'
  } else {
    status = 'CYCLE_CLOSED'
  }

  const errorReceipt = status === 'CYCLE_CLOSED'
    ? await evaluatePredictionAgainstObservation(prediction, observation)
    : await buildUnscorableErrorReceipt(prediction, observation, status)

  const proposal = await buildUpdateProposal(
    prediction,
    observation,
    status,
    errorReceipt,
  )

  return buildCycleReceipt(
    snapshot,
    prediction,
    observation,
    status,
    errorReceipt,
    proposal,
  )
}
