// ============================================================
// SOVEREIGN OMEGA — EventBridge (LedgerChain → BlockChain)
// EPISTEMIC TIER: T2 · distributed ledger precursor
//
// bridgeToBlockChain() converts an append-only LedgerChain of
// individual governance events into a BlockChain of CommittedBlocks.
// Each block contains exactly `batchSize` entries (last block may
// contain fewer). Empty chain → empty BlockChain.
// Pure function of its inputs — deterministic, no side effects.
// ============================================================

import { type LedgerChain } from './chain.js'
import { assembleBlock, type CommittedBlock } from './block.js'
import { BlockChain } from './block-chain.js'

export class EventBridgeError extends Error {
  override readonly name = 'EventBridgeError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface BridgeResult {
  readonly blockChain: BlockChain
  /** Total entries processed. */
  readonly entry_count: number
  /** Number of blocks assembled. */
  readonly block_count: number
  /** Entries in the final (possibly partial) block. */
  readonly last_batch_size: number
}

// ─── Public API ────────────────────────────────────────────

/**
 * Convert a LedgerChain into a BlockChain by batching entries.
 * batchSize must be >= 1. Empty chain produces an empty BlockChain.
 * Throws EventBridgeError for invalid batchSize.
 */
export async function bridgeToBlockChain(
  chain: LedgerChain,
  batchSize: number,
): Promise<BridgeResult> {
  if (!Number.isInteger(batchSize) || batchSize < 1) {
    throw new EventBridgeError(`batchSize must be a positive integer (got ${batchSize})`)
  }

  const entries = chain.getAll()
  if (entries.length === 0) {
    return {
      blockChain:      BlockChain.empty(),
      entry_count:     0,
      block_count:     0,
      last_batch_size: 0,
    }
  }

  let blockChain: BlockChain    = BlockChain.empty()
  let prevBlock: CommittedBlock | null = null
  let lastBatchSize              = 0

  for (let offset = 0; offset < entries.length; offset += batchSize) {
    const batch  = entries.slice(offset, offset + batchSize)
    const block  = await assembleBlock(prevBlock, batch)
    blockChain   = blockChain.append(block)
    prevBlock    = block
    lastBatchSize = batch.length
  }

  return {
    blockChain,
    entry_count:     entries.length,
    block_count:     blockChain.length,
    last_batch_size: lastBatchSize,
  }
}
