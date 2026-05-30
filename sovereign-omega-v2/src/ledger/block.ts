// ============================================================
// SOVEREIGN OMEGA — CommittedBlock (distributed ledger precursor)
// EPISTEMIC TIER: T2 · engineering precursor to multi-node replication.
//
// Tendermint-shaped block header over a batch of LedgerEntries.
// Each block carries state_root_before/after (Merkle over transactions)
// and deterministic BFT validator commitments — all re-derivable from
// inputs alone, making every block replay-reconstructable.
//
// Physical multi-node consensus is not wired here; the block shape is
// correct and verifiable on a single node today. Replication adds the
// transport layer; this module owns the cryptographic invariants.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue, computeMerkleRootFromValues } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import { GENESIS_HASH, type LedgerEntry } from './types.js'

export const BLOCK_SCHEMA_VERSION = '1.0.0' as const

// BFT agents with constitutional vote weights (out of 1000, summing to 1000).
// Weights mirror the swarm constants: coordinator φ-scaled, auditor + implementer
// each occupy the 1/φ² complement.
const VALIDATORS = [
  { id: 'coordinator', weight: 618 },
  { id: 'auditor',     weight: 191 },
  { id: 'implementer', weight: 191 },
] as const

export type ValidatorId = (typeof VALIDATORS)[number]['id']

/** Deterministic commitment: SHA-256({validator_id, state_root_after, weight}). */
export interface ValidatorSignature {
  readonly validator_id: ValidatorId
  readonly weight: number
  readonly commitment: SHA256Hex
}

/**
 * CommittedBlock — Tendermint-shaped block over a batch of LedgerEntries.
 * Fields are deterministically derivable; verifyBlock() re-derives all hashes.
 */
export interface CommittedBlock {
  readonly index: number
  /** Hash of the previous block's {index, state_root_after}. GENESIS_HASH for index 0. */
  readonly prev_hash: SHA256Hex
  /** Cumulative state root before this block's transactions. GENESIS_HASH for index 0. */
  readonly state_root_before: SHA256Hex
  /** Merkle root over [state_root_before, ...transactions]. */
  readonly state_root_after: SHA256Hex
  readonly transactions: readonly LedgerEntry[]
  readonly validator_signatures: readonly ValidatorSignature[]
  readonly schema_version: typeof BLOCK_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class BlockError extends Error {
  override readonly name = 'BlockError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

// ─── Internal helpers ──────────────────────────────────────

function prevHashOf(b: CommittedBlock): Promise<SHA256Hex> {
  return hashValue({ index: b.index, state_root_after: b.state_root_after })
}

function deriveStateRootAfter(
  state_root_before: SHA256Hex,
  txs: readonly LedgerEntry[],
): Promise<SHA256Hex> {
  return computeMerkleRootFromValues([state_root_before, ...txs] as readonly unknown[])
}

async function deriveSignatures(state_root_after: SHA256Hex): Promise<readonly ValidatorSignature[]> {
  return Promise.all(
    VALIDATORS.map(async v =>
      deepFreeze<ValidatorSignature>({
        validator_id: v.id,
        weight: v.weight,
        commitment: await hashValue({ validator_id: v.id, state_root_after, weight: v.weight }),
      })
    ),
  )
}

// ─── Public API ────────────────────────────────────────────

/**
 * Assemble a CommittedBlock from pending ledger entries.
 * prevBlock=null produces the genesis block (index 0).
 * Throws BlockError if entries is empty.
 */
export async function assembleBlock(
  prevBlock: CommittedBlock | null,
  entries: readonly LedgerEntry[],
): Promise<CommittedBlock> {
  if (entries.length === 0) throw new BlockError('Cannot assemble block with no transactions')

  const index             = prevBlock === null ? 0 : prevBlock.index + 1
  const prev_hash         = prevBlock === null ? GENESIS_HASH : await prevHashOf(prevBlock)
  const state_root_before = prevBlock === null ? GENESIS_HASH : prevBlock.state_root_after
  const state_root_after  = await deriveStateRootAfter(state_root_before, entries)
  const validator_signatures = await deriveSignatures(state_root_after)

  return deepFreeze<CommittedBlock>({
    index,
    prev_hash,
    state_root_before,
    state_root_after,
    transactions: deepFreeze([...entries]),
    validator_signatures,
    schema_version: BLOCK_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

/**
 * Re-derive all hashes from scratch and compare against the stored block.
 * Returns false on any chain linkage or signature mismatch — tamper-evident.
 * prevBlock=null expects index===0 and GENESIS_HASH prev_hash/state_root_before.
 */
export async function verifyBlock(
  block: CommittedBlock,
  prevBlock: CommittedBlock | null,
): Promise<boolean> {
  const expectedPrevHash         = prevBlock === null ? GENESIS_HASH : await prevHashOf(prevBlock)
  const expectedStateRootBefore  = prevBlock === null ? GENESIS_HASH : prevBlock.state_root_after

  if (block.prev_hash        !== expectedPrevHash)        return false
  if (block.state_root_before !== expectedStateRootBefore) return false

  const expectedStateRootAfter = await deriveStateRootAfter(block.state_root_before, block.transactions)
  if (block.state_root_after !== expectedStateRootAfter) return false

  const expectedSigs = await deriveSignatures(block.state_root_after)
  for (let i = 0; i < expectedSigs.length; i++) {
    if (block.validator_signatures[i]?.commitment !== expectedSigs[i]?.commitment) return false
  }

  return true
}
