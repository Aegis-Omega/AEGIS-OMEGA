// ============================================================
// SOVEREIGN OMEGA — REFLEXIVE_SELF_MODEL_V1 Closed Contracts
// EPISTEMIC TIER: T2 · evidence only
//
// Reflexive artifacts describe and score the system's own behavior.
// They never grant execution, effect, policy, capability, or admission authority.
// ============================================================

export const REFLEXIVE_SELF_MODEL_SCHEMA_VERSION = '1.0.0' as const
export const SELF_MODEL_EVIDENCE_ONLY = 'SELF_MODEL_EVIDENCE_ONLY' as const
export const PREDICTION_EVIDENCE_ONLY = 'PREDICTION_EVIDENCE_ONLY' as const
export const OBSERVATION_EVIDENCE_ONLY = 'OBSERVATION_EVIDENCE_ONLY' as const
export const CALIBRATION_EVIDENCE_ONLY = 'CALIBRATION_EVIDENCE_ONLY' as const
export const UPDATE_PROPOSAL_ONLY = 'UPDATE_PROPOSAL_ONLY' as const

export const PREDICTION_CLAUSE_KINDS = [
  'BOOLEAN',
  'EXACT_STRING',
  'SHA256_DIGEST',
  'INTEGER_RANGE',
  'BPS_INTERVAL',
] as const

export const OBSERVATION_SOURCE_MODALITIES = [
  'RUNTIME_TELEMETRY',
  'LEDGER_STATE',
  'TEST_RESULT',
  'FORMAL_VERIFIER_RECEIPT',
  'WORLD_OBSERVATION_RECEIPT',
  'PROVIDER_REPORT',
] as const

export const SELF_MODEL_UPDATE_ACTIONS = [
  'HOLD',
  'DEMOTE_CONFIDENCE',
  'RAISE_UNCERTAINTY',
  'MARK_CONTRADICTION',
  'REQUEST_REVIEW',
] as const

export type PredictionClauseKind = typeof PREDICTION_CLAUSE_KINDS[number]
export type ObservationSourceModality = typeof OBSERVATION_SOURCE_MODALITIES[number]
export type SelfModelUpdateAction = typeof SELF_MODEL_UPDATE_ACTIONS[number]
export type ReflexiveTargetKind = 'TRANSITION' | 'WORK_NODE'
export type ObservationEpistemicStatus = 'CANDIDATE' | 'VERIFIED'
export type PredictionScoringStatus = 'SCORED' | 'UNSCORABLE'

interface PredictionClauseBase {
  clause_id: string
  kind: PredictionClauseKind
  weight_bps: number
  confidence_bps: number
}

export interface BooleanPredictionClauseV1 extends PredictionClauseBase {
  kind: 'BOOLEAN'
  expected: boolean
}

export interface ExactStringPredictionClauseV1 extends PredictionClauseBase {
  kind: 'EXACT_STRING'
  expected: string
}

export interface SHA256DigestPredictionClauseV1 extends PredictionClauseBase {
  kind: 'SHA256_DIGEST'
  expected: string
}

export interface IntegerRangePredictionClauseV1 extends PredictionClauseBase {
  kind: 'INTEGER_RANGE'
  min: number
  max: number
}

export interface BpsIntervalPredictionClauseV1 extends PredictionClauseBase {
  kind: 'BPS_INTERVAL'
  min_bps: number
  max_bps: number
}

export type PredictionClauseV1 =
  | BooleanPredictionClauseV1
  | ExactStringPredictionClauseV1
  | SHA256DigestPredictionClauseV1
  | IntegerRangePredictionClauseV1
  | BpsIntervalPredictionClauseV1

export interface ObservedClauseV1 {
  clause_id: string
  value: unknown
}

export interface SelfModelSnapshotV1 {
  record_kind: 'SELF_MODEL_SNAPSHOT_V1'
  schema_version: typeof REFLEXIVE_SELF_MODEL_SCHEMA_VERSION
  snapshot_id: string
  created_at: number
  source_commit_sha: string
  policy_digest: string
  epoch_id: string
  state_root: string
  capability_inventory_digest: string
  claim_state_digest: string
  calibration_state_digest: string
  previous_snapshot_digest: string | null
  snapshot_digest: string
  epistemic_ceiling: 'T2'
  authority: typeof SELF_MODEL_EVIDENCE_ONLY
}

