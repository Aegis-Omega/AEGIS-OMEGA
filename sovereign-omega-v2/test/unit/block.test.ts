// ============================================================
// SOVEREIGN OMEGA — CommittedBlock tests
// EPISTEMIC TIER: T2 · Gate companion to ledger.test.ts
// ============================================================

import { describe, it, expect } from 'vitest'
import { assembleBlock, verifyBlock, BlockError, BLOCK_SCHEMA_VERSION } from '../../src/ledger/block.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

// Fixed timestamps derived from epoch constant — never Date.now().
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

describe('assembleBlock', () => {
  it('throws BlockError when entries is empty', async () => {
    await expect(assembleBlock(null, [])).rejects.toBeInstanceOf(BlockError)
  })

  it('genesis block has GENESIS_HASH for prev_hash and state_root_before', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    expect(block.index).toBe(0)
    expect(block.prev_hash).toBe(GENESIS_HASH)
    expect(block.state_root_before).toBe(GENESIS_HASH)
  })

  it('genesis block carries is_replay_reconstructable and schema_version', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    expect(block.is_replay_reconstructable).toBe(true)
    expect(block.schema_version).toBe(BLOCK_SCHEMA_VERSION)
  })

  it('validator_signatures has exactly 3 entries with constitutional weights', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    expect(block.validator_signatures).toHaveLength(3)
    const weights = block.validator_signatures.map(s => s.weight)
    expect(weights).toContain(618)
    const auditorWeights = weights.filter(w => w === 191)
    expect(auditorWeights).toHaveLength(2)
  })

  it('chained block increments index and links state_root_before', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    expect(block1.index).toBe(1)
    expect(block1.state_root_before).toBe(block0.state_root_after)
  })

  it('is deterministic — triple run produces identical state_root_after', async () => {
    const entry = makeEntry(0)
    const [b1, b2, b3] = await Promise.all([
      assembleBlock(null, [entry]),
      assembleBlock(null, [entry]),
      assembleBlock(null, [entry]),
    ])
    expect(b1.state_root_after).toBe(b2.state_root_after)
    expect(b2.state_root_after).toBe(b3.state_root_after)
  })

  it('is deterministic — triple run produces identical validator commitments', async () => {
    const entry = makeEntry(0)
    const [b1, b2, b3] = await Promise.all([
      assembleBlock(null, [entry]),
      assembleBlock(null, [entry]),
      assembleBlock(null, [entry]),
    ])
    const c = (b: typeof b1) => b.validator_signatures[0]!.commitment
    expect(c(b1)).toBe(c(b2))
    expect(c(b2)).toBe(c(b3))
  })

  it('different transactions produce different state_root_after', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(null, [makeEntry(1)])
    expect(block0.state_root_after).not.toBe(block1.state_root_after)
  })

  it('different state roots produce different validator commitments', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(null, [makeEntry(1)])
    expect(block0.validator_signatures[0]!.commitment).not.toBe(
      block1.validator_signatures[0]!.commitment,
    )
  })
})

describe('verifyBlock', () => {
  it('verifies a valid genesis block', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    expect(await verifyBlock(block, null)).toBe(true)
  })

  it('verifies a valid chained block', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    expect(await verifyBlock(block1, block0)).toBe(true)
  })

  it('returns false when state_root_after is tampered', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const tampered = { ...block, state_root_after: 'f'.repeat(64) as SHA256Hex }
    expect(await verifyBlock(tampered, null)).toBe(false)
  })

  it('returns false when prev_hash is tampered', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const tampered = { ...block1, prev_hash: 'e'.repeat(64) as SHA256Hex }
    expect(await verifyBlock(tampered, block0)).toBe(false)
  })

  it('returns false when block1 is verified against null prevBlock', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    expect(await verifyBlock(block1, null)).toBe(false)
  })

  it('returns false when a validator commitment is tampered', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const sigs = [...block.validator_signatures]
    sigs[0] = { ...sigs[0]!, commitment: 'c'.repeat(64) as SHA256Hex }
    const tampered = { ...block, validator_signatures: sigs }
    expect(await verifyBlock(tampered, null)).toBe(false)
  })
})
