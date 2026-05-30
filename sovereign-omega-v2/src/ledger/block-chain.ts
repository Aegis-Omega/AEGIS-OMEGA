// ============================================================
// SOVEREIGN OMEGA — BlockChain (ordered CommittedBlock sequence)
// EPISTEMIC TIER: T2 · distributed ledger precursor
//
// Immutable functional-update pattern (mirrors LedgerChain).
// append() enforces index monotonicity synchronously — fast and
// cheap. verifyAll() runs full cryptographic verifyBlock() across
// every adjacent pair — async, tamper-evident.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { type CommittedBlock, verifyBlock } from './block.js'

export class BlockChainError extends Error {
  override readonly name = 'BlockChainError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export class BlockChain {
  private readonly _blocks: readonly CommittedBlock[]
  /**
   * Index of the first block in this chain. 0 for full chains; N for
   * partial chains imported from a StateCapsule (epoch-anchored).
   */
  private readonly _offset: number

  private constructor(blocks: readonly CommittedBlock[], offset = 0) {
    this._blocks = blocks
    this._offset = offset
  }

  /** Empty full chain starting at genesis (index 0). */
  static empty(): BlockChain {
    return new BlockChain(deepFreeze([]), 0)
  }

  /**
   * Empty partial chain anchored at startIndex. Use this when importing
   * a StateCapsule that starts mid-sequence (e.g. post-epoch blocks).
   * append() will accept blocks beginning at startIndex.
   */
  static partial(startIndex: number): BlockChain {
    return new BlockChain(deepFreeze([]), startIndex)
  }

  /**
   * Append a block. Enforces strict index monotonicity: block.index must
   * equal offset + current length. Returns a new BlockChain; does not mutate.
   * Throws BlockChainError on index violation.
   */
  append(block: CommittedBlock): BlockChain {
    const expectedIndex = this._offset + this._blocks.length
    if (block.index !== expectedIndex) {
      throw new BlockChainError(
        `Block index ${block.index} does not match expected ${expectedIndex}`,
      )
    }
    return new BlockChain(deepFreeze([...this._blocks, block]), this._offset)
  }

  /**
   * Full cryptographic verification of the chain.
   * For full chains (offset=0), the first block is verified against null
   * (genesis). For partial chains, the first block is verified against null
   * — this will fail if the first block is not a genesis block; callers
   * must use verifyStateCapsule() for partial-chain integrity.
   */
  async verifyAll(): Promise<boolean> {
    for (let i = 0; i < this._blocks.length; i++) {
      const block    = this._blocks[i]!
      const prevBlock = i === 0 ? null : (this._blocks[i - 1] ?? null)
      const valid    = await verifyBlock(block, prevBlock)
      if (!valid) return false
    }
    return true
  }

  /** All committed blocks in append order. Frozen. */
  getAll(): readonly CommittedBlock[] { return this._blocks }

  /** Most recently appended block, or null if the chain is empty. */
  get lastBlock(): CommittedBlock | null {
    /* c8 ignore next -- noUncheckedIndexedAccess artifact */
    return this._blocks.length > 0
      ? (this._blocks[this._blocks.length - 1] ?? null)
      : null
  }

  /** Number of committed blocks in this chain (not counting offset). */
  get length(): number { return this._blocks.length }

  /** Index of the highest committed block, or offset-1 if empty. */
  get height(): number { return this._offset + this._blocks.length - 1 }

  /** First block index expected by append() — 0 for full chains. */
  get offset(): number { return this._offset }
}