export interface SelfPredictionV1 {
  record_kind: 'SELF_PREDICTION_V1'
  schema_version: typeof REFLEXIVE_SELF_MODEL_SCHEMA_VERSION
  prediction_id: string
  cycle_id: string
  self_model_snapshot_digest: string
  target_kind: ReflexiveTargetKind
  target_id: string
  policy_digest: string
  epoch_id: string
  prestate_root: string
  clauses: PredictionClauseV1[]
  sealed_at: number
  prediction_digest: string
  authority: typeof PREDICTION_EVIDENCE_ONLY
}

export interface SelfObservationV1 {
  record_kind: 'SELF_OBSERVATION_V1'
  schema_version: typeof REFLEXIVE_SELF_MODEL_SCHEMA_VERSION
  observation_id: string
  cycle_id: string
  target_kind: ReflexiveTargetKind
  target_id: string
  policy_digest: string
  epoch_id: string
  prestate_root: string
  prediction_digest: string
  source_modality: ObservationSourceModality
  clauses: ObservedClauseV1[]
  evidence_artifact_digests: string[]
  verifier_receipt_digests: string[]
  observed_at: number
  observation_digest: string
  epistemic_status: ObservationEpistemicStatus
  authority: typeof OBSERVATION_EVIDENCE_ONLY
}

export interface PredictionClauseScoreV1 {
  clause_id: string
  correct: boolean
  error_bps: number
  confidence_residual_bps: number
}

export interface PredictionErrorReceiptV1 {
  record_kind: 'PREDICTION_ERROR_RECEIPT_V1'
  schema_version: typeof REFLEXIVE_SELF_MODEL_SCHEMA_VERSION
  cycle_id: string
  prediction_digest: string
  observation_digest: string
  target_kind: ReflexiveTargetKind
  target_id: string
  policy_digest: string
  epoch_id: string
  prestate_root: string
  per_clause: PredictionClauseScoreV1[]
  weighted_error_bps: number | null
  confidence_residual_bps: number | null
  scoring_status: PredictionScoringStatus
  diagnostics: string[]
  receipt_digest: string
  authority: typeof CALIBRATION_EVIDENCE_ONLY
}

export interface SelfModelUpdateProposalV1 {
  record_kind: 'SELF_MODEL_UPDATE_PROPOSAL_V1'
  schema_version: typeof REFLEXIVE_SELF_MODEL_SCHEMA_VERSION
  proposal_id: string
  cycle_id: string
  action: SelfModelUpdateAction
  supporting_receipt_digests: string[]
  created_at: number
  proposal_digest: string
  authority: typeof UPDATE_PROPOSAL_ONLY
}

export interface ReflexiveCycleReceiptV1 {
  record_kind: 'REFLEXIVE_CYCLE_RECEIPT_V1'
  schema_version: typeof REFLEXIVE_SELF_MODEL_SCHEMA_VERSION
  cycle_id: string
  snapshot_digest: string
  prediction_digest: string
  observation_digest: string
  prediction_error_receipt_digest: string
  update_proposal_digest: string
  replayable: boolean
  scorable: boolean
  contradiction_free: boolean
  cycle_status: string
  cycle_digest: string
  authority: 'REFLEXIVE_EVIDENCE_ONLY'
}

