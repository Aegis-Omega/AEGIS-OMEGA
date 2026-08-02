import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'

export const LIFEQUEST_EVENT_SCHEMA_VERSION = '1.0.0' as const
export const LIFEQUEST_ADMISSION_SCHEMA_VERSION = '1.0.0' as const

export type LifeQuestStatusV1 =
  | 'DRAFT'
  | 'ACTIVE'
  | 'EVIDENCE_PENDING'
  | 'READY_FOR_REVIEW'
  | 'COMPLETED'
  | 'REJECTED'

export type LifeQuestEventTypeV1 =
  | 'QUEST_SELECTED'
  | 'QUEST_ACTIVATION_REQUESTED'
  | 'EVIDENCE_REQUESTED'
  | 'EVIDENCE_SUBMITTED'
  | 'COMPLETION_CONFIRMATION_REQUESTED'
  | 'COMPLETION_REJECTED'

export type JSONPrimitive = string | number | boolean | null
export type JSONValue = JSONPrimitive | readonly JSONValue[] | { readonly [key: string]: JSONValue }

export interface LifeQuestEventV1 {
  schemaVersion: typeof LIFEQUEST_EVENT_SCHEMA_VERSION
  eventId: string
  questId: string
  eventType: LifeQuestEventTypeV1
  actorId: string
  occurredAt: string
  authorityMode: 'PROPOSAL_ONLY'
  payload: Readonly<Record<string, JSONValue>>
}

export interface LifeQuestAdmissionCandidateV1 {
  schemaVersion: typeof LIFEQUEST_ADMISSION_SCHEMA_VERSION
  candidateId: string
  authorityDomain: 'lifequest.quest-state'
  sourceEventHash: SHA256Hex
  sourceEvent: LifeQuestEventV1
  expectedQuestStatus: LifeQuestStatusV1
  requestedQuestStatus: LifeQuestStatusV1
  requiredApproval: 'OPERATOR_EXPLICIT'
  admissionStatus: 'PENDING_OPERATOR'
  executionAuthorityGranted: false
  canonicalStateRoot: null
  authorityLeaseHash: null
  approvalRecordHash: null
}

const EVENT_KEYS = [
  'actorId',
  'authorityMode',
  'eventId',
  'eventType',
  'occurredAt',
  'payload',
  'questId',
  'schemaVersion',
] as const

const LIFEQUEST_EVENT_TYPES = new Set<LifeQuestEventTypeV1>([
  'QUEST_SELECTED',
  'QUEST_ACTIVATION_REQUESTED',
  'EVIDENCE_REQUESTED',
  'EVIDENCE_SUBMITTED',
  'COMPLETION_CONFIRMATION_REQUESTED',
  'COMPLETION_REJECTED',
])

const ALLOWED_TRANSITIONS: Readonly<Record<LifeQuestStatusV1, readonly LifeQuestStatusV1[]>> = {
  DRAFT: ['ACTIVE'],
  ACTIVE: ['EVIDENCE_PENDING'],
  EVIDENCE_PENDING: ['READY_FOR_REVIEW'],
  READY_FOR_REVIEW: ['COMPLETED', 'ACTIVE'],
  COMPLETED: [],
  REJECTED: ['ACTIVE'],
}

const ISO_8601_UTC_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/

function assertBoundedString(field: string, value: unknown, maxLength: number): asserts value is string {
  if (typeof value !== 'string' || value.length === 0 || value.length > maxLength) {
    throw new TypeError(`${field} must be a non-empty string of at most ${maxLength} characters`)
  }
}

function assertExactKeys(value: Record<string, unknown>, expected: readonly string[], field: string): void {
  const actual = Object.keys(value).sort()
  const required = [...expected].sort()
  if (actual.length !== required.length || actual.some((key, index) => key !== required[index])) {
    throw new TypeError(`${field} contains missing or unexpected fields`)
  }
}

