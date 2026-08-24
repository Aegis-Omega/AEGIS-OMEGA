// ============================================================
// AEGIS Scale OS — Signed Control-Plane Events V1
// EPISTEMIC TIER: T1/T2 — deterministic contracts + Ed25519
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import { signBytes, verifyBytes } from '../consensus/crypto.js'

export const SCALE_OS_EVENT_SCHEMA_VERSION = '1.0.0' as const
export type ScaleOSEventSchemaVersionV1 = typeof SCALE_OS_EVENT_SCHEMA_VERSION
export type DecimalSequenceV1 = string
export type Ed25519PublicKeyHexV1 = string
export type Ed25519SignatureHexV1 = string

export type ScaleOSEventTypeV1 =
  | 'REQUEST_CREATED'
  | 'REQUEST_VALIDATED'
  | 'APPROVAL_REQUESTED'
  | 'APPROVAL_GRANTED'
  | 'APPROVAL_DENIED'
  | 'APPROVAL_REVOKED'
  | 'APPROVAL_EXPIRED'
  | 'EXECUTION_STARTED'
  | 'EXECUTION_SUCCEEDED'
  | 'EXECUTION_FAILED'
  | 'EXECUTION_REVERTED'
  | 'VERIFICATION_RECORDED'

export type ScaleOSApprovalStateV1 =
  | 'REQUESTED'
  | 'VALIDATED'
  | 'PENDING_OPERATOR'
  | 'APPROVED'
  | 'EXECUTING'
  | 'SUCCEEDED'
  | 'DENIED'
  | 'EXPIRED'
  | 'REVOKED'
  | 'FAILED'
  | 'REVERTED'

export interface ScaleOSRoleIdentityV1 {
  actor_id: string
  session_id: string
  executor_id: string
}

export interface ScaleOSIdentitySetV1 {
  request: ScaleOSRoleIdentityV1
  approval: ScaleOSRoleIdentityV1 | null
  execution: ScaleOSRoleIdentityV1 | null
  verification: ScaleOSRoleIdentityV1 | null
}

export interface ScaleOSEventEnvelopeDraftV1 {
  schema_version: ScaleOSEventSchemaVersionV1
  event_id: string
  event_type: ScaleOSEventTypeV1
  aggregate_id: string
  sequence: DecimalSequenceV1
  previous_event_hash: SHA256Hex | null
  idempotency_key: string
  correlation_id: string
  causation_id: string | null
  emitted_at: string
  identities: ScaleOSIdentitySetV1
  signer_key_id: string
  signer_public_key: Ed25519PublicKeyHexV1
}

export interface ScaleOSSignedEventEnvelopeV1 extends ScaleOSEventEnvelopeDraftV1 {
  source_object_hash: SHA256Hex
  payload_hash: SHA256Hex
  signature: Ed25519SignatureHexV1
}

export interface ScaleOSEventReplayInputV1 {
  envelope: ScaleOSSignedEventEnvelopeV1
  source_object: unknown
  payload: unknown
}

export interface ScaleOSProjectionV1 {
  aggregate_id: string
  approval_state: ScaleOSApprovalStateV1
  sequence: DecimalSequenceV1
  head_event_hash: SHA256Hex
  applied_event_count: DecimalSequenceV1
  last_event_type: ScaleOSEventTypeV1
}

export type ScaleOSApplyOutcomeV1 = 'APPLIED' | 'NO_OP'

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const PUBLIC_KEY_PATTERN = /^[0-9a-f]{64}$/
const SIGNATURE_PATTERN = /^[0-9a-f]{128}$/
const DECIMAL_PATTERN = /^(0|[1-9][0-9]*)$/
const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:@/+\-]{1,255}$/
const ISO8601_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/

const EVENT_TYPES = new Set<ScaleOSEventTypeV1>([
  'REQUEST_CREATED',
  'REQUEST_VALIDATED',
  'APPROVAL_REQUESTED',
  'APPROVAL_GRANTED',
  'APPROVAL_DENIED',
  'APPROVAL_REVOKED',
  'APPROVAL_EXPIRED',
  'EXECUTION_STARTED',
  'EXECUTION_SUCCEEDED',
  'EXECUTION_FAILED',
  'EXECUTION_REVERTED',
  'VERIFICATION_RECORDED',
])

const TERMINAL_STATES = new Set<ScaleOSApprovalStateV1>([
  'SUCCEEDED',
  'DENIED',
  'EXPIRED',
  'REVOKED',
  'FAILED',
  'REVERTED',
])