export class ReflexiveContractError extends Error {
  override readonly name = 'ReflexiveContractError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const HASH_RE = /^[0-9a-f]{64}$/
const PREDICTION_KIND_SET = new Set<string>(PREDICTION_CLAUSE_KINDS)
const SOURCE_MODALITY_SET = new Set<string>(OBSERVATION_SOURCE_MODALITIES)
const UPDATE_ACTION_SET = new Set<string>(SELF_MODEL_UPDATE_ACTIONS)
const TARGET_KIND_SET = new Set<string>(['TRANSITION', 'WORK_NODE'])
const EPISTEMIC_STATUS_SET = new Set<string>(['CANDIDATE', 'VERIFIED'])

const SNAPSHOT_KEYS = new Set([
  'record_kind', 'schema_version', 'snapshot_id', 'created_at', 'source_commit_sha',
  'policy_digest', 'epoch_id', 'state_root', 'capability_inventory_digest',
  'claim_state_digest', 'calibration_state_digest', 'previous_snapshot_digest',
  'snapshot_digest', 'epistemic_ceiling', 'authority',
])

const PREDICTION_KEYS = new Set([
  'record_kind', 'schema_version', 'prediction_id', 'cycle_id',
  'self_model_snapshot_digest', 'target_kind', 'target_id', 'policy_digest',
  'epoch_id', 'prestate_root', 'clauses', 'sealed_at', 'prediction_digest', 'authority',
])

const OBSERVATION_KEYS = new Set([
  'record_kind', 'schema_version', 'observation_id', 'cycle_id', 'target_kind',
  'target_id', 'policy_digest', 'epoch_id', 'prestate_root', 'prediction_digest',
  'source_modality', 'clauses', 'evidence_artifact_digests',
  'verifier_receipt_digests', 'observed_at', 'observation_digest',
  'epistemic_status', 'authority',
])

const UPDATE_PROPOSAL_KEYS = new Set([
  'record_kind', 'schema_version', 'proposal_id', 'cycle_id', 'action',
  'supporting_receipt_digests', 'created_at', 'proposal_digest', 'authority',
])

const OBSERVED_CLAUSE_KEYS = new Set(['clause_id', 'value'])
const CLAUSE_BASE_KEYS = ['clause_id', 'kind', 'weight_bps', 'confidence_bps'] as const

function fail(message: string): never {
  throw new ReflexiveContractError(message)
}

function asRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    fail(`${path} must be an object`)
  }
  return value as Record<string, unknown>
}

function assertClosed(
  value: Record<string, unknown>,
  allowed: ReadonlySet<string>,
  path: string,
): void {
  const unknown = Object.keys(value).filter(key => !allowed.has(key)).sort()
  if (unknown.length > 0) fail(`unknown field ${path}.${unknown[0]}`)
}

function assertConst(value: unknown, expected: string, path: string): void {
  if (value !== expected) fail(`${path} must equal ${expected}`)
}

function assertNonEmptyString(value: unknown, path: string): asserts value is string {
  if (typeof value !== 'string' || value.length === 0) fail(`${path} must be non-empty`)
}

function assertHash(value: unknown, path: string): asserts value is string {
  if (typeof value !== 'string' || !HASH_RE.test(value)) {
    fail(`${path} must be lowercase sha256 hex`)
  }
}

function assertSafeNonNegativeInteger(value: unknown, path: string): asserts value is number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) {
    fail(`${path} must be a non-negative safe integer`)
  }
}

function assertBps(value: unknown, path: string): asserts value is number {
  if (!Number.isSafeInteger(value) || (value as number) < 0 || (value as number) > 10_000) {
    fail(`${path} must be an integer in [0,10000]`)
  }
}

function assertTarget(value: Record<string, unknown>, path: string): void {
  if (typeof value.target_kind !== 'string' || !TARGET_KIND_SET.has(value.target_kind)) {
    fail(`${path}.target_kind is invalid`)
  }
  assertNonEmptyString(value.target_id, `${path}.target_id`)
}

function assertHashArray(value: unknown, path: string): asserts value is string[] {
  if (!Array.isArray(value)) fail(`${path} must be an array`)
  for (let index = 0; index < value.length; index += 1) {
    assertHash(value[index], `${path}[${index}]`)
  }
}

