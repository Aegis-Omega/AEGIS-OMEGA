// ============================================================
// AEGIS Experiment Admission Gate v0.1
// EPISTEMIC TIER: T1 — deterministic admission contracts
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'

export const EXPERIMENT_ADMISSION_SCHEMA_VERSION = '0.1.0' as const
export type ExperimentAdmissionSchemaVersion = typeof EXPERIMENT_ADMISSION_SCHEMA_VERSION
export type ExperimentExecutionClassV01 = 'BOOTSTRAP_GOVERNANCE' | 'EXPERIMENT'
export type ExperimentEvidenceTierV01 = 'T0' | 'T1' | 'T2' | 'T3'

export interface GitEvidenceBindingV01 {
  path: string
  blob_id: string
}

export interface ExperimentApprovalV01 {
  required: true
  state: 'APPROVED'
  operator_actor_id: string
  operator_session_id: string
  authorization_basis: string
  decided_at: string
  signature_mode: 'GITHUB_OIDC_ATTESTATION'
  approval_record_hash: SHA256Hex
}

export interface ExperimentBudgetV01 {
  max_duration_seconds: number
  max_mutations: number
  max_cost_microunits: number
}

export interface ExperimentObservabilityV01 {
  provider: 'github-actions'
  durable_execution_required: true
  cancellation_mechanism: 'github-actions-cancel-run'
  heartbeat_max_seconds: number
  emergency_stop_reference: string
}

export interface ExperimentReplayPackageV01 {
  required: true
  include_plan: true
  include_admission_receipt: true
  include_evidence_manifest: true
  include_integration_ledger: true
}

export interface ExperimentPlanV01 {
  schema_version: ExperimentAdmissionSchemaVersion
  experiment_id: string
  title: string
  execution_class: ExperimentExecutionClassV01
  repository: string
  expected_parent_sha: string
  expected_parent_state_root: SHA256Hex
  constitution: GitEvidenceBindingV01
  policy: GitEvidenceBindingV01
  sovereignty_contracts: GitEvidenceBindingV01
  claims_ledger: {
    path: string
    root: SHA256Hex
  }
  admission_workflow: GitEvidenceBindingV01
  admission_executable: GitEvidenceBindingV01
  integration_ledger_generator: GitEvidenceBindingV01
  requested_authority_domains: readonly string[]
  expected_outputs: readonly string[]
  evidence_tier: ExperimentEvidenceTierV01
  budget: ExperimentBudgetV01
  termination_conditions: readonly string[]
  operator_approval: ExperimentApprovalV01
  observability: ExperimentObservabilityV01
  replay_package: ExperimentReplayPackageV01
}

export interface AdmissionContextV01 {
  repository: string
  candidate_sha: string
  parent_sha: string
  source_timestamp: string
  workflow_ref: string
  workflow_run_id: string
  workflow_run_attempt: string
}

export interface AdmissionEvidenceV01 {
  plan_path: string
  plan_sha256: SHA256Hex
  constitution_sha256: SHA256Hex
  policy_sha256: SHA256Hex
  sovereignty_contracts_sha256: SHA256Hex
  claims_ledger_sha256: SHA256Hex
  admission_workflow_sha256: SHA256Hex
  admission_executable_sha256: SHA256Hex
  integration_ledger_generator_sha256: SHA256Hex
  integration_ledger_json_sha256: SHA256Hex
}

export interface ExperimentAdmissionReceiptV01 {
  schema_version: ExperimentAdmissionSchemaVersion
  receipt_kind: 'AEGIS_EXPERIMENT_ADMISSION_RECEIPT_V0_1'
  outcome: 'ADMITTED'
  experiment_id: string
  repository: string
  candidate_sha: string
  parent_sha: string
  parent_state_root: SHA256Hex
  plan_path: string
  plan_digest: SHA256Hex
  requested_authority_domains: readonly string[]
  evidence_tier: ExperimentEvidenceTierV01
  budget: ExperimentBudgetV01
  operator_approval_hash: SHA256Hex
  observability_provider: 'github-actions'
  workflow_ref: string
  workflow_run_id: string
  workflow_run_attempt: string
  source_timestamp: string
  evidence: AdmissionEvidenceV01
  receipt_hash: SHA256Hex
}

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const GIT_OBJECT_PATTERN = /^[0-9a-f]{40,64}$/
const EXPERIMENT_ID_PATTERN = /^[a-z0-9][a-z0-9._-]{2,127}$/
const SAFE_PATH_PATTERN = /^(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9._@/+:-]+$/

function assertString(field: string, value: unknown): asserts value is string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new TypeError(`${field} must be a non-empty string`)
  }
}

function assertHash(field: string, value: unknown): asserts value is SHA256Hex {
  if (typeof value !== 'string' || !SHA256_PATTERN.test(value)) {
    throw new TypeError(`${field} must be lowercase SHA-256 hex`)
  }
}

function assertGitObject(field: string, value: unknown): asserts value is string {
  if (typeof value !== 'string' || !GIT_OBJECT_PATTERN.test(value)) {
    throw new TypeError(`${field} must be a lowercase Git object id`)
  }
}

