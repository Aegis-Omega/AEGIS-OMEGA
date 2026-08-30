// ============================================================
// SOVEREIGN OMEGA — EpochSeal (block-range finalization)
// EPISTEMIC TIER: T2 · distributed ledger precursor
//
// sealEpoch() produces a compact, tamper-evident commitment over a
// contiguous range of CommittedBlocks. New nodes can start replay from
// an epoch boundary (O(1) verification) rather than from genesis (O(n)).
// seal_hash = SHA-256({epoch_number, start_height, end_height,
//                       final_state_root, merkle_root}).
// verifyEpochSeal() re-derives all fields from the chain.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue, computeMerkleRootFromValues } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { BlockChain } from './block-chain.js'

export const EPOCH_SEAL_VERSION = '1.0.0' as const

export class EpochSealError extends Error {
  override readonly name = 'EpochSealError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface EpochSeal {
  /** Monotonically increasing epoch counter, starting at 0. */
  readonly epoch_number: number
  /** Index of the first block in this epoch (inclusive). */
  readonly start_height: number
  /** Index of the last block in this epoch (inclusive). */
  readonly end_height: number
  /** state_root_after of the last block in the epoch — anchor for next epoch. */
  readonly final_state_root: SHA256Hex
  /** Merkle root of ordered state_root_after values across all blocks in range. */
  readonly merkle_root: SHA256Hex
  /** SHA-256({epoch_number, start_height, end_height, final_state_root, merkle_root}) */
  readonly seal_hash: SHA256Hex
  readonly schema_version: typeof EPOCH_SEAL_VERSION
  readonly is_replay_reconstructable: true
}

// ─── Public API ────────────────────────────────────────────

/**
 * Seal a contiguous range of blocks [startHeight, endHeight] as an epoch.
 * Throws EpochSealError if:
 *   - epochNumber < 0
 *   - startHeight > endHeight
 *   - startHeight or endHeight out of chain bounds
 */
export async function sealEpoch(
  chain: BlockChain,
  epochNumber: number,
  startHeight: number,
  endHeight: number,
): Promise<EpochSeal> {
  if (epochNumber < 0) {
    throw new EpochSealError(`epochNumber must be >= 0 (got ${epochNumber})`)
  }
  if (startHeight < 0 || endHeight < 0) {
    throw new EpochSealError(`Heights must be non-negative (got ${startHeight}..${endHeight})`)
  }
  if (startHeight > endHeight) {
    throw new EpochSealError(`startHeight ${startHeight} exceeds endHeight ${endHeight}`)
  }

  const blocks = chain.getAll()
  if (endHeight >= blocks.length) {
    throw new EpochSealError(
      `endHeight ${endHeight} out of range (chain length ${blocks.length})`,
    )
  }

  const slice = blocks.slice(startHeight, endHeight + 1)
  const stateRoots = slice.map(b => b.state_root_after)

  const merkle_root      = await computeMerkleRootFromValues(stateRoots as readonly unknown[])
  const final_state_root = stateRoots[stateRoots.length - 1]!
  const seal_hash        = await hashValue({
    epoch_number: epochNumber,
    start_height: startHeight,
    end_height:   endHeight,
    final_state_root,
    merkle_root,
  })

  return deepFreeze<EpochSeal>({
    epoch_number:        epochNumber,
    start_height:        startHeight,
    end_height:          endHeight,
    final_state_root,
    merkle_root,
    seal_hash,
    schema_version:      EPOCH_SEAL_VERSION,
    is_replay_reconstructable: true,
  })
}

/**
 * Verify an EpochSeal against the chain. Re-derives merkle_root,
 * final_state_root, and seal_hash from the chain; returns false on any mismatch.
 */
export async function verifyEpochSeal(seal: EpochSeal, chain: BlockChain): Promise<boolean> {
  const blocks = chain.getAll()
  if (seal.end_height >= blocks.length) return false
  if (seal.start_height > seal.end_height) return false

  const slice      = blocks.slice(seal.start_height, seal.end_height + 1)
  const stateRoots = slice.map(b => b.state_root_after)

  const expectedMerkle = await computeMerkleRootFromValues(stateRoots as readonly unknown[])
  if (seal.merkle_root !== expectedMerkle) return false

  const expectedFinal = stateRoots[stateRoots.length - 1]!
  if (seal.final_state_root !== expectedFinal) return false

  const expectedSealHash = await hashValue({
    epoch_number:    seal.epoch_number,
    start_height:    seal.start_height,
    end_height:      seal.end_height,
    final_state_root: seal.final_state_root,
    merkle_root:     seal.merkle_root,
  })
  return seal.seal_hash === expectedSealHash
}