function validatePredictionClause(value: unknown, index: number): PredictionClauseV1 {
  const path = `prediction.clauses[${index}]`
  const record = asRecord(value, path)
  assertNonEmptyString(record.clause_id, `${path}.clause_id`)
  if (typeof record.kind !== 'string' || !PREDICTION_KIND_SET.has(record.kind)) {
    fail(`${path}.kind is unsupported`)
  }
  assertBps(record.weight_bps, `${path}.weight_bps`)
  assertBps(record.confidence_bps, `${path}.confidence_bps`)

  if (record.kind === 'BOOLEAN') {
    assertClosed(record, new Set([...CLAUSE_BASE_KEYS, 'expected']), path)
    if (typeof record.expected !== 'boolean') fail(`${path}.expected must be boolean`)
  } else if (record.kind === 'EXACT_STRING') {
    assertClosed(record, new Set([...CLAUSE_BASE_KEYS, 'expected']), path)
    assertNonEmptyString(record.expected, `${path}.expected`)
  } else if (record.kind === 'SHA256_DIGEST') {
    assertClosed(record, new Set([...CLAUSE_BASE_KEYS, 'expected']), path)
    assertHash(record.expected, `${path}.expected`)
  } else if (record.kind === 'INTEGER_RANGE') {
    assertClosed(record, new Set([...CLAUSE_BASE_KEYS, 'min', 'max']), path)
    if (!Number.isSafeInteger(record.min) || !Number.isSafeInteger(record.max)) {
      fail(`${path} integer range endpoints must be safe integers`)
    }
    if ((record.min as number) > (record.max as number)) fail(`${path}.min must be <= max`)
  } else {
    assertClosed(record, new Set([...CLAUSE_BASE_KEYS, 'min_bps', 'max_bps']), path)
    assertBps(record.min_bps, `${path}.min_bps`)
    assertBps(record.max_bps, `${path}.max_bps`)
    if ((record.min_bps as number) > (record.max_bps as number)) {
      fail(`${path}.min_bps must be <= max_bps`)
    }
  }

  return record as unknown as PredictionClauseV1
}

export function validateSelfModelSnapshotV1(value: unknown): SelfModelSnapshotV1 {
  const record = asRecord(value, 'snapshot')
  assertClosed(record, SNAPSHOT_KEYS, 'snapshot')
  assertConst(record.record_kind, 'SELF_MODEL_SNAPSHOT_V1', 'snapshot.record_kind')
  assertConst(record.schema_version, REFLEXIVE_SELF_MODEL_SCHEMA_VERSION, 'snapshot.schema_version')
  assertNonEmptyString(record.snapshot_id, 'snapshot.snapshot_id')
  assertSafeNonNegativeInteger(record.created_at, 'snapshot.created_at')
  assertHash(record.source_commit_sha, 'snapshot.source_commit_sha')
  assertHash(record.policy_digest, 'snapshot.policy_digest')
  assertNonEmptyString(record.epoch_id, 'snapshot.epoch_id')
  assertHash(record.state_root, 'snapshot.state_root')
  assertHash(record.capability_inventory_digest, 'snapshot.capability_inventory_digest')
  assertHash(record.claim_state_digest, 'snapshot.claim_state_digest')
  assertHash(record.calibration_state_digest, 'snapshot.calibration_state_digest')
  if (record.previous_snapshot_digest !== null) {
    assertHash(record.previous_snapshot_digest, 'snapshot.previous_snapshot_digest')
  }
  assertHash(record.snapshot_digest, 'snapshot.snapshot_digest')
  assertConst(record.epistemic_ceiling, 'T2', 'snapshot.epistemic_ceiling')
  assertConst(record.authority, SELF_MODEL_EVIDENCE_ONLY, 'snapshot.authority')
  return record as unknown as SelfModelSnapshotV1
}

export function validateSelfPredictionV1(value: unknown): SelfPredictionV1 {
  const record = asRecord(value, 'prediction')
  assertClosed(record, PREDICTION_KEYS, 'prediction')
  assertConst(record.record_kind, 'SELF_PREDICTION_V1', 'prediction.record_kind')
  assertConst(record.schema_version, REFLEXIVE_SELF_MODEL_SCHEMA_VERSION, 'prediction.schema_version')
  assertNonEmptyString(record.prediction_id, 'prediction.prediction_id')
  assertNonEmptyString(record.cycle_id, 'prediction.cycle_id')
  assertHash(record.self_model_snapshot_digest, 'prediction.self_model_snapshot_digest')
  assertTarget(record, 'prediction')
  assertHash(record.policy_digest, 'prediction.policy_digest')
  assertNonEmptyString(record.epoch_id, 'prediction.epoch_id')
  assertHash(record.prestate_root, 'prediction.prestate_root')
  assertSafeNonNegativeInteger(record.sealed_at, 'prediction.sealed_at')
  assertHash(record.prediction_digest, 'prediction.prediction_digest')
  assertConst(record.authority, PREDICTION_EVIDENCE_ONLY, 'prediction.authority')

  if (!Array.isArray(record.clauses) || record.clauses.length === 0) {
    fail('prediction.clauses must be a non-empty array')
  }
  const clauses = record.clauses.map(validatePredictionClause)
  const ids = new Set<string>()
  let weightSum = 0
  for (const clause of clauses) {
    if (ids.has(clause.clause_id)) fail(`duplicate prediction clause_id: ${clause.clause_id}`)
    ids.add(clause.clause_id)
    weightSum += clause.weight_bps
  }
  if (weightSum !== 10_000) fail(`prediction clause weights must sum to 10000, got ${weightSum}`)

  return record as unknown as SelfPredictionV1
}

