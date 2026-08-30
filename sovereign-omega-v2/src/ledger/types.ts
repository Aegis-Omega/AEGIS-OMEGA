// ============================================================
// SOVEREIGN OMEGA — Merkle Replay Ledger Types
// EPISTEMIC TIER: T0 · Gate 17
//
// The LedgerEntry is the fundamental unit of the constitutional
// replay chain. Each entry is cryptographically linked to its
// predecessor via previous_hash, forming an append-only merkle
// chain verifiable without trusted state.
//
// timestamp_ms: MUST be injected from E5 event substrate.
// Never use Date.now() — this field is E5-sourced, not ambient.
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'

export const LEDGER_SCHEMA_VERSION = '1.0.0' as const

/** Zero-hash used for the first entry's previous_hash (genesis anchor). */
export const GENESIS_HASH: SHA256Hex = '0'.repeat(64) as SHA256Hex

// ─── Primary types ─────────────────────────────────────────

/**
 * One committed frame's ledger record.
 * Forms a cryptographic hash chain: entry[n].previous_hash = hash(entry[n-1]).
 */
export interface LedgerEntry {
  readonly sequence: SequenceNumber
  /** Hash of the previous LedgerEntry; GENESIS_HASH for the first entry. */
  readonly previous_hash: SHA256Hex
  /** SHA-256 of the FrameExecutionResult for this sequence. */
  readonly frame_hash: SHA256Hex
  /** SHA-256 of the GovernanceDecision emitted in this frame. */
  readonly governance_hash: SHA256Hex
  /** Frame wall-clock timestamp sourced from E5 event — never Date.now(). */
  readonly timestamp_ms: number
}

/**
 * Immutable point-in-time snapshot of the ledger chain.
 * merkle_root covers all entries in order.
 */
export interface LedgerSnapshot {
  readonly entries: readonly LedgerEntry[]
  readonly merkle_root: SHA256Hex
  readonly snapshot_sequence: SequenceNumber
  readonly entry_count: number
  readonly schema_version: typeof LEDGER_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

// ─── Error ─────────────────────────────────────────────────

export class LedgerConstraintError extends Error {
  constructor(msg: string) {
    super(msg)
    this.name = 'LedgerConstraintError'
  }
}
