// ============================================================
// SOVEREIGN OMEGA — Deterministic Message Queue
// EPISTEMIC TIER: T2 · Gate 24
//
// DeterministicMessageQueue guarantees:
//   1. Messages are processed in lexicographic message_id order,
//      regardless of arrival order (determinism under reordering).
//   2. Duplicate message_id → DUPLICATE (idempotent delivery).
//   3. Same (sender, sequence) with different payload_hash →
//      NetworkError (anti-equivocation enforcement).
//
// No Map/Set in queue state — sorted arrays only, RFC 8785 safe.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type {
  ReplayMessage,
  MessageId,
  DeliveryResult,
} from './types.js'
import { NetworkError } from './types.js'

// ─── Internal record (array-based, no Map/Set) ────────────

interface QueueEntry {
  readonly message_id: MessageId
  readonly message: ReplayMessage
}

// ─── Helpers ───────────────────────────────────────────────

/** Lexicographic comparison for message_id strings. */
function compareMessageIds(a: MessageId, b: MessageId): number {
  if (a < b) return -1
  if (a > b) return 1
  return 0
}

/** Binary search: find insertion index for a new message_id. */
function findInsertionIndex(entries: readonly QueueEntry[], id: MessageId): number {
  let lo = 0
  let hi = entries.length
  while (lo < hi) {
    const mid = (lo + hi) >>> 1
    const entry = entries[mid]
    /* c8 ignore next -- noUncheckedIndexedAccess; binary search guarantees mid < entries.length */
    if (entry === undefined) break
    if (compareMessageIds(entry.message_id, id) < 0) {
      lo = mid + 1
    } else {
      hi = mid
    }
  }
  return lo
}

/** Find an entry by message_id via binary search. Returns index or -1. */
function findById(entries: readonly QueueEntry[], id: MessageId): number {
  let lo = 0
  let hi = entries.length - 1
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1
    const entry = entries[mid]
    /* c8 ignore next -- noUncheckedIndexedAccess; binary search guarantees mid < entries.length */
    if (entry === undefined) break
    const cmp = compareMessageIds(entry.message_id, id)
    if (cmp === 0) return mid
    if (cmp < 0) lo = mid + 1
    else hi = mid - 1
  }
  return -1
}

// ─── Queue State ───────────────────────────────────────────

interface QueueState {
  /** Sorted by message_id lexicographically. */
  readonly entries: readonly QueueEntry[]
  /**
   * Anti-equivocation index: sorted array of "<sender>:<sequence>" keys.
   * Parallel array payload_hashes stores the corresponding payload_hash.
   * No Map — arrays only.
   */
  readonly equivocation_keys: readonly string[]
  readonly equivocation_hashes: readonly string[]
}

// ─── DeterministicMessageQueue ────────────────────────────

/**
 * A pure-state, deterministic message queue.
 *
 * All state is stored in sorted arrays (no Map/Set) so that
 * RFC 8785 canonicalization of the queue state is well-defined.
 * Each method returns a new frozen queue instance — mutation-free.
 */
export class DeterministicMessageQueue {
  private readonly _state: QueueState

  private constructor(state: QueueState) {
    this._state = deepFreeze(state) as QueueState
  }

  static create(): DeterministicMessageQueue {
    return new DeterministicMessageQueue(
      deepFreeze({ entries: [], equivocation_keys: [], equivocation_hashes: [] }) as QueueState,
    )
  }

  get size(): number {
    return this._state.entries.length
  }

  /**
   * Enqueue a message.
   *
   * Returns a tuple of [newQueue, DeliveryResult]:
   *   - DELIVERED: message accepted and inserted in sorted order.
   *   - DUPLICATE: message_id already present (idempotent, no insert).
   *   - NetworkError thrown: same (sender, sequence) but different payload_hash
   *     (anti-equivocation violation).
   */
  enqueue(msg: ReplayMessage): [DeterministicMessageQueue, DeliveryResult] {
    const { entries, equivocation_keys, equivocation_hashes } = this._state

    // ── Duplicate detection ──────────────────────────────
    const existingIdx = findById(entries, msg.message_id)
    if (existingIdx !== -1) {
      const result = deepFreeze<DeliveryResult>({
        message: msg,
        status: 'DUPLICATE',
        reason: `message_id ${msg.message_id} already present`,
      })
      return [this, result]
    }

    // ── Anti-equivocation ────────────────────────────────
    const equivKey = `${msg.sender}:${String(msg.sequence)}`
    const keyIdx = binarySearchString(equivocation_keys, equivKey)
    if (keyIdx !== -1) {
      const existingHash = equivocation_hashes[keyIdx]
      if (existingHash !== msg.payload_hash) {
        throw new NetworkError(
          `Anti-equivocation violation: sender=${msg.sender} sequence=${msg.sequence} ` +
          `has conflicting payload_hash (existing=${existingHash}, new=${msg.payload_hash})`,
        )
      }
      // Same payload_hash for same (sender, sequence): allow (it's a retransmit, not equivocation)
    }

    // ── Insert in sorted position ────────────────────────
    const insertAt = findInsertionIndex(entries, msg.message_id)
    const newEntries: QueueEntry[] = [
      ...entries.slice(0, insertAt),
      { message_id: msg.message_id, message: msg },
      ...entries.slice(insertAt),
    ]

    // ── Update equivocation index ────────────────────────
    let newKeys: string[]
    let newHashes: string[]
    if (keyIdx === -1) {
      const keyInsertAt = findStringInsertionIndex(equivocation_keys, equivKey)
      newKeys = [
        ...equivocation_keys.slice(0, keyInsertAt),
        equivKey,
        ...equivocation_keys.slice(keyInsertAt),
      ]
      newHashes = [
        ...equivocation_hashes.slice(0, keyInsertAt),
        msg.payload_hash,
        ...equivocation_hashes.slice(keyInsertAt),
      ]
    } else {
      newKeys = [...equivocation_keys]
      newHashes = [...equivocation_hashes]
    }

    const newState = deepFreeze<QueueState>({
      entries: newEntries,
      equivocation_keys: newKeys,
      equivocation_hashes: newHashes,
    })

    const result = deepFreeze<DeliveryResult>({
      message: msg,
      status: 'DELIVERED',
    })

    return [new DeterministicMessageQueue(newState), result]
  }

  /**
   * Drain all messages in deterministic (lexicographic message_id) order.
   * Returns [emptyQueue, messages].
   */
  drain(): [DeterministicMessageQueue, readonly ReplayMessage[]] {
    const messages = this._state.entries.map(e => e.message)
    const empty = DeterministicMessageQueue.create()
    return [empty, Object.freeze(messages)]
  }
}

// ─── String binary search helpers ─────────────────────────

function binarySearchString(arr: readonly string[], target: string): number {
  let lo = 0
  let hi = arr.length - 1
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1
    const v = arr[mid]
    /* c8 ignore next -- noUncheckedIndexedAccess; binary search guarantees mid < arr.length */
    if (v === undefined) break
    if (v === target) return mid
    if (v < target) lo = mid + 1
    else hi = mid - 1
  }
  return -1
}

function findStringInsertionIndex(arr: readonly string[], target: string): number {
  let lo = 0
  let hi = arr.length
  while (lo < hi) {
    const mid = (lo + hi) >>> 1
    const v = arr[mid]
    /* c8 ignore next -- noUncheckedIndexedAccess; binary search guarantees mid < arr.length */
    if (v === undefined) break
    if (v < target) lo = mid + 1
    else hi = mid
  }
  return lo
}
