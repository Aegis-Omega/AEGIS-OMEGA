// ============================================================
// SOVEREIGN OMEGA — LedgerChain Replay Integrity Verifier
// EPISTEMIC TIER: T0 · Gate 17
//
// verifyChain() performs full cryptographic verification of an
// ordered LedgerEntry slice: sequence monotonicity + hash chain.
// Pure function of its inputs — same entries always same result.
// ============================================================

import { hashValue } from '../core/hashing.js'
import type { SequenceNumber, SHA256Hex } from '../core/types.js'
import { type LedgerEntry, GENESIS_HASH } from './types.js'

// ─── Result type ───────────────────────────────────────────

export interface ChainVerificationResult {
  readonly valid: boolean
  readonly verified_entries: number
  /** Sequence number of the first invalid entry, if any. */
  readonly failed_at_sequence?: SequenceNumber
  readonly reason?: string
}

// ─── Verify ────────────────────────────────────────────────

/**
 * Verify a slice of LedgerEntries forms a valid hash chain.
 *
 * Checks:
 *   1. Sequence numbers are strictly monotonically increasing.
 *   2. entry[i].previous_hash === hash(entry[i-1]) for i > 0.
 *   3. entry[0].previous_hash === GENESIS_HASH.
 *
 * Pure function — no side effects.
 */
export async function verifyChain(
  entries: readonly LedgerEntry[],
): Promise<ChainVerificationResult> {
  if (entries.length === 0) {
    return { valid: true, verified_entries: 0 }
  }

  // Genesis anchor: first entry's previous_hash must be the zero hash
  const first = entries[0]!
  if (first.previous_hash !== GENESIS_HASH) {
    return {
      valid: false,
      verified_entries: 0,
      failed_at_sequence: first.sequence,
      reason: `first entry previous_hash must equal GENESIS_HASH`,
    }
  }

  let expectedPreviousHash: SHA256Hex = GENESIS_HASH

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]!

    // 1. Sequence monotonicity
    if (i > 0) {
      const prev = entries[i - 1]!
      if (entry.sequence <= prev.sequence) {
        return {
          valid: false,
          verified_entries: i,
          failed_at_sequence: entry.sequence,
          reason: `sequence ${entry.sequence} not strictly after ${prev.sequence}`,
        }
      }
    }

    // 2. Hash chain integrity
    if (entry.previous_hash !== expectedPreviousHash) {
      return {
        valid: false,
        verified_entries: i,
        failed_at_sequence: entry.sequence,
        reason: `hash chain broken at sequence ${entry.sequence}`,
      }
    }

    // Compute this entry's hash to use as expectedPreviousHash for the next
    expectedPreviousHash = await hashValue(entry)
  }

  return { valid: true, verified_entries: entries.length }
}

/**
 * Quick structural-only check (no cryptography) — validates sequence
 * monotonicity only. O(n), synchronous. Use for fast pre-flight checks.
 */
export function verifySequences(entries: readonly LedgerEntry[]): ChainVerificationResult {
  for (let i = 1; i < entries.length; i++) {
    const curr = entries[i]!
    const prev = entries[i - 1]!
    if (curr.sequence <= prev.sequence) {
      return {
        valid: false,
        verified_entries: i,
        failed_at_sequence: curr.sequence,
        reason: `sequence ${curr.sequence} not strictly after ${prev.sequence}`,
      }
    }
  }
  return { valid: true, verified_entries: entries.length }
}