export function validateSelfObservationV1(value: unknown): SelfObservationV1 {
  const record = asRecord(value, 'observation')
  assertClosed(record, OBSERVATION_KEYS, 'observation')
  assertConst(record.record_kind, 'SELF_OBSERVATION_V1', 'observation.record_kind')
  assertConst(record.schema_version, REFLEXIVE_SELF_MODEL_SCHEMA_VERSION, 'observation.schema_version')
  assertNonEmptyString(record.observation_id, 'observation.observation_id')
  assertNonEmptyString(record.cycle_id, 'observation.cycle_id')
  assertTarget(record, 'observation')
  assertHash(record.policy_digest, 'observation.policy_digest')
  assertNonEmptyString(record.epoch_id, 'observation.epoch_id')
  assertHash(record.prestate_root, 'observation.prestate_root')
  assertHash(record.prediction_digest, 'observation.prediction_digest')
  if (typeof record.source_modality !== 'string' || !SOURCE_MODALITY_SET.has(record.source_modality)) {
    fail('observation.source_modality is invalid')
  }
  if (!Array.isArray(record.clauses)) fail('observation.clauses must be an array')
  const seen = new Set<string>()
  for (let index = 0; index < record.clauses.length; index += 1) {
    const clause = asRecord(record.clauses[index], `observation.clauses[${index}]`)
    assertClosed(clause, OBSERVED_CLAUSE_KEYS, `observation.clauses[${index}]`)
    assertNonEmptyString(clause.clause_id, `observation.clauses[${index}].clause_id`)
    if (seen.has(clause.clause_id)) fail(`duplicate observation clause_id: ${clause.clause_id}`)
    seen.add(clause.clause_id)
  }
  assertHashArray(record.evidence_artifact_digests, 'observation.evidence_artifact_digests')
  assertHashArray(record.verifier_receipt_digests, 'observation.verifier_receipt_digests')
  assertSafeNonNegativeInteger(record.observed_at, 'observation.observed_at')
  assertHash(record.observation_digest, 'observation.observation_digest')
  if (
    typeof record.epistemic_status !== 'string' ||
    !EPISTEMIC_STATUS_SET.has(record.epistemic_status)
  ) {
    fail('observation.epistemic_status is invalid')
  }
  assertConst(record.authority, OBSERVATION_EVIDENCE_ONLY, 'observation.authority')
  return record as unknown as SelfObservationV1
}

export function validateSelfModelUpdateProposalV1(value: unknown): SelfModelUpdateProposalV1 {
  const record = asRecord(value, 'update_proposal')
  assertClosed(record, UPDATE_PROPOSAL_KEYS, 'update_proposal')
  assertConst(
    record.record_kind,
    'SELF_MODEL_UPDATE_PROPOSAL_V1',
    'update_proposal.record_kind',
  )
  assertConst(
    record.schema_version,
    REFLEXIVE_SELF_MODEL_SCHEMA_VERSION,
    'update_proposal.schema_version',
  )
  assertNonEmptyString(record.proposal_id, 'update_proposal.proposal_id')
  assertNonEmptyString(record.cycle_id, 'update_proposal.cycle_id')
  if (typeof record.action !== 'string' || !UPDATE_ACTION_SET.has(record.action)) {
    fail('update_proposal.action is invalid')
  }
  assertHashArray(record.supporting_receipt_digests, 'update_proposal.supporting_receipt_digests')
  assertSafeNonNegativeInteger(record.created_at, 'update_proposal.created_at')
  assertHash(record.proposal_digest, 'update_proposal.proposal_digest')
  assertConst(record.authority, UPDATE_PROPOSAL_ONLY, 'update_proposal.authority')
  return record as unknown as SelfModelUpdateProposalV1
}