function assertStrictJSON(value: unknown, path: string, seen: WeakSet<object>): asserts value is JSONValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return

  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new TypeError(`${path} contains a non-finite number`)
    return
  }

  if (typeof value !== 'object') {
    throw new TypeError(`${path} contains a non-JSON value`)
  }

  if (seen.has(value)) {
    throw new TypeError(`${path} contains a cycle or shared object alias`)
  }
  seen.add(value)

  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      if (!(index in value)) throw new TypeError(`${path} contains a sparse array`)
      assertStrictJSON(value[index], `${path}[${index}]`, seen)
    }
    return
  }

  const prototype = Object.getPrototypeOf(value)
  if (prototype !== Object.prototype && prototype !== null) {
    throw new TypeError(`${path} must contain only plain objects`)
  }

  if (Object.getOwnPropertySymbols(value).length > 0) {
    throw new TypeError(`${path} contains symbol keys`)
  }

  const descriptors = Object.getOwnPropertyDescriptors(value)
  for (const [key, descriptor] of Object.entries(descriptors)) {
    if (!descriptor.enumerable) throw new TypeError(`${path}.${key} must be enumerable`)
    if ('get' in descriptor || 'set' in descriptor) {
      throw new TypeError(`${path}.${key} must be a data property`)
    }
    if (descriptor.value === undefined) throw new TypeError(`${path}.${key} must not be undefined`)
    assertStrictJSON(descriptor.value, `${path}.${key}`, seen)
  }
}

export function assertLifeQuestEventV1(value: unknown): asserts value is LifeQuestEventV1 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('LifeQuest event must be an object')
  }

  const event = value as Record<string, unknown>
  assertExactKeys(event, EVENT_KEYS, 'LifeQuest event')

  if (event.schemaVersion !== LIFEQUEST_EVENT_SCHEMA_VERSION) {
    throw new TypeError(`unsupported LifeQuest event schema: ${String(event.schemaVersion)}`)
  }

  assertBoundedString('eventId', event.eventId, 160)
  assertBoundedString('questId', event.questId, 160)
  assertBoundedString('actorId', event.actorId, 256)

  if (!LIFEQUEST_EVENT_TYPES.has(event.eventType as LifeQuestEventTypeV1)) {
    throw new TypeError(`unsupported LifeQuest event type: ${String(event.eventType)}`)
  }

  if (event.authorityMode !== 'PROPOSAL_ONLY') {
    throw new TypeError('LifeQuest clients may submit proposal-only events')
  }

  if (typeof event.occurredAt !== 'string' || !ISO_8601_UTC_PATTERN.test(event.occurredAt)) {
    throw new TypeError('occurredAt must be an ISO-8601 UTC timestamp with milliseconds')
  }

  if (!event.payload || typeof event.payload !== 'object' || Array.isArray(event.payload)) {
    throw new TypeError('payload must be a JSON object')
  }

  assertStrictJSON(event.payload, 'payload', new WeakSet<object>())
}

export function assertLifeQuestTransitionAllowed(
  expectedStatus: LifeQuestStatusV1,
  requestedStatus: LifeQuestStatusV1,
): void {
  if (!ALLOWED_TRANSITIONS[expectedStatus].includes(requestedStatus)) {
    throw new TypeError(`illegal LifeQuest transition: ${expectedStatus} -> ${requestedStatus}`)
  }
}

export function canonicalizeLifeQuestEventV1(event: LifeQuestEventV1): Uint8Array {
  assertLifeQuestEventV1(event)
  return canonicalizeJCS({ domain: 'AEGIS_LIFEQUEST_EVENT_V1', event })
}

export async function hashLifeQuestEventV1(event: LifeQuestEventV1): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeLifeQuestEventV1(event))
}

export async function buildLifeQuestAdmissionCandidateV1(input: {
  event: LifeQuestEventV1
  expectedQuestStatus: LifeQuestStatusV1
  requestedQuestStatus: LifeQuestStatusV1
}): Promise<LifeQuestAdmissionCandidateV1> {
  assertLifeQuestEventV1(input.event)
  assertLifeQuestTransitionAllowed(input.expectedQuestStatus, input.requestedQuestStatus)

  const sourceEventHash = await hashLifeQuestEventV1(input.event)

  return {
    schemaVersion: LIFEQUEST_ADMISSION_SCHEMA_VERSION,
    candidateId: `lifequest-admission:${sourceEventHash}`,
    authorityDomain: 'lifequest.quest-state',
    sourceEventHash,
    sourceEvent: input.event,
    expectedQuestStatus: input.expectedQuestStatus,
    requestedQuestStatus: input.requestedQuestStatus,
    requiredApproval: 'OPERATOR_EXPLICIT',
    admissionStatus: 'PENDING_OPERATOR',
    executionAuthorityGranted: false,
    canonicalStateRoot: null,
    authorityLeaseHash: null,
    approvalRecordHash: null,
  }
}
