// ============================================================
// AEGIS Operator-Sovereignty Contracts V1
// EPISTEMIC TIER: T1/T2 — mechanically canonicalized contracts
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'

export const SOVEREIGNTY_SCHEMA_VERSION = '1.0.0' as const
export type SovereigntySchemaVersion = typeof SOVEREIGNTY_SCHEMA_VERSION
export type DecimalSequence = string
export type ISO8601Timestamp = string
export type Ed25519SignatureHex = string

export interface CanonicalStateRootV1 {
  schema_version: SovereigntySchemaVersion
  repository_commit: string
  repository_tree: string
  constitutional_bundle_hash: SHA256Hex
  claims_ledger_root: SHA256Hex
  policy_hash: SHA256Hex
  deployed_artifact_hash: SHA256Hex
  workflow_identity_hash: SHA256Hex
  environment_hash: SHA256Hex
  signing_identity_hash: SHA256Hex
  parent_state_root: SHA256Hex
  sequence: DecimalSequence
}

export interface AuthorityLeaseV1 {
  schema_version: SovereigntySchemaVersion
  lease_id: string
  authority_domain: string
  holder_actor_id: string
  holder_session_id: string
  executor_id: string
  workspace_id: string
  fencing_token: DecimalSequence
  expected_head: string
  expected_parent_state_root: SHA256Hex
  authorization_hash: SHA256Hex
  issued_at: ISO8601Timestamp
  expires_at: ISO8601Timestamp
  revoked_at: ISO8601Timestamp | null
}

export type ApprovalStateV1 = 'REQUESTED' | 'APPROVED' | 'REJECTED' | 'REVOKED' | 'EXPIRED'

export interface ApprovalRecordV1 {
  schema_version: SovereigntySchemaVersion
  approval_id: string
  request_hash: SHA256Hex
  authority_domain: string
  state: ApprovalStateV1
  operator_actor_id: string
  operator_session_id: string
  decision_reason_hash: SHA256Hex
  decided_at: ISO8601Timestamp
  expires_at: ISO8601Timestamp | null
  signer_key_id: string
  signature: Ed25519SignatureHex
}

export type MutationOutcomeV1 = 'SUCCEEDED' | 'DENIED' | 'FAILED' | 'ROLLED_BACK'

export interface MutationReceiptV1 {
  schema_version: SovereigntySchemaVersion
  receipt_id: string
  canonical_state_root: SHA256Hex
  actor_id: string
  model_id: string
  session_id: string
  physical_executor_id: string
  workspace_id: string
  authority_domain: string
  authority_lease_hash: SHA256Hex
  approval_record_hash: SHA256Hex
  command_hash: SHA256Hex
  tool_id: string
  target_resource: string
  before_state_hash: SHA256Hex
  after_state_hash: SHA256Hex
  outcome: MutationOutcomeV1
  started_at: ISO8601Timestamp
  completed_at: ISO8601Timestamp
  operator_notification_hash: SHA256Hex
  signer_key_id: string
  signature: Ed25519SignatureHex
}

export type DurableExecutionStatusV1 =
  | 'REGISTERED'
  | 'RUNNING'
  | 'CANCELLING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED'
  | 'EXPIRED'

export interface DurableExecutionRecordV1 {
  schema_version: SovereigntySchemaVersion
  execution_id: string
  provider: string
  executor_id: string
  workflow_identity_hash: SHA256Hex
  canonical_state_root: SHA256Hex
  status: DurableExecutionStatusV1
  held_authority_domains: readonly string[]
  registration_time: ISO8601Timestamp
  last_heartbeat_at: ISO8601Timestamp
  heartbeat_expires_at: ISO8601Timestamp
  cancellation_endpoint_hash: SHA256Hex
  terminal_receipt_hash: SHA256Hex | null
}

export type OperatorNotificationSeverityV1 = 'INFO' | 'WARNING' | 'CRITICAL' | 'EMERGENCY'

export interface OperatorNotificationV1 {
  schema_version: SovereigntySchemaVersion
  notification_id: string
  canonical_state_root: SHA256Hex
  execution_id: string | null
  receipt_id: string | null
  severity: OperatorNotificationSeverityV1
  event_type: string
  message_hash: SHA256Hex
  emitted_at: ISO8601Timestamp
  delivery_channel: string
  delivery_status: 'PENDING' | 'DELIVERED' | 'FAILED' | 'ACKNOWLEDGED'
  acknowledged_at: ISO8601Timestamp | null
}

export type SovereigntyRecordV1 =
  | CanonicalStateRootV1
  | AuthorityLeaseV1
  | ApprovalRecordV1
  | MutationReceiptV1
  | DurableExecutionRecordV1
  | OperatorNotificationV1

export type SovereigntyRecordKindV1 =
  | 'CANONICAL_STATE_ROOT_V1'
  | 'AUTHORITY_LEASE_V1'
  | 'APPROVAL_RECORD_V1'
  | 'MUTATION_RECEIPT_V1'
  | 'DURABLE_EXECUTION_RECORD_V1'
  | 'OPERATOR_NOTIFICATION_V1'

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const GIT_OBJECT_PATTERN = /^[0-9a-f]{40,64}$/
const DECIMAL_PATTERN = /^(0|[1-9][0-9]*)$/

function assertHash(field: string, value: string): void {
  if (!SHA256_PATTERN.test(value)) throw new TypeError(`${field} must be lowercase SHA-256 hex`)
}

function assertGitObject(field: string, value: string): void {
  if (!GIT_OBJECT_PATTERN.test(value)) throw new TypeError(`${field} must be a lowercase Git object id`)
}

function assertDecimal(field: string, value: string): void {
  if (!DECIMAL_PATTERN.test(value)) throw new TypeError(`${field} must be a canonical unsigned decimal string`)
}

export function assertCanonicalStateRootV1(record: CanonicalStateRootV1): void {
  if (record.schema_version !== SOVEREIGNTY_SCHEMA_VERSION) {
    throw new TypeError(`unsupported sovereignty schema: ${record.schema_version}`)
  }
  assertGitObject('repository_commit', record.repository_commit)
  assertGitObject('repository_tree', record.repository_tree)
  assertHash('constitutional_bundle_hash', record.constitutional_bundle_hash)
  assertHash('claims_ledger_root', record.claims_ledger_root)
  assertHash('policy_hash', record.policy_hash)
  assertHash('deployed_artifact_hash', record.deployed_artifact_hash)
  assertHash('workflow_identity_hash', record.workflow_identity_hash)
  assertHash('environment_hash', record.environment_hash)
  assertHash('signing_identity_hash', record.signing_identity_hash)
  assertHash('parent_state_root', record.parent_state_root)
  assertDecimal('sequence', record.sequence)
}

export function canonicalizeSovereigntyRecordV1(
  kind: SovereigntyRecordKindV1,
  record: SovereigntyRecordV1,
): Uint8Array {
  return canonicalizeJCS({ domain: `AEGIS_${kind}`, record })
}

export async function hashSovereigntyRecordV1(
  kind: SovereigntyRecordKindV1,
  record: SovereigntyRecordV1,
): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeSovereigntyRecordV1(kind, record))
}

export async function computeCanonicalStateRootV1(record: CanonicalStateRootV1): Promise<SHA256Hex> {
  assertCanonicalStateRootV1(record)
  return hashSovereigntyRecordV1('CANONICAL_STATE_ROOT_V1', record)
}
