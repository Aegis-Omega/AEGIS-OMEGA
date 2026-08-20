// ============================================================
// SOVEREIGN OMEGA — REFLEXIVE_SELF_MODEL_V1 Metacognition Bridge
// EPISTEMIC TIER: T2 · evidence projection only
//
// Projects structured reflexive-cycle evidence into the existing
// hash-chained MetacognitiveLoop. It never emits authority, performs
// admission, or promotes the historical CONSCIOUSNESS taxonomy label.
// ============================================================

import { hashValue } from '../core/hashing.js'
import type { SequenceNumber } from '../core/types.js'
import {
  MetacognitiveLoop,
  type MetacognitiveEntry,
  type MetacognitiveLayer,
  type MetacognitiveObservation,
} from '../metacognition/loop.js'
import type { ReflexiveCycleReceiptV1 } from './contracts.js'

const HASH_RE = /^[0-9a-f]{64}$/
const ALLOWED_STATUSES = new Set([
  'CYCLE_CLOSED',
  'UNSCORABLE_POSTDICTION',
  'UNSCORABLE_STALE_BINDING',
  'UNSCORABLE_UNVERIFIED_OUTCOME',
  'CONTRADICTION_DETECTED',
  'TAMPER_DETECTED',
  'VERIFIER_UNAVAILABLE',
])

const RECEIPT_KEYS = new Set([
  'record_kind',
  'schema_version',
  'cycle_id',
  'snapshot_digest',
  'prediction_digest',
  'observation_digest',
  'prediction_error_receipt_digest',
  'update_proposal_digest',
  'replayable',
  'scorable',
  'contradiction_free',
  'cycle_status',
  'cycle_digest',
  'authority',
])

export class ReflexiveMetacognitionBridgeError extends Error {
  override readonly name = 'ReflexiveMetacognitionBridgeError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface ReflexiveMetacognitionBridgeResultV1 {
  readonly loop: MetacognitiveLoop
  readonly entries: readonly MetacognitiveEntry[]
}

function fail(message: string): never {
  throw new ReflexiveMetacognitionBridgeError(message)
}

function assertReceiptShape(receipt: ReflexiveCycleReceiptV1): void {
  if (typeof receipt !== 'object' || receipt === null || Array.isArray(receipt)) {
    fail('cycle receipt must be an object')
  }

  const keys = Object.keys(receipt as unknown as Record<string, unknown>)
  const unknown = keys.filter(key => !RECEIPT_KEYS.has(key)).sort()
  const missing = [...RECEIPT_KEYS].filter(key => !keys.includes(key)).sort()
  if (unknown.length > 0) fail(`cycle receipt contains unknown field: ${unknown[0]}`)
  if (missing.length > 0) fail(`cycle receipt missing field: ${missing[0]}`)

  if (receipt.record_kind !== 'REFLEXIVE_CYCLE_RECEIPT_V1') fail('invalid cycle receipt kind')
  if (receipt.schema_version !== '1.0.0') fail('invalid cycle receipt schema version')
  if (receipt.authority !== 'REFLEXIVE_EVIDENCE_ONLY') fail('invalid cycle receipt authority')
  if (typeof receipt.cycle_id !== 'string' || receipt.cycle_id.length === 0) fail('invalid cycle_id')
  if (!ALLOWED_STATUSES.has(receipt.cycle_status)) fail('invalid cycle_status')
  if (
    typeof receipt.replayable !== 'boolean' ||
    typeof receipt.scorable !== 'boolean' ||
    typeof receipt.contradiction_free !== 'boolean'
  ) fail('cycle receipt flags must be boolean')

  for (const [name, value] of [
    ['snapshot_digest', receipt.snapshot_digest],
    ['prediction_digest', receipt.prediction_digest],
    ['observation_digest', receipt.observation_digest],
    ['prediction_error_receipt_digest', receipt.prediction_error_receipt_digest],
    ['update_proposal_digest', receipt.update_proposal_digest],
    ['cycle_digest', receipt.cycle_digest],
  ] as const) {
    if (!HASH_RE.test(value)) fail(`${name} must be lowercase sha256 hex`)
  }
}

async function assertCycleDigest(receipt: ReflexiveCycleReceiptV1): Promise<void> {
  const { cycle_digest: _cycleDigest, ...body } = receipt
  const expected = await hashValue(body)
  if (expected !== receipt.cycle_digest) {
    fail('cycle receipt digest mismatch')
  }
}

function stableObservation(
  layer: MetacognitiveLayer,
  signal: string,
): MetacognitiveObservation {
  return Object.freeze({ layer, signal, tier: 'T2' })
}

function projections(receipt: ReflexiveCycleReceiptV1): readonly MetacognitiveObservation[] {
  const cycle = receipt.cycle_id
  const cycleDigest = receipt.cycle_digest.slice(0, 12)
  const base: MetacognitiveObservation[] = [
    stableObservation(
      'SELF_MODEL',
      `reflexive cycle=${cycle} prediction=${receipt.prediction_digest.slice(0, 12)} cycle_digest=${cycleDigest} sealed`,
    ),
    stableObservation(
      'PERCEPTION',
      `reflexive cycle=${cycle} observation=${receipt.observation_digest.slice(0, 12)} cycle_digest=${cycleDigest} captured`,
    ),
    stableObservation(
      'METACOGNITIVE',
      `reflexive cycle=${cycle} error=${receipt.prediction_error_receipt_digest.slice(0, 12)} status=${receipt.cycle_status} cycle_digest=${cycleDigest}`,
    ),
    stableObservation(
      'SELF_MODEL',
      `reflexive cycle=${cycle} update=${receipt.update_proposal_digest.slice(0, 12)} status=${receipt.cycle_status} cycle_digest=${cycleDigest} proposed`,
    ),
  ]

  if (!receipt.contradiction_free || receipt.cycle_status === 'CONTRADICTION_DETECTED') {
    base.push(stableObservation(
      'METACOGNITIVE',
      `reflexive cycle=${cycle} status=CONTRADICTION_DETECTED cycle_digest=${cycleDigest}`,
    ))
  }

  return Object.freeze(base)
}

export async function appendReflexiveCycleToMetacognition(
  loop: MetacognitiveLoop,
  receipt: ReflexiveCycleReceiptV1,
  startingSequence: SequenceNumber,
): Promise<ReflexiveMetacognitionBridgeResultV1> {
  assertReceiptShape(receipt)
  await assertCycleDigest(receipt)

  let current = loop
  let sequence = startingSequence as bigint
  const entries: MetacognitiveEntry[] = []

  for (const observation of projections(receipt)) {
    sequence += 1n
    const advanced = await current.observe(observation, sequence as SequenceNumber)
    current = advanced.loop
    entries.push(advanced.entry)
  }

  return Object.freeze({
    loop: current,
    entries: Object.freeze(entries),
  })
}
