// ============================================================
// SOVEREIGN OMEGA — BlockChain tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import { BlockChain, BlockChainError } from '../../src/ledger/block-chain.js'
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

async function makeBlock(prevBlock: Awaited<ReturnType<typeof assembleBlock>> | null, seq: number) {
  return assembleBlock(prevBlock, [makeEntry(seq)])
}

describe('BlockChain', () => {
  it('starts empty with height -1 and length 0', () => {
    const chain = BlockChain.empty()
    expect(chain.length).toBe(0)
    expect(chain.height).toBe(-1)
    expect(chain.lastBlock).toBeNull()
    expect(chain.getAll()).toHaveLength(0)
  })

  it('append returns a new chain without mutating the original', async () => {
    const chain = BlockChain.empty()
    const block0 = await makeBlock(null, 0)
    const chain1 = chain.append(block0)
    expect(chain.length).toBe(0)
    expect(chain1.length).toBe(1)
  })

  it('append enforces index monotonicity', async () => {
    const block0 = await makeBlock(null, 0)
    const block1 = await makeBlock(block0, 1)
    const chain  = BlockChain.empty().append(block0)
    // block1 has index 1 — correct
    const chain2 = chain.append(block1)
    expect(chain2.length).toBe(2)
    // Re-appending block0 (index 0) to a chain expecting index 2 must throw
    expect(() => chain2.append(block0)).toThrow(BlockChainError)
  })

  it('lastBlock tracks the most recently appended block', async () => {
    const block0 = await makeBlock(null, 0)
    const block1 = await makeBlock(block0, 1)
    const chain  = BlockChain.empty().append(block0).append(block1)
    expect(chain.lastBlock?.index).toBe(1)
    expect(chain.height).toBe(1)
  })

  it('verifyAll returns true for a valid chain', async () => {
    const block0 = await makeBlock(null, 0)
    const block1 = await makeBlock(block0, 1)
    const block2 = await makeBlock(block1, 2)
    const chain  = BlockChain.empty().append(block0).append(block1).append(block2)
    expect(await chain.verifyAll()).toBe(true)
  })

  it('verifyAll returns true for an empty chain', async () => {
    expect(await BlockChain.empty().verifyAll()).toBe(true)
  })

  it('verifyAll returns false when a block state_root_after is tampered', async () => {
    const block0 = await makeBlock(null, 0)
    const tampered = { ...block0, state_root_after: 'f'.repeat(64) as SHA256Hex }
    const chain  = BlockChain.empty().append(tampered)
    expect(await chain.verifyAll()).toBe(false)
  })

  it('is deterministic — three identical chains produce the same lastBlock state_root', async () => {
    async function buildChain() {
      const b0 = await makeBlock(null, 0)
      const b1 = await makeBlock(b0, 1)
      return BlockChain.empty().append(b0).append(b1)
    }
    const [c1, c2, c3] = await Promise.all([buildChain(), buildChain(), buildChain()])
    expect(c1.lastBlock!.state_root_after).toBe(c2.lastBlock!.state_root_after)
    expect(c2.lastBlock!.state_root_after).toBe(c3.lastBlock!.state_root_after)
  })
})
