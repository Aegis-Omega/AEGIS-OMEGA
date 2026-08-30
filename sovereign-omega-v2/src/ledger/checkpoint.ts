// ============================================================
// SOVEREIGN OMEGA — LedgerChain Checkpoint Capture
// EPISTEMIC TIER: T0 · Gate 17
//
// captureCheckpoint() produces a frozen LedgerSnapshot with a
// Merkle root covering all entries in sequence order.
// The merkle_root is byte-identical to the Rust WASM
// merkle_root function for the same entry set (via JCS + SHA-256).
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { computeMerkleRootFromValues, sha256Hex } from '../core/hashing.js'
import type { SequenceNumber } from '../core/types.js'
import { type LedgerSnapshot, LEDGER_SCHEMA_VERSION } from './types.js'
import type { LedgerChain } from './chain.js'

/**
 * Capture an immutable snapshot of the ledger chain at its current state.
 * The merkle_root covers all entries in order, using JCS → SHA-256 per leaf.
 * Deterministic: same chain state always produces the same snapshot.
 */
export async function captureCheckpoint(chain: LedgerChain): Promise<Readonly<LedgerSnapshot>> {
  const entries = chain.getAll()

  const merkle_root = entries.length > 0
    ? await computeMerkleRootFromValues([...entries])
    : await sha256Hex(new Uint8Array(0))  // empty chain: SHA-256 of empty bytes

  const snapshot_sequence: SequenceNumber = entries.length > 0
    ? (entries[entries.length - 1]!.sequence)
    : (0n as SequenceNumber)

  return deepFreeze<LedgerSnapshot>({
    entries: Object.freeze([...entries]),
    merkle_root,
    snapshot_sequence,
    entry_count: entries.length,
    schema_version: LEDGER_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}