function assertIdentifier(field: string, value: string): void {
  if (!IDENTIFIER_PATTERN.test(value)) throw new TypeError(`${field} is not a canonical identifier`)
}

function assertHash(field: string, value: string): asserts value is SHA256Hex {
  if (!SHA256_PATTERN.test(value)) throw new TypeError(`${field} must be lowercase SHA-256 hex`)
}

function assertDecimal(field: string, value: string): void {
  if (!DECIMAL_PATTERN.test(value)) throw new TypeError(`${field} must be a canonical unsigned decimal string`)
}

function assertTimestamp(field: string, value: string): void {
  if (!ISO8601_PATTERN.test(value) || Number.isNaN(Date.parse(value))) {
    throw new TypeError(`${field} must be an ISO-8601 UTC timestamp`)
  }
}

function assertIdentity(field: string, identity: ScaleOSRoleIdentityV1): void {
  assertIdentifier(`${field}.actor_id`, identity.actor_id)
  assertIdentifier(`${field}.session_id`, identity.session_id)
  assertIdentifier(`${field}.executor_id`, identity.executor_id)
}

function identityFingerprint(identity: ScaleOSRoleIdentityV1): string {
  return `${identity.actor_id}\u0000${identity.session_id}\u0000${identity.executor_id}`
}

function assertDistinctIdentityRoles(identities: ScaleOSIdentitySetV1): void {
  const present: Array<readonly [string, ScaleOSRoleIdentityV1]> = [
    ['request', identities.request],
  ]
  if (identities.approval) present.push(['approval', identities.approval])
  if (identities.execution) present.push(['execution', identities.execution])
  if (identities.verification) present.push(['verification', identities.verification])

  const fingerprints = new Map<string, string>()
  for (const [role, identity] of present) {
    const fingerprint = identityFingerprint(identity)
    const previous = fingerprints.get(fingerprint)
    if (previous) throw new TypeError(`identity roles ${previous} and ${role} must be distinct`)
    fingerprints.set(fingerprint, role)
  }
}

function assertRoleRequirements(eventType: ScaleOSEventTypeV1, identities: ScaleOSIdentitySetV1): void {
  assertIdentity('identities.request', identities.request)
  if (identities.approval) assertIdentity('identities.approval', identities.approval)
  if (identities.execution) assertIdentity('identities.execution', identities.execution)
  if (identities.verification) assertIdentity('identities.verification', identities.verification)
  assertDistinctIdentityRoles(identities)

  if ([
    'APPROVAL_GRANTED',
    'APPROVAL_DENIED',
    'APPROVAL_REVOKED',
    'APPROVAL_EXPIRED',
  ].includes(eventType) && identities.approval === null) {
    throw new TypeError(`${eventType} requires an approval identity`)
  }

  if ([
    'EXECUTION_STARTED',
    'EXECUTION_SUCCEEDED',
    'EXECUTION_FAILED',
    'EXECUTION_REVERTED',
  ].includes(eventType) && identities.execution === null) {
    throw new TypeError(`${eventType} requires an execution identity`)
  }

  if (eventType === 'VERIFICATION_RECORDED' && identities.verification === null) {
    throw new TypeError('VERIFICATION_RECORDED requires a verification identity')
  }
}

export function assertScaleOSEventEnvelopeDraftV1(draft: ScaleOSEventEnvelopeDraftV1): void {
  if (draft.schema_version !== SCALE_OS_EVENT_SCHEMA_VERSION) {
    throw new TypeError(`unsupported Scale OS event schema: ${draft.schema_version}`)
  }
  if (!EVENT_TYPES.has(draft.event_type)) throw new TypeError('event_type is invalid')
  assertIdentifier('event_id', draft.event_id)
  assertIdentifier('aggregate_id', draft.aggregate_id)
  assertDecimal('sequence', draft.sequence)
  const sequence = BigInt(draft.sequence)
  if (sequence === 0n && draft.previous_event_hash !== null) {
    throw new TypeError('sequence 0 must have a null previous_event_hash')
  }
  if (sequence > 0n) {
    if (draft.previous_event_hash === null) throw new TypeError('nonzero sequence requires previous_event_hash')
    assertHash('previous_event_hash', draft.previous_event_hash)
  }
  assertIdentifier('idempotency_key', draft.idempotency_key)
  assertIdentifier('correlation_id', draft.correlation_id)
  if (draft.causation_id !== null) assertIdentifier('causation_id', draft.causation_id)
  assertTimestamp('emitted_at', draft.emitted_at)
  assertRoleRequirements(draft.event_type, draft.identities)
  assertIdentifier('signer_key_id', draft.signer_key_id)
  if (!PUBLIC_KEY_PATTERN.test(draft.signer_public_key)) {
    throw new TypeError('signer_public_key must be 32-byte lowercase Ed25519 hex')
  }
}

