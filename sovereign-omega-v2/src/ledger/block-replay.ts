// ============================================================
// SOVEREIGN OMEGA — BlockReplay (deterministic state reconstruction)
// EPISTEMIC TIER: T2 · distributed ledger precursor
//
// replay(block_range) → deterministic reconstruction. Re-derives
// every block hash from scratch; any tampered block sets is_valid=false
// and records failed_at_index. Pure function of its inputs — identical
// block sequences produce identical ReplayResults across all nodes.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { GENESIS_HASH } from './types.js'
import { verifyBlock } from './block.js'
import type { CommittedBlock } from './block.js'
import type { BlockChain } from './block-chain.js'
import { deepFreeze } from '../core/immutable.js'

export class BlockReplayError extends Error {
  override readonly name = 'BlockReplayError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface ReplayResult {
  /** True iff every block in the replayed range verified successfully. */
  readonly is_valid: boolean
  /** Number of blocks visited (including the failing block if is_valid=false). */
  readonly block_count: number
  /**
   * State root after the last successfully verified block.
   * Equals GENESIS_HASH for an empty range; null only when block_count=0
   * AND all blocks failed (which means failed_at_index=0).
   * More precisely: state root after the last block with index < failed_at_index,
   * or GENESIS_HASH when no block succeeded.
   */
  readonly final_state_root: SHA256Hex
  /** Ordered state_root_after for every successfully verified block. */
  readonly state_trace: readonly SHA256Hex[]
  /** Index of the first block that failed verification (is_valid=false only). */
  readonly failed_at_index?: number
}

// ─── Public API ────────────────────────────────────────────

/**
 * Replay the full BlockChain from genesis, re-deriving every hash.
 * Returns a ReplayResult capturing state evolution across all blocks.
 */
export async function replayChain(chain: BlockChain): Promise<ReplayResult> {
  const blocks = chain.getAll()
  return _replayBlocks(blocks)
}

/**
 * Replay a contiguous sub-range [fromIndex, toIndex] (inclusive) of the chain.
 * Throws BlockReplayError for invalid index ranges.
 * Note: fromIndex must be 0 when the range starts at genesis; replaying a
 * mid-chain slice starting at fromIndex > 0 begins from GENESIS_HASH as
 * prev-block context — callers are responsible for providing the right anchor.
 */
export async function replayRange(
  chain: BlockChain,
  fromIndex: number,
  toIndex: number,
): Promise<ReplayResult> {
  const blocks = chain.getAll()

  if (fromIndex < 0 || toIndex < 0) {
    throw new BlockReplayError(`Indices must be non-negative (got ${fromIndex}..${toIndex})`)
  }
  if (fromIndex > toIndex) {
    throw new BlockReplayError(`fromIndex ${fromIndex} exceeds toIndex ${toIndex}`)
  }
  if (toIndex >= blocks.length) {
    throw new BlockReplayError(
      `toIndex ${toIndex} out of range (chain length ${blocks.length})`,
    )
  }

  const slice = blocks.slice(fromIndex, toIndex + 1)
  // Provide the real previous block as context when replaying a mid-chain slice
  const prevBlock = fromIndex === 0 ? null : (blocks[fromIndex - 1] ?? null)
  return _replayBlocks(slice, prevBlock)
}

// ─── Internal ──────────────────────────────────────────────

async function _replayBlocks(
  blocks: readonly CommittedBlock[],
  firstPrevBlock: CommittedBlock | null = null,
): Promise<ReplayResult> {
  const stateTrace: SHA256Hex[] = []
  let lastGoodRoot: SHA256Hex = firstPrevBlock?.state_root_after ?? GENESIS_HASH

  for (let i = 0; i < blocks.length; i++) {
    const block    = blocks[i]!
    const prevBlock = i === 0 ? firstPrevBlock : (blocks[i - 1] ?? null)
    const valid    = await verifyBlock(block, prevBlock)

    if (!valid) {
      return deepFreeze<ReplayResult>({
        is_valid: false,
        block_count: i + 1,
        final_state_root: lastGoodRoot,
        state_trace: deepFreeze(stateTrace),
        failed_at_index: block.index,
      })
    }

    lastGoodRoot = block.state_root_after
    stateTrace.push(block.state_root_after)
  }

  return deepFreeze<ReplayResult>({
    is_valid: true,
    block_count: blocks.length,
    final_state_root: lastGoodRoot,
    state_trace: deepFreeze(stateTrace),
  })
}
