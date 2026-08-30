// ============================================================
// SOVEREIGN OMEGA — BlockReplay tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import { replayChain, replayRange, BlockReplayError } from '../../src/ledger/block-replay.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import { assembleBlock } from '../../src/ledger/block.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

const EPOCH_BASE = 1_600_000_000_000

function makeEntry(seq: number, prevHash: SHA256Hex = GENESIS_HASH): LedgerEntry {
  return Object.freeze<LedgerEntry>({
    sequence:        BigInt(seq) as SequenceNumber,
    previous_hash:   prevHash,
    frame_hash:      ('a'.repeat(64)) as SHA256Hex,
    governance_hash: ('b'.repeat(64)) as SHA256Hex,
    timestamp_ms:    EPOCH_BASE + seq * 1_000,
  })
}

async function buildChain(length: number): Promise<BlockChain> {
  let chain    = BlockChain.empty()
  let prevBlock = null
  for (let i = 0; i < length; i++) {
    const block = await assembleBlock(prevBlock, [makeEntry(i)])
    chain       = chain.append(block)
    prevBlock   = block
  }
  return chain
}

describe('replayChain', () => {
  it('empty chain → valid, 0 blocks, GENESIS_HASH final_state_root', async () => {
    const result = await replayChain(BlockChain.empty())
    expect(result.is_valid).toBe(true)
    expect(result.block_count).toBe(0)
    expect(result.final_state_root).toBe(GENESIS_HASH)
    expect(result.state_trace).toHaveLength(0)
    expect(result.failed_at_index).toBeUndefined()
  })

  it('single valid block → valid, state_root matches block', async () => {
    const block  = await assembleBlock(null, [makeEntry(0)])
    const chain  = BlockChain.empty().append(block)
    const result = await replayChain(chain)
    expect(result.is_valid).toBe(true)
    expect(result.block_count).toBe(1)
    expect(result.final_state_root).toBe(block.state_root_after)
    expect(result.state_trace).toHaveLength(1)
    expect(result.state_trace[0]).toBe(block.state_root_after)
  })

  it('multi-block chain → trace length equals block count', async () => {
    const chain  = await buildChain(4)
    const result = await replayChain(chain)
    expect(result.is_valid).toBe(true)
    expect(result.block_count).toBe(4)
    expect(result.state_trace).toHaveLength(4)
  })

  it('state_trace entries are ordered and match each block state_root_after', async () => {
    const chain  = await buildChain(3)
    const result = await replayChain(chain)
    const blocks = chain.getAll()
    expect(result.state_trace[0]).toBe(blocks[0]!.state_root_after)
    expect(result.state_trace[1]).toBe(blocks[1]!.state_root_after)
    expect(result.state_trace[2]).toBe(blocks[2]!.state_root_after)
  })

  it('tampered block → is_valid=false, failed_at_index set', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const tampered = { ...block1, state_root_after: 'f'.repeat(64) as SHA256Hex }
    const chain  = BlockChain.empty().append(block0).append(tampered)
    const result = await replayChain(chain)
    expect(result.is_valid).toBe(false)
    expect(result.failed_at_index).toBe(1)
    expect(result.block_count).toBe(2)
    // Only the first (good) block's root is in state_trace
    expect(result.state_trace).toHaveLength(1)
    expect(result.state_trace[0]).toBe(block0.state_root_after)
  })

  it('tampered genesis → is_valid=false, failed_at_index=0, GENESIS_HASH final_state_root', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const tampered = { ...block, state_root_after: 'e'.repeat(64) as SHA256Hex }
    const chain  = BlockChain.empty().append(tampered)
    const result = await replayChain(chain)
    expect(result.is_valid).toBe(false)
    expect(result.failed_at_index).toBe(0)
    expect(result.final_state_root).toBe(GENESIS_HASH)
    expect(result.state_trace).toHaveLength(0)
  })

  it('is deterministic — two identical chains produce identical ReplayResults', async () => {
    const [c1, c2] = await Promise.all([buildChain(3), buildChain(3)])
    const [r1, r2] = await Promise.all([replayChain(c1), replayChain(c2)])
    expect(r1.final_state_root).toBe(r2.final_state_root)
    expect(r1.state_trace).toEqual(r2.state_trace)
    expect(r1.is_valid).toBe(r2.is_valid)
  })
})

describe('replayRange', () => {
  it('full range [0, len-1] matches replayChain', async () => {
    const chain  = await buildChain(3)
    const full   = await replayChain(chain)
    const ranged = await replayRange(chain, 0, 2)
    expect(ranged.is_valid).toBe(true)
    expect(ranged.final_state_root).toBe(full.final_state_root)
    expect(ranged.state_trace).toEqual(full.state_trace)
  })

  it('mid-chain range [1, 2] verifies against correct prev context', async () => {
    const chain  = await buildChain(4)
    const result = await replayRange(chain, 1, 2)
    expect(result.is_valid).toBe(true)
    expect(result.block_count).toBe(2)
    expect(result.state_trace).toHaveLength(2)
    const blocks = chain.getAll()
    expect(result.state_trace[0]).toBe(blocks[1]!.state_root_after)
    expect(result.state_trace[1]).toBe(blocks[2]!.state_root_after)
  })

  it('single-block range works correctly', async () => {
    const chain  = await buildChain(3)
    const result = await replayRange(chain, 1, 1)
    expect(result.is_valid).toBe(true)
    expect(result.block_count).toBe(1)
    const blocks = chain.getAll()
    expect(result.final_state_root).toBe(blocks[1]!.state_root_after)
  })

  it('throws BlockReplayError when fromIndex > toIndex', async () => {
    const chain = await buildChain(3)
    await expect(replayRange(chain, 2, 1)).rejects.toBeInstanceOf(BlockReplayError)
  })

  it('throws BlockReplayError when toIndex out of range', async () => {
    const chain = await buildChain(3)
    await expect(replayRange(chain, 0, 5)).rejects.toBeInstanceOf(BlockReplayError)
  })

  it('throws BlockReplayError for negative indices', async () => {
    const chain = await buildChain(3)
    await expect(replayRange(chain, -1, 1)).rejects.toBeInstanceOf(BlockReplayError)
  })
})
