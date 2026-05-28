// ============================================================
// SOVEREIGN OMEGA — Ledger Persistence Seam
// EPISTEMIC TIER: T0 · Gate 23
//
// Deterministic serialization/deserialization layer for ledger
// state. This is the persistence seam — it does not connect to
// any database, but provides the exact contract that a crash-safe
// storage layer would implement.
//
// BigInt (SequenceNumber) fields are serialized as decimal strings.
// The canonical form uses RFC 8785 JCS ordering for determinism.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import {
  type LedgerEntry,
  type LedgerSnapshot,
  LEDGER_SCHEMA_VERSION,
} from './types.js'
import { LedgerChain } from './chain.js'
import { captureCheckpoint } from './checkpoint.js'

// ─── Error ─────────────────────────────────────────────────

export class LedgerPersistenceError extends Error {
  constructor(msg: string) {
    super(msg)
    this.name = 'LedgerPersistenceError'
  }
}

// ─── Serialization helpers ─────────────────────────────────

/**
 * Convert a LedgerSnapshot to a plain object suitable for JCS serialization.
 * BigInt SequenceNumber values are stored as decimal strings to survive
 * the JSON round-trip.
 */
function snapshotToSerializable(snap: Readonly<LedgerSnapshot>): Record<string, unknown> {
  const entries = snap.entries.map(e => ({
    sequence: e.sequence.toString(),
    previous_hash: e.previous_hash,
    frame_hash: e.frame_hash,
    governance_hash: e.governance_hash,
    timestamp_ms: e.timestamp_ms,
  }))

  return {
    entries,
    merkle_root: snap.merkle_root,
    snapshot_sequence: snap.snapshot_sequence.toString(),
    entry_count: snap.entry_count,
    schema_version: snap.schema_version,
    is_replay_reconstructable: snap.is_replay_reconstructable,
  }
}

// ─── serializeSnapshot ─────────────────────────────────────

/**
 * Serialize a LedgerSnapshot to a deterministic JSON string.
 * Uses RFC 8785 JCS canonical ordering — same snapshot → same bytes always.
 *
 * BigInt SequenceNumber fields are encoded as decimal strings.
 */
export function serializeSnapshot(snap: Readonly<LedgerSnapshot>): string {
  const serializable = snapshotToSerializable(snap)
  const canonical = canonicalizeJCS(serializable)
  return new TextDecoder().decode(canonical)
}

// ─── deserializeSnapshot ───────────────────────────────────

/**
 * Deserialize and validate a JSON string back to a frozen LedgerSnapshot.
 *
 * Throws LedgerPersistenceError if:
 *   - invalid JSON
 *   - missing fields or wrong types
 *   - schema_version mismatch
 *   - is_replay_reconstructable !== true
 *   - entry_count !== entries.length
 *   - any entry is missing required fields or has wrong types
 */
