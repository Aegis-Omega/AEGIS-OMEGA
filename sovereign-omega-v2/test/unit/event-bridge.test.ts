// ============================================================
// SOVEREIGN OMEGA — EventBridge tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import { bridgeToBlockChain, EventBridgeError } from '../../src/ledger/event-bridge.js'
import { replayChain } from '../../src/ledger/block-replay.js'
import { LedgerChain } from '../../src/ledger/chain.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

const EPOCH_BASE = 1_600_000_000_000

function makeEntry(seq: number): LedgerEntry {
  return Object.freeze<LedgerEntry>({
    sequence:        BigInt(seq) as SequenceNumber,
    previous_hash:   GENESIS_HASH,
    frame_hash:      ('a'.repeat(64)) as SHA256Hex,
    governance_hash: ('b'.repeat(64)) as SHA256Hex,
    timestamp_ms:    EPOCH_BASE + seq * 1_000,
  })
}

function chainOf(count: number): LedgerChain {
  let c = LedgerChain.empty()
  for (let i = 0; i < count; i++) c = c.append(makeEntry(i))
  return c
}

describe('bridgeToBlockChain', () => {
  it('throws EventBridgeError for batchSize = 0', async () => {
    await expect(bridgeToBlockChain(LedgerChain.empty(), 0)).rejects.toBeInstanceOf(EventBridgeError)
  })

  it('throws EventBridgeError for negative batchSize', async () => {
    await expect(bridgeToBlockChain(LedgerChain.empty(), -3)).rejects.toBeInstanceOf(EventBridgeError)
  })

  it('throws EventBridgeError for non-integer batchSize', async () => {
    await expect(bridgeToBlockChain(LedgerChain.empty(), 1.5)).rejects.toBeInstanceOf(EventBridgeError)
  })

  it('empty chain → empty BlockChain, zero counts', async () => {
    const result = await bridgeToBlockChain(LedgerChain.empty(), 3)
    expect(result.blockChain.length).toBe(0)
    expect(result.entry_count).toBe(0)
    expect(result.block_count).toBe(0)
    expect(result.last_batch_size).toBe(0)
  })

  it('batchSize=1 → one block per entry', async () => {
    const chain  = chainOf(5)
    const result = await bridgeToBlockChain(chain, 1)
    expect(result.block_count).toBe(5)
    expect(result.entry_count).toBe(5)
    expect(result.last_batch_size).toBe(1)
  })

  it('batchSize larger than entry count → single block', async () => {
    const chain  = chainOf(3)
    const result = await bridgeToBlockChain(chain, 10)
    expect(result.block_count).toBe(1)
    expect(result.last_batch_size).toBe(3)
  })

  it('entries exactly divisible by batchSize → no remainder block', async () => {
    const chain  = chainOf(6)
    const result = await bridgeToBlockChain(chain, 2)
    expect(result.block_count).toBe(3)
    expect(result.last_batch_size).toBe(2)
  })

  it('remainder entries go into a final partial block', async () => {
    const chain  = chainOf(7)
    const result = await bridgeToBlockChain(chain, 3)
    // 3+3+1 → 3 blocks; last block has 1 entry
    expect(result.block_count).toBe(3)
    expect(result.last_batch_size).toBe(1)
    expect(result.entry_count).toBe(7)
  })

  it('resulting BlockChain passes verifyAll()', async () => {
    const chain  = chainOf(5)
    const result = await bridgeToBlockChain(chain, 2)
    expect(await result.blockChain.verifyAll()).toBe(true)
  })

  it('resulting BlockChain passes BlockReplay', async () => {
    const chain  = chainOf(6)
    const result = await bridgeToBlockChain(chain, 2)
    const replay = await replayChain(result.blockChain)
    expect(replay.is_valid).toBe(true)
    expect(replay.block_count).toBe(3)
    expect(replay.state_trace).toHaveLength(3)
  })

  it('is deterministic — same LedgerChain and batchSize produce identical lastBlock', async () => {
    const chain = chainOf(4)
    const [r1, r2, r3] = await Promise.all([
      bridgeToBlockChain(chain, 2),
      bridgeToBlockChain(chain, 2),
      bridgeToBlockChain(chain, 2),
    ])
    const root = (r: typeof r1) => r.blockChain.lastBlock!.state_root_after
    expect(root(r1)).toBe(root(r2))
    expect(root(r2)).toBe(root(r3))
  })

  it('different batchSizes produce different block structures', async () => {
    const chain = chainOf(6)
    const [r2, r3] = await Promise.all([
      bridgeToBlockChain(chain, 2),
      bridgeToBlockChain(chain, 3),
    ])
    // Block counts differ
    expect(r2.block_count).toBe(3)
    expect(r3.block_count).toBe(2)
    // State roots differ because block boundaries differ
    expect(r2.blockChain.lastBlock!.state_root_after).not.toBe(
      r3.blockChain.lastBlock!.state_root_after,
    )
  })
})
