// ============================================================
// SOVEREIGN OMEGA — LedgerEntry G-Set CRDT
// EPISTEMIC TIER: T2 · Gate 20
//
// Models ledger entries as a grow-only set (G-Set) keyed by
// sequence number. join(A, B) = union of both entry sets.
// Invariant: same sequence number must have identical content
// in both sets — any deviation signals tampering and throws
// CRDTConflictError. The join is commutative, associative,
// and idempotent for conflict-free inputs.
// ============================================================

import { canonicalizeJCS } from '../core/canonicalize.js'
import { uint8ArrayToHex } from '../core/hashing.js'
import { CRDTConflictError } from './types.js'
import type { LedgerEntry } from '../ledger/types.js'

// ─── Fingerprint ───────────────────────────────────────────

/** Synchronous JCS fingerprint for conflict detection (no crypto — just string comparison). */
function fingerprintEntry(entry: LedgerEntry): string {
  return uint8ArrayToHex(canonicalizeJCS(entry))
}

// ─── Join ──────────────────────────────────────────────────

/**
 * G-Set join for LedgerEntry arrays.
 *
 * Returns the sorted union of both inputs.
 * If the same sequence number appears in both with different content,
 * throws CRDTConflictError — this indicates a hash-chain fork (tampering).
 *
 * Commutative, associative, idempotent (for conflict-free inputs).
 */
export function joinLedgerEntries(
  a: readonly LedgerEntry[],
  b: readonly LedgerEntry[],
): readonly LedgerEntry[] {
  const bySeq = new Map<bigint, { entry: LedgerEntry; fingerprint: string }>()

  for (const entry of a) {
    bySeq.set(entry.sequence, { entry, fingerprint: fingerprintEntry(entry) })
  }

  for (const entry of b) {
    const existing = bySeq.get(entry.sequence)
    const fp = fingerprintEntry(entry)

    if (existing !== undefined) {
      if (existing.fingerprint !== fp) {
        throw new CRDTConflictError(
          `LedgerEntry conflict at sequence ${entry.sequence}: ` +
          `hash-chain fork detected — entries are not byte-identical`,
        )
      }
      // Identical entry already present — idempotent, skip
      continue
    }

    bySeq.set(entry.sequence, { entry, fingerprint: fp })
  }

  // Sort by sequence ascending
  const sorted = [...bySeq.values()]
    .sort((x, y) => (x.entry.sequence < y.entry.sequence ? -1 : 1))  // sequences are unique bigints; equality impossible
    .map(({ entry }) => entry)

  return Object.freeze(sorted)
}