function assertSafePath(field: string, value: unknown): asserts value is string {
  assertString(field, value)
  if (!SAFE_PATH_PATTERN.test(value)) throw new TypeError(`${field} must be a repository-relative safe path`)
}

function assertSortedUnique(field: string, values: readonly string[]): void {
  if (values.length === 0) throw new TypeError(`${field} must not be empty`)
  const sorted = [...values].sort()
  if (new Set(values).size !== values.length || values.some((value, index) => value !== sorted[index])) {
    throw new TypeError(`${field} must be sorted and unique`)
  }
}

function assertBinding(field: string, binding: GitEvidenceBindingV01): void {
  assertSafePath(`${field}.path`, binding.path)
  assertGitObject(`${field}.blob_id`, binding.blob_id)
}

export function approvalPayloadV01(approval: ExperimentApprovalV01): Record<string, unknown> {
  return {
    required: approval.required,
    state: approval.state,
    operator_actor_id: approval.operator_actor_id,
    operator_session_id: approval.operator_session_id,
    authorization_basis: approval.authorization_basis,
    decided_at: approval.decided_at,
    signature_mode: approval.signature_mode,
  }
}

export async function computeApprovalRecordHashV01(approval: ExperimentApprovalV01): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_OPERATOR_APPROVAL_V0_1',
    approval: approvalPayloadV01(approval),
  }))
}

export async function computeExpectedParentStateRootV01(plan: ExperimentPlanV01): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_EXPERIMENT_PARENT_STATE_V0_1',
    repository: plan.repository,
    expected_parent_sha: plan.expected_parent_sha,
    constitution_blob_id: plan.constitution.blob_id,
    policy_blob_id: plan.policy.blob_id,
    sovereignty_contracts_blob_id: plan.sovereignty_contracts.blob_id,
    claims_ledger_root: plan.claims_ledger.root,
  }))
}

export function canonicalizeExperimentPlanV01(plan: ExperimentPlanV01): Uint8Array {
  return canonicalizeJCS({ domain: 'AEGIS_EXPERIMENT_PLAN_V0_1', plan })
}

export async function hashExperimentPlanV01(plan: ExperimentPlanV01): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeExperimentPlanV01(plan))
}

