// ============================================================
// SOVEREIGN OMEGA — EpochSeal tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import { sealEpoch, verifyEpochSeal, EpochSealError, EPOCH_SEAL_VERSION } from '../../src/ledger/epoch-seal.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import { assembleBlock } from '../../src/ledger/block.js'
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

describe('sealEpoch', () => {
  it('throws EpochSealError for negative epochNumber', async () => {
    const chain = await buildChain(3)
    await expect(sealEpoch(chain, -1, 0, 2)).rejects.toBeInstanceOf(EpochSealError)
  })

  it('throws EpochSealError for negative heights', async () => {
    const chain = await buildChain(3)
    await expect(sealEpoch(chain, 0, -1, 1)).rejects.toBeInstanceOf(EpochSealError)
  })

  it('throws EpochSealError when startHeight > endHeight', async () => {
    const chain = await buildChain(3)
    await expect(sealEpoch(chain, 0, 2, 0)).rejects.toBeInstanceOf(EpochSealError)
  })

  it('throws EpochSealError when endHeight out of chain range', async () => {
    const chain = await buildChain(3)
    await expect(sealEpoch(chain, 0, 0, 5)).rejects.toBeInstanceOf(EpochSealError)
  })

  it('single-block epoch — correct schema fields', async () => {
    const chain = await buildChain(1)
    const seal  = await sealEpoch(chain, 0, 0, 0)
    expect(seal.epoch_number).toBe(0)
    expect(seal.start_height).toBe(0)
    expect(seal.end_height).toBe(0)
    expect(seal.schema_version).toBe(EPOCH_SEAL_VERSION)
    expect(seal.is_replay_reconstructable).toBe(true)
  })

  it('final_state_root matches last block in range', async () => {
    const chain  = await buildChain(4)
    const blocks = chain.getAll()
    const seal   = await sealEpoch(chain, 0, 0, 2)
    expect(seal.final_state_root).toBe(blocks[2]!.state_root_after)
  })

  it('seal_hash is non-empty SHA256Hex (64 hex chars)', async () => {
    const chain = await buildChain(3)
    const seal  = await sealEpoch(chain, 0, 0, 2)
    expect(seal.seal_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(seal.seal_hash)).toBe(true)
  })

  it('mid-chain range seal — final_state_root matches mid block', async () => {
    const chain  = await buildChain(5)
    const blocks = chain.getAll()
    const seal   = await sealEpoch(chain, 1, 2, 4)
    expect(seal.final_state_root).toBe(blocks[4]!.state_root_after)
    expect(seal.epoch_number).toBe(1)
    expect(seal.start_height).toBe(2)
    expect(seal.end_height).toBe(4)
  })

  it('is deterministic — same chain and range produce identical seal', async () => {
    const [c1, c2] = await Promise.all([buildChain(4), buildChain(4)])
    const [s1, s2] = await Promise.all([
      sealEpoch(c1, 0, 0, 3),
      sealEpoch(c2, 0, 0, 3),
    ])
    expect(s1.seal_hash).toBe(s2.seal_hash)
    expect(s1.merkle_root).toBe(s2.merkle_root)
    expect(s1.final_state_root).toBe(s2.final_state_root)
  })

  it('different epoch ranges produce different seal_hashes', async () => {
    const chain = await buildChain(4)
    const [s1, s2] = await Promise.all([
      sealEpoch(chain, 0, 0, 1),
      sealEpoch(chain, 1, 2, 3),
    ])
    expect(s1.seal_hash).not.toBe(s2.seal_hash)
    expect(s1.merkle_root).not.toBe(s2.merkle_root)
  })
})

describe('verifyEpochSeal', () => {
  it('returns true for a valid seal', async () => {
    const chain = await buildChain(4)
    const seal  = await sealEpoch(chain, 0, 0, 3)
    expect(await verifyEpochSeal(seal, chain)).toBe(true)
  })

  it('returns false when seal_hash is tampered', async () => {
    const chain   = await buildChain(3)
    const seal    = await sealEpoch(chain, 0, 0, 2)
    const tampered = { ...seal, seal_hash: 'f'.repeat(64) as SHA256Hex }
    expect(await verifyEpochSeal(tampered, chain)).toBe(false)
  })

  it('returns false when merkle_root is tampered', async () => {
    const chain   = await buildChain(3)
    const seal    = await sealEpoch(chain, 0, 0, 2)
    const tampered = { ...seal, merkle_root: 'e'.repeat(64) as SHA256Hex }
    expect(await verifyEpochSeal(tampered, chain)).toBe(false)
  })

  it('returns false when final_state_root is tampered', async () => {
    const chain   = await buildChain(3)
    const seal    = await sealEpoch(chain, 0, 0, 2)
    const tampered = { ...seal, final_state_root: 'd'.repeat(64) as SHA256Hex }
    expect(await verifyEpochSeal(tampered, chain)).toBe(false)
  })

  it('returns false when endHeight exceeds chain length', async () => {
    const chain = await buildChain(3)
    const seal  = await sealEpoch(chain, 0, 0, 2)
    // Verify against a shorter chain
    const shortChain = (await buildChain(2))
    expect(await verifyEpochSeal(seal, shortChain)).toBe(false)
  })

  it('mid-chain seal verifies correctly', async () => {
    const chain = await buildChain(6)
    const seal  = await sealEpoch(chain, 1, 2, 4)
    expect(await verifyEpochSeal(seal, chain)).toBe(true)
  })
})
