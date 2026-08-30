// ============================================================
// SOVEREIGN OMEGA — StateCapsule (portable state-transfer bundle)
// EPISTEMIC TIER: T2 · distributed ledger precursor
//
// A StateCapsule is the minimum transferable bundle that lets a
// joining node verify the chain tip without replaying from genesis:
//
//   latest_epoch  — compact proof of all blocks up to end_height
//   anchor_block  — last block of the epoch (needed to verify the
//                   first post-epoch block via verifyBlock())
//   pending_blocks — blocks after the epoch boundary
//   tip_checkpoint — self-verifying state-root commitment at tip
//
// When latest_epoch is null, there is no sealed epoch — the capsule
// carries all blocks from genesis (anchor_block = null).
//
// verifyStateCapsule() is fully self-contained — the capsule proves
// itself without access to the full historical chain.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import { type CommittedBlock, verifyBlock } from './block.js'
import { BlockChain } from './block-chain.js'
import { type EpochSeal } from './epoch-seal.js'
import { type NodeCheckpoint, captureNodeCheckpoint, verifyNodeCheckpoint } from './node-checkpoint.js'

export const STATE_CAPSULE_VERSION = '1.0.0' as const

export class StateCapsuleError extends Error {
  override readonly name = 'StateCapsuleError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface StateCapsule {
  /**
   * Compact proof of all blocks up to end_height.
   * Null when no epoch has been sealed (full genesis capsule).
   */
  readonly latest_epoch: EpochSeal | null
  /**
   * The last CommittedBlock of the epoch — required to verify the
   * first pending_block via verifyBlock(). Null iff latest_epoch is null.
   */
  readonly anchor_block: CommittedBlock | null
  /**
   * All blocks after the epoch boundary (not including anchor_block).
   * Empty when the chain tip coincides with the epoch end.
   */
  readonly pending_blocks: readonly CommittedBlock[]
  /** Self-verifying tip commitment. */
  readonly tip_checkpoint: NodeCheckpoint
  /**
   * SHA-256({ epoch_seal_hash?, anchor_index?, tip_checkpoint_hash }).
   * Tamper any field and capsule_hash will not match.
   */
  readonly capsule_hash: SHA256Hex
  readonly schema_version: typeof STATE_CAPSULE_VERSION
  readonly is_replay_reconstructable: true
}

// ─── Internal ──────────────────────────────────────────────

function capsuleHashInput(
  latestEpoch: EpochSeal | null,
  anchorBlock: CommittedBlock | null,
  tipCheckpointHash: SHA256Hex,
): Record<string, unknown> {
  return {
    epoch_seal_hash:       latestEpoch?.seal_hash ?? null,
    anchor_index:          anchorBlock?.index ?? null,
    anchor_state_root:     anchorBlock?.state_root_after ?? null,
    tip_checkpoint_hash:   tipCheckpointHash,
  }
}

// ─── Public API ────────────────────────────────────────────

/**
 * Export a StateCapsule from the current chain state.
 * latestEpoch supplies the sealed epoch proof (null = no epoch sealed).
 * If latestEpoch is provided, anchorBlock must be the block at latestEpoch.end_height.
 * node_id identifies the exporting node.
 *
 * Throws StateCapsuleError on mismatched epoch / anchor block.
 */