export async function assertExperimentPlanV01(
  plan: ExperimentPlanV01,
  context: AdmissionContextV01,
): Promise<void> {
  if (plan.schema_version !== EXPERIMENT_ADMISSION_SCHEMA_VERSION) {
    throw new TypeError(`unsupported experiment admission schema: ${plan.schema_version}`)
  }
  if (!EXPERIMENT_ID_PATTERN.test(plan.experiment_id)) throw new TypeError('experiment_id is invalid')
  assertString('title', plan.title)
  if (plan.execution_class !== 'BOOTSTRAP_GOVERNANCE' && plan.execution_class !== 'EXPERIMENT') {
    throw new TypeError('execution_class is invalid')
  }
  if (plan.repository !== context.repository) throw new TypeError('repository does not match workflow context')
  assertGitObject('expected_parent_sha', plan.expected_parent_sha)
  if (plan.expected_parent_sha !== context.parent_sha) throw new TypeError('expected_parent_sha does not match admitted parent')
  assertHash('expected_parent_state_root', plan.expected_parent_state_root)
  assertBinding('constitution', plan.constitution)
  assertBinding('policy', plan.policy)
  assertBinding('sovereignty_contracts', plan.sovereignty_contracts)
  assertSafePath('claims_ledger.path', plan.claims_ledger.path)
  assertHash('claims_ledger.root', plan.claims_ledger.root)
  assertBinding('admission_workflow', plan.admission_workflow)
  assertBinding('admission_executable', plan.admission_executable)
  assertBinding('integration_ledger_generator', plan.integration_ledger_generator)

  if (!Array.isArray(plan.requested_authority_domains)) throw new TypeError('requested_authority_domains must be an array')
  plan.requested_authority_domains.forEach((value, index) => assertString(`requested_authority_domains[${index}]`, value))
  assertSortedUnique('requested_authority_domains', plan.requested_authority_domains)

  if (!Array.isArray(plan.expected_outputs)) throw new TypeError('expected_outputs must be an array')
  plan.expected_outputs.forEach((value, index) => assertSafePath(`expected_outputs[${index}]`, value))
  assertSortedUnique('expected_outputs', plan.expected_outputs)

  if (!['T0', 'T1', 'T2', 'T3'].includes(plan.evidence_tier)) throw new TypeError('evidence_tier is invalid')

  if (!Number.isInteger(plan.budget.max_duration_seconds) ||
      plan.budget.max_duration_seconds < 1 ||
      plan.budget.max_duration_seconds > 21600) {
    throw new TypeError('budget.max_duration_seconds must be an integer in [1, 21600]')
  }
  if (!Number.isInteger(plan.budget.max_mutations) ||
      plan.budget.max_mutations < 0 ||
      plan.budget.max_mutations > 1000) {
    throw new TypeError('budget.max_mutations must be an integer in [0, 1000]')
  }
  if (!Number.isSafeInteger(plan.budget.max_cost_microunits) ||
      plan.budget.max_cost_microunits < 0 ||
      plan.budget.max_cost_microunits > 1_000_000_000_000) {
    throw new TypeError('budget.max_cost_microunits is outside the admitted range')
  }

  if (!Array.isArray(plan.termination_conditions)) throw new TypeError('termination_conditions must be an array')
  plan.termination_conditions.forEach((value, index) => assertString(`termination_conditions[${index}]`, value))
  assertSortedUnique('termination_conditions', plan.termination_conditions)
  for (const required of ['budget_exhausted', 'operator_emergency_stop', 'observability_expired']) {
    if (!plan.termination_conditions.includes(required)) throw new TypeError(`termination_conditions missing ${required}`)
  }

  if (plan.operator_approval.required !== true || plan.operator_approval.state !== 'APPROVED') {
    throw new TypeError('operator approval must be explicitly APPROVED')
  }
  assertString('operator_approval.operator_actor_id', plan.operator_approval.operator_actor_id)
  assertString('operator_approval.operator_session_id', plan.operator_approval.operator_session_id)
  assertString('operator_approval.authorization_basis', plan.operator_approval.authorization_basis)
  assertString('operator_approval.decided_at', plan.operator_approval.decided_at)
  if (plan.operator_approval.signature_mode !== 'GITHUB_OIDC_ATTESTATION') {
    throw new TypeError('operator approval signature mode is unsupported')
  }
  assertHash('operator_approval.approval_record_hash', plan.operator_approval.approval_record_hash)
  const approvalHash = await computeApprovalRecordHashV01(plan.operator_approval)
  if (approvalHash !== plan.operator_approval.approval_record_hash) {
    throw new TypeError('operator approval hash mismatch')
  }

  if (plan.observability.provider !== 'github-actions' ||
      plan.observability.durable_execution_required !== true ||
      plan.observability.cancellation_mechanism !== 'github-actions-cancel-run') {
    throw new TypeError('observability contract is invalid')
  }
  if (!Number.isInteger(plan.observability.heartbeat_max_seconds) ||
      plan.observability.heartbeat_max_seconds < 30 ||
      plan.observability.heartbeat_max_seconds > 3600) {
    throw new TypeError('observability.heartbeat_max_seconds must be in [30, 3600]')
  }
  assertString('observability.emergency_stop_reference', plan.observability.emergency_stop_reference)

  if (plan.replay_package.required !== true ||
      plan.replay_package.include_plan !== true ||
      plan.replay_package.include_admission_receipt !== true ||
      plan.replay_package.include_evidence_manifest !== true ||
      plan.replay_package.include_integration_ledger !== true) {
    throw new TypeError('replay package is incomplete')
  }

  const parentRoot = await computeExpectedParentStateRootV01(plan)
  if (parentRoot !== plan.expected_parent_state_root) throw new TypeError('expected parent state root mismatch')

  assertGitObject('candidate_sha', context.candidate_sha)
  assertString('source_timestamp', context.source_timestamp)
  assertString('workflow_ref', context.workflow_ref)
  assertString('workflow_run_id', context.workflow_run_id)
  assertString('workflow_run_attempt', context.workflow_run_attempt)
}

export async function buildAdmissionReceiptV01(
  plan: ExperimentPlanV01,
  context: AdmissionContextV01,
  evidence: AdmissionEvidenceV01,
): Promise<ExperimentAdmissionReceiptV01> {
  await assertExperimentPlanV01(plan, context)
  const planDigest = await hashExperimentPlanV01(plan)
  if (planDigest !== evidence.plan_sha256) throw new TypeError('evidence plan digest mismatch')

  const unsigned = {
    schema_version: EXPERIMENT_ADMISSION_SCHEMA_VERSION,
    receipt_kind: 'AEGIS_EXPERIMENT_ADMISSION_RECEIPT_V0_1' as const,
    outcome: 'ADMITTED' as const,
    experiment_id: plan.experiment_id,
    repository: context.repository,
    candidate_sha: context.candidate_sha,
    parent_sha: context.parent_sha,
    parent_state_root: plan.expected_parent_state_root,
    plan_path: evidence.plan_path,
    plan_digest: planDigest,
    requested_authority_domains: [...plan.requested_authority_domains],
    evidence_tier: plan.evidence_tier,
    budget: plan.budget,
    operator_approval_hash: plan.operator_approval.approval_record_hash,
    observability_provider: plan.observability.provider,
    workflow_ref: context.workflow_ref,
    workflow_run_id: context.workflow_run_id,
    workflow_run_attempt: context.workflow_run_attempt,
    source_timestamp: context.source_timestamp,
    evidence,
  }
  const receiptHash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_EXPERIMENT_ADMISSION_RECEIPT_V0_1',
    receipt: unsigned,
  }))
  return { ...unsigned, receipt_hash: receiptHash }
}
