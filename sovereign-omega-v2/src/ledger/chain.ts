// ============================================================
// SOVEREIGN OMEGA — LedgerChain (append-only hash chain)
// EPISTEMIC TIER: T0 · Gate 17
//
// Immutable functional-update pattern (identical to MutationLedger).
// Sequence monotonicity enforced at append time.
// Hash-chain integrity verified by verifyChain() (async, separate).
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { SequenceNumber } from '../core/types.js'
import { type LedgerEntry, LedgerConstraintError } from './types.js'

export class LedgerChain {
  private readonly _entries: readonly LedgerEntry[]
  private readonly _lastSeq: SequenceNumber | null

  private constructor(
    entries: readonly LedgerEntry[],
    lastSeq: SequenceNumber | null,
  ) {
    this._entries = entries
    this._lastSeq = lastSeq
  }

  static empty(): LedgerChain {
    return new LedgerChain(deepFreeze([]), null)
  }

  /**
   * Append a new entry. Throws LedgerConstraintError if sequence is not
   * strictly greater than the last appended sequence.
   * Returns a new LedgerChain — does not mutate this instance.
   */
  append(entry: LedgerEntry): LedgerChain {
    if (this._lastSeq !== null && entry.sequence <= this._lastSeq) {
      throw new LedgerConstraintError(
        `Ledger sequence ${entry.sequence} must be > last sequence ${this._lastSeq}`
      )
    }
    return new LedgerChain(
      deepFreeze([...this._entries, deepFreeze(entry)]),
      entry.sequence,
    )
  }

  /** All entries in append order. Frozen. */
  getAll(): readonly LedgerEntry[] { return this._entries }

  /** Number of appended entries. */
  get length(): number { return this._entries.length }

  /** Sequence number of the most recently appended entry, or null if empty. */
  get lastSequence(): SequenceNumber | null { return this._lastSeq }

  /** Most recently appended entry, or null if empty. */
  get lastEntry(): Readonly<LedgerEntry> | null {
    /* c8 ignore next -- noUncheckedIndexedAccess artifact; length > 0 guard ensures element is defined */
    return this._entries.length > 0
      ? (this._entries[this._entries.length - 1] ?? null)
      : null
  }
}