export function deserializeSnapshot(json: string): Readonly<LedgerSnapshot> {
  // 1. Parse JSON
  let raw: unknown
  try {
    raw = JSON.parse(json)
  } catch (err) {
    throw new LedgerPersistenceError(`Invalid JSON: ${String(err)}`)
  }

  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new LedgerPersistenceError('Snapshot must be a JSON object')
  }

  const obj = raw as Record<string, unknown>

  // 2. schema_version check
  if (obj['schema_version'] !== LEDGER_SCHEMA_VERSION) {
    throw new LedgerPersistenceError(
      `schema_version mismatch: expected ${LEDGER_SCHEMA_VERSION}, got ${String(obj['schema_version'])}`
    )
  }

  // 3. is_replay_reconstructable check
  if (obj['is_replay_reconstructable'] !== true) {
    throw new LedgerPersistenceError(
      'is_replay_reconstructable must be true'
    )
  }

  // 4. entries array
  if (!Array.isArray(obj['entries'])) {
    throw new LedgerPersistenceError('entries must be an array')
  }
  const rawEntries = obj['entries'] as unknown[]

  // 5. entry_count check
  const rawEntryCount = obj['entry_count']
  if (typeof rawEntryCount !== 'number') {
    throw new LedgerPersistenceError('entry_count must be a number')
  }
  if (rawEntryCount !== rawEntries.length) {
    throw new LedgerPersistenceError(
      `entry_count mismatch: declared ${rawEntryCount}, actual ${rawEntries.length}`
    )
  }

  // 6. merkle_root
  if (typeof obj['merkle_root'] !== 'string' || obj['merkle_root'].length !== 64) {
    throw new LedgerPersistenceError('merkle_root must be a 64-character hex string')
  }

  // 7. snapshot_sequence
  if (typeof obj['snapshot_sequence'] !== 'string') {
    throw new LedgerPersistenceError('snapshot_sequence must be a decimal string')
  }
  let snapshotSeq: SequenceNumber
  try {
    snapshotSeq = BigInt(obj['snapshot_sequence']) as SequenceNumber
  } catch {
    throw new LedgerPersistenceError(
      `snapshot_sequence is not a valid BigInt: ${obj['snapshot_sequence']}`
    )
  }

  // 8. Parse each entry
  const entries: LedgerEntry[] = rawEntries.map((rawEntry, idx) => {
    if (rawEntry === null || typeof rawEntry !== 'object' || Array.isArray(rawEntry)) {
      throw new LedgerPersistenceError(`entry[${idx}] must be an object`)
    }
    const e = rawEntry as Record<string, unknown>

    // sequence (stored as decimal string)
    if (typeof e['sequence'] !== 'string') {
      throw new LedgerPersistenceError(`entry[${idx}].sequence must be a decimal string`)
    }
    let seq: SequenceNumber
    try {
      seq = BigInt(e['sequence']) as SequenceNumber
    } catch {
      throw new LedgerPersistenceError(
        `entry[${idx}].sequence is not a valid BigInt: ${String(e['sequence'])}`
      )
    }

    // previous_hash (64-char hex)
    if (typeof e['previous_hash'] !== 'string' || e['previous_hash'].length !== 64) {
      throw new LedgerPersistenceError(
        `entry[${idx}].previous_hash must be a 64-character hex string`
      )
    }

    // frame_hash (64-char hex)
    if (typeof e['frame_hash'] !== 'string' || e['frame_hash'].length !== 64) {
      throw new LedgerPersistenceError(
        `entry[${idx}].frame_hash must be a 64-character hex string`
      )
    }

    // governance_hash (64-char hex)
    if (typeof e['governance_hash'] !== 'string' || e['governance_hash'].length !== 64) {
      throw new LedgerPersistenceError(
        `entry[${idx}].governance_hash must be a 64-character hex string`
      )
    }

    // timestamp_ms
    if (typeof e['timestamp_ms'] !== 'number') {
      throw new LedgerPersistenceError(`entry[${idx}].timestamp_ms must be a number`)
    }

    return deepFreeze<LedgerEntry>({
      sequence: seq,
      previous_hash: e['previous_hash'] as SHA256Hex,
      frame_hash: e['frame_hash'] as SHA256Hex,
      governance_hash: e['governance_hash'] as SHA256Hex,
      timestamp_ms: e['timestamp_ms'],
    })
  })

  const snapshot: LedgerSnapshot = {
    entries: Object.freeze(entries),
    merkle_root: obj['merkle_root'] as SHA256Hex,
    snapshot_sequence: snapshotSeq,
    entry_count: rawEntryCount,
    schema_version: LEDGER_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  }

  return deepFreeze(snapshot)
}

// ─── serializeChain ────────────────────────────────────────

/**
 * Export a LedgerChain to a portable JSON string (via snapshot).
 * Captures a checkpoint then serializes it deterministically.
 */
export async function serializeChain(chain: LedgerChain): Promise<string> {
  const snap = await captureCheckpoint(chain)
  return serializeSnapshot(snap)
}

// ─── deserializeChain ──────────────────────────────────────

/**
 * Import a LedgerChain from a serialized snapshot.
 * Reconstructs chain by replaying entries in sequence order.
 *
 * Throws LedgerPersistenceError on parse failure or sequence violation.
 */
export async function deserializeChain(json: string): Promise<LedgerChain> {
  let snap: Readonly<LedgerSnapshot>
  try {
    snap = deserializeSnapshot(json)
  } catch (err) {
    /* c8 ignore next -- deserializeSnapshot only throws LedgerPersistenceError; false arm is structurally unreachable */
    if (err instanceof LedgerPersistenceError) throw err
    throw new LedgerPersistenceError(`Failed to parse snapshot: ${String(err)}`)
  }

  let chain = LedgerChain.empty()
  for (const entry of snap.entries) {
    try {
      chain = chain.append(entry)
    } catch (err) {
      throw new LedgerPersistenceError(
        `Sequence violation during chain reconstruction at sequence ${entry.sequence}: ${String(err)}`
      )
    }
  }

  return chain
}