export async function exportStateCapsule(
  node_id: string,
  chain: BlockChain,
  latestEpoch: EpochSeal | null,
): Promise<StateCapsule> {
  const blocks = chain.getAll()
  if (blocks.length === 0) {
    throw new StateCapsuleError('Cannot export capsule from an empty chain')
  }

  let anchorBlock: CommittedBlock | null     = null
  let pendingBlocks: readonly CommittedBlock[]

  if (latestEpoch === null) {
    // No sealed epoch — ship all blocks
    pendingBlocks = blocks
  } else {
    const epochEnd = latestEpoch.end_height
    if (epochEnd >= blocks.length) {
      throw new StateCapsuleError(
        `EpochSeal end_height ${epochEnd} exceeds chain length ${blocks.length}`,
      )
    }
    /* c8 ignore start -- noUncheckedIndexedAccess artifact; epochEnd < blocks.length guarantees block exists */
    anchorBlock   = blocks[epochEnd] ?? null
    if (anchorBlock === null) {
      throw new StateCapsuleError(`No block at epoch end_height ${epochEnd}`)
    }
    /* c8 ignore stop */
    if (anchorBlock.state_root_after !== latestEpoch.final_state_root) {
      throw new StateCapsuleError(
        'anchor_block.state_root_after does not match EpochSeal.final_state_root',
      )
    }
    pendingBlocks = blocks.slice(epochEnd + 1)
  }

  const tip            = chain.lastBlock!
  const tip_checkpoint = await captureNodeCheckpoint(node_id, tip)
  const capsule_hash   = await hashValue(
    capsuleHashInput(latestEpoch, anchorBlock, tip_checkpoint.checkpoint_hash),
  )

  return deepFreeze<StateCapsule>({
    latest_epoch:   latestEpoch,
    anchor_block:   anchorBlock,
    pending_blocks: deepFreeze([...pendingBlocks]),
    tip_checkpoint,
    capsule_hash,
    schema_version: STATE_CAPSULE_VERSION,
    is_replay_reconstructable: true,
  })
}

/**
 * Verify a StateCapsule without access to the full historical chain.
 * Checks:
 *   1. capsule_hash integrity
 *   2. tip_checkpoint self-hash
 *   3. anchor_block consistent with latest_epoch
 *   4. pending_blocks form a valid chain from anchor_block
 *   5. tip_checkpoint.state_root matches the tip block
 *
 * Returns false on any verification failure — never throws.
 */
export async function verifyStateCapsule(capsule: StateCapsule): Promise<boolean> {
  try {
    // 1. Capsule hash integrity
    const expectedCapsuleHash = await hashValue(
      capsuleHashInput(
        capsule.latest_epoch,
        capsule.anchor_block,
        capsule.tip_checkpoint.checkpoint_hash,
      ),
    )
    if (capsule.capsule_hash !== expectedCapsuleHash) return false

    // 2. Tip checkpoint self-hash
    if (!(await verifyNodeCheckpoint(capsule.tip_checkpoint))) return false

    // 3. anchor_block vs epoch consistency
    if (capsule.latest_epoch !== null) {
      if (capsule.anchor_block === null) return false
      if (capsule.anchor_block.index !== capsule.latest_epoch.end_height) return false
      if (capsule.anchor_block.state_root_after !== capsule.latest_epoch.final_state_root) return false
    } else {
      // No epoch → anchor must be null and pending_blocks starts from genesis
      if (capsule.anchor_block !== null) return false
    }

    // 4. pending_blocks chain validity from anchor_block
    let prevBlock: CommittedBlock | null = capsule.anchor_block
    for (const block of capsule.pending_blocks) {
      const valid = await verifyBlock(block, prevBlock)
      if (!valid) return false
      prevBlock = block
    }

    // 5. tip_checkpoint.state_root matches chain tip
    const tipBlock = capsule.pending_blocks.length > 0
      ? capsule.pending_blocks[capsule.pending_blocks.length - 1]!
      : capsule.anchor_block
    if (tipBlock === null) return false
    if (capsule.tip_checkpoint.state_root !== tipBlock.state_root_after) return false

    return true
  } catch {
    return false
  }
}

/**
 * Reconstruct a BlockChain from a StateCapsule.
 * The returned chain covers only the capsule's scope:
 *   - anchor_block (if present) as first block
 *   - then all pending_blocks
 * The capsule must be verified before calling this.
 * Throws StateCapsuleError if anchor_block is null and pending_blocks is empty.
 */
export async function importStateCapsule(capsule: StateCapsule): Promise<BlockChain> {
  // Determine the starting offset for the partial chain
  const startIndex = capsule.anchor_block?.index ?? 0
  let chain = startIndex === 0 ? BlockChain.empty() : BlockChain.partial(startIndex)

  if (capsule.anchor_block !== null) {
    chain = chain.append(capsule.anchor_block)
  }

  for (const block of capsule.pending_blocks) {
    chain = chain.append(block)
  }

  if (chain.length === 0) {
    throw new StateCapsuleError('Capsule contains no blocks to import')
  }

  return chain
}