export function assertScaleOSSignedEventEnvelopeV1(envelope: ScaleOSSignedEventEnvelopeV1): void {
  assertScaleOSEventEnvelopeDraftV1(envelope)
  assertHash('source_object_hash', envelope.source_object_hash)
  assertHash('payload_hash', envelope.payload_hash)
  if (!SIGNATURE_PATTERN.test(envelope.signature)) {
    throw new TypeError('signature must be 64-byte lowercase Ed25519 hex')
  }
}

export function canonicalizeScaleOSSourceObjectV1(sourceObject: unknown): Uint8Array {
  return canonicalizeJCS({ domain: 'AEGIS_SCALE_OS_SOURCE_OBJECT_V1', source_object: sourceObject })
}

export function canonicalizeScaleOSPayloadV1(payload: unknown): Uint8Array {
  return canonicalizeJCS({ domain: 'AEGIS_SCALE_OS_EVENT_PAYLOAD_V1', payload })
}

export async function hashScaleOSSourceObjectV1(sourceObject: unknown): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeScaleOSSourceObjectV1(sourceObject))
}

export async function hashScaleOSPayloadV1(payload: unknown): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeScaleOSPayloadV1(payload))
}

export function canonicalizeUnsignedScaleOSEventEnvelopeV1(
  envelope: Omit<ScaleOSSignedEventEnvelopeV1, 'signature'>,
): Uint8Array {
  return canonicalizeJCS({ domain: 'AEGIS_SCALE_OS_EVENT_ENVELOPE_V1', envelope })
}

export function canonicalizeSignedScaleOSEventEnvelopeV1(
  envelope: ScaleOSSignedEventEnvelopeV1,
): Uint8Array {
  return canonicalizeJCS({ domain: 'AEGIS_SCALE_OS_SIGNED_EVENT_V1', envelope })
}

export async function signScaleOSEventEnvelopeV1(
  draft: ScaleOSEventEnvelopeDraftV1,
  sourceObject: unknown,
  payload: unknown,
  privateKey: Uint8Array,
): Promise<ScaleOSSignedEventEnvelopeV1> {
  assertScaleOSEventEnvelopeDraftV1(draft)
  const unsigned = {
    ...draft,
    source_object_hash: await hashScaleOSSourceObjectV1(sourceObject),
    payload_hash: await hashScaleOSPayloadV1(payload),
  }
  const signature = await signBytes(privateKey, canonicalizeUnsignedScaleOSEventEnvelopeV1(unsigned))
  const envelope: ScaleOSSignedEventEnvelopeV1 = { ...unsigned, signature }
  assertScaleOSSignedEventEnvelopeV1(envelope)
  return envelope
}

export async function verifyScaleOSEventEnvelopeV1(
  envelope: ScaleOSSignedEventEnvelopeV1,
  sourceObject: unknown,
  payload: unknown,
): Promise<boolean> {
  try {
    assertScaleOSSignedEventEnvelopeV1(envelope)
    const sourceHash = await hashScaleOSSourceObjectV1(sourceObject)
    if (sourceHash !== envelope.source_object_hash) return false
    const payloadHash = await hashScaleOSPayloadV1(payload)
    if (payloadHash !== envelope.payload_hash) return false
    const { signature, ...unsigned } = envelope
    return verifyBytes(
      envelope.signer_public_key,
      canonicalizeUnsignedScaleOSEventEnvelopeV1(unsigned),
      signature,
    )
  } catch {
    return false
  }
}

export async function hashScaleOSEventEnvelopeV1(
  envelope: ScaleOSSignedEventEnvelopeV1,
): Promise<SHA256Hex> {
  assertScaleOSSignedEventEnvelopeV1(envelope)
  return sha256Hex(canonicalizeSignedScaleOSEventEnvelopeV1(envelope))
}

function transitionState(
  current: ScaleOSApprovalStateV1 | null,
  eventType: ScaleOSEventTypeV1,
): ScaleOSApprovalStateV1 {
  if (eventType === 'REQUEST_CREATED') {
    if (current !== null) throw new Error('REQUEST_CREATED requires an empty aggregate')
    return 'REQUESTED'
  }
  if (current === null) throw new Error(`${eventType} requires an existing aggregate`)
  if (eventType === 'VERIFICATION_RECORDED') {
    if (!TERMINAL_STATES.has(current)) {
      throw new Error('VERIFICATION_RECORDED requires a terminal aggregate state')
    }
    return current
  }
  if (TERMINAL_STATES.has(current)) {
    throw new Error(`terminal state ${current} cannot transition via ${eventType}`)
  }

  switch (eventType) {
    case 'REQUEST_VALIDATED':
      if (current !== 'REQUESTED') throw new Error('REQUEST_VALIDATED requires REQUESTED')
      return 'VALIDATED'
    case 'APPROVAL_REQUESTED':
      if (current !== 'VALIDATED') throw new Error('APPROVAL_REQUESTED requires VALIDATED')
      return 'PENDING_OPERATOR'
    case 'APPROVAL_GRANTED':
      if (current !== 'PENDING_OPERATOR') throw new Error('APPROVAL_GRANTED requires PENDING_OPERATOR')
      return 'APPROVED'
    case 'APPROVAL_DENIED':
      if (!['REQUESTED', 'VALIDATED', 'PENDING_OPERATOR'].includes(current)) {
        throw new Error('APPROVAL_DENIED requires a pre-approval state')
      }
      return 'DENIED'
    case 'APPROVAL_REVOKED':
      if (current !== 'APPROVED') throw new Error('APPROVAL_REVOKED requires APPROVED')
      return 'REVOKED'
    case 'APPROVAL_EXPIRED':
      if (current !== 'APPROVED') throw new Error('APPROVAL_EXPIRED requires APPROVED')
      return 'EXPIRED'
    case 'EXECUTION_STARTED':
      if (current !== 'APPROVED') throw new Error('EXECUTION_STARTED requires APPROVED')
      return 'EXECUTING'
    case 'EXECUTION_SUCCEEDED':
      if (current !== 'EXECUTING') throw new Error('EXECUTION_SUCCEEDED requires EXECUTING')
      return 'SUCCEEDED'
    case 'EXECUTION_FAILED':
      if (current !== 'EXECUTING') throw new Error('EXECUTION_FAILED requires EXECUTING')
      return 'FAILED'
    case 'EXECUTION_REVERTED':
      if (current !== 'EXECUTING') throw new Error('EXECUTION_REVERTED requires EXECUTING')
      return 'REVERTED'
  }
}

export class ScaleOSControlPlaneProjectorV1 {
  private readonly projections = new Map<string, ScaleOSProjectionV1>()
  private readonly idempotency = new Map<string, SHA256Hex>()

  getProjection(aggregateId: string): ScaleOSProjectionV1 | null {
    const projection = this.projections.get(aggregateId)
    return projection ? { ...projection } : null
  }

  async apply(input: ScaleOSEventReplayInputV1): Promise<ScaleOSApplyOutcomeV1> {
    const { envelope, source_object: sourceObject, payload } = input
    if (!await verifyScaleOSEventEnvelopeV1(envelope, sourceObject, payload)) {
      throw new Error('event signature or source/payload binding is invalid')
    }
    const eventHash = await hashScaleOSEventEnvelopeV1(envelope)
    const existingIdempotencyHash = this.idempotency.get(envelope.idempotency_key)
    if (existingIdempotencyHash) {
      if (existingIdempotencyHash === eventHash) return 'NO_OP'
      throw new Error('idempotency key conflict')
    }

    const current = this.projections.get(envelope.aggregate_id) ?? null
    const expectedSequence = current === null ? 0n : BigInt(current.sequence) + 1n
    if (BigInt(envelope.sequence) !== expectedSequence) {
      throw new Error(`sequence mismatch: expected ${expectedSequence}, got ${envelope.sequence}`)
    }
    const expectedParent = current?.head_event_hash ?? null
    if (envelope.previous_event_hash !== expectedParent) {
      throw new Error('previous_event_hash does not match aggregate head')
    }

    const approvalState = transitionState(current?.approval_state ?? null, envelope.event_type)
    const projection: ScaleOSProjectionV1 = {
      aggregate_id: envelope.aggregate_id,
      approval_state: approvalState,
      sequence: envelope.sequence,
      head_event_hash: eventHash,
      applied_event_count: String((current === null ? 0n : BigInt(current.applied_event_count)) + 1n),
      last_event_type: envelope.event_type,
    }
    this.projections.set(envelope.aggregate_id, projection)
    this.idempotency.set(envelope.idempotency_key, eventHash)
    return 'APPLIED'
  }

  async replay(inputs: readonly ScaleOSEventReplayInputV1[]): Promise<void> {
    for (const input of inputs) await this.apply(input)
  }
}
