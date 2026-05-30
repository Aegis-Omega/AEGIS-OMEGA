// ============================================================
// SOVEREIGN OMEGA — StateCapsule tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  exportStateCapsule,
  verifyStateCapsule,
  importStateCapsule,
  StateCapsuleError,
  STATE_CAPSULE_VERSION,
} from '../../src/ledger/state-capsule.js'
import { sealEpoch } from '../../src/ledger/epoch-seal.js'
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

describe('exportStateCapsule', () => {
  it('throws StateCapsuleError for empty chain', async () => {
    await expect(
      exportStateCapsule('node-a', BlockChain.empty(), null),
    ).rejects.toBeInstanceOf(StateCapsuleError)
  })

  it('null epoch → anchor_block is null, pending_blocks = all blocks', async () => {
    const chain  = await buildChain(3)
    const capsule = await exportStateCapsule('node-a', chain, null)
    expect(capsule.latest_epoch).toBeNull()
    expect(capsule.anchor_block).toBeNull()
    expect(capsule.pending_blocks).toHaveLength(3)
    expect(capsule.schema_version).toBe(STATE_CAPSULE_VERSION)
    expect(capsule.is_replay_reconstructable).toBe(true)
  })

  it('with epoch → anchor_block = last epoch block, pending_blocks = post-epoch', async () => {
    const chain = await buildChain(6)
    const epoch = await sealEpoch(chain, 0, 0, 2)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    expect(capsule.anchor_block?.index).toBe(2)
    expect(capsule.pending_blocks).toHaveLength(3)  // blocks 3, 4, 5
  })

  it('epoch covering full chain → pending_blocks is empty', async () => {
    const chain = await buildChain(4)
    const epoch = await sealEpoch(chain, 0, 0, 3)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    expect(capsule.anchor_block?.index).toBe(3)
    expect(capsule.pending_blocks).toHaveLength(0)
  })

  it('tip_checkpoint.state_root matches chain tip', async () => {
    const chain  = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    expect(capsule.tip_checkpoint.state_root).toBe(chain.lastBlock!.state_root_after)
  })

  it('throws StateCapsuleError when epoch end_height out of chain range', async () => {
    const chain = await buildChain(3)
    const epoch = await sealEpoch(chain, 0, 0, 2)
    const shortChain = await buildChain(2)  // only 2 blocks — epoch end_height=2 is out of range
    await expect(
      exportStateCapsule('node-a', shortChain, epoch),
    ).rejects.toBeInstanceOf(StateCapsuleError)
  })
})

describe('verifyStateCapsule', () => {
  it('returns true for a valid no-epoch capsule', async () => {
    const chain  = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    expect(await verifyStateCapsule(capsule)).toBe(true)
  })

  it('returns true for a valid epoch capsule', async () => {
    const chain  = await buildChain(6)
    const epoch  = await sealEpoch(chain, 0, 0, 2)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    expect(await verifyStateCapsule(capsule)).toBe(true)
  })

  it('returns true for epoch covering full chain (pending_blocks empty)', async () => {
    const chain  = await buildChain(4)
    const epoch  = await sealEpoch(chain, 0, 0, 3)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    expect(await verifyStateCapsule(capsule)).toBe(true)
  })

  it('returns false when capsule_hash is tampered', async () => {
    const chain  = await buildChain(3)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const tampered = { ...capsule, capsule_hash: 'f'.repeat(64) as SHA256Hex }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('returns false when tip_checkpoint is tampered', async () => {
    const chain  = await buildChain(3)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const badCp   = { ...capsule.tip_checkpoint, checkpoint_hash: 'e'.repeat(64) as SHA256Hex }
    const tampered = { ...capsule, tip_checkpoint: badCp }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('returns false when a pending block is tampered', async () => {
    const chain  = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const badBlock = { ...capsule.pending_blocks[1]!, state_root_after: 'd'.repeat(64) as SHA256Hex }
    const pending  = [capsule.pending_blocks[0]!, badBlock, capsule.pending_blocks[2]!, capsule.pending_blocks[3]!]
    const tampered = { ...capsule, pending_blocks: pending }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })
})

describe('importStateCapsule', () => {
  it('no-epoch capsule → BlockChain with all blocks', async () => {
    const chain  = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const imported = await importStateCapsule(capsule)
    expect(imported.length).toBe(4)
    expect(imported.lastBlock!.state_root_after).toBe(chain.lastBlock!.state_root_after)
  })

  it('epoch capsule → BlockChain with anchor + pending blocks, correct offset', async () => {
    const chain  = await buildChain(6)
    const epoch  = await sealEpoch(chain, 0, 0, 2)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    const imported = await importStateCapsule(capsule)
    // anchor (index 2) + 3 pending blocks = 4 blocks
    expect(imported.length).toBe(4)
    expect(imported.offset).toBe(2)
    expect(imported.height).toBe(5)
    expect(imported.lastBlock!.state_root_after).toBe(chain.lastBlock!.state_root_after)
  })

  it('no-epoch imported chain passes verifyAll() (starts at genesis)', async () => {
    const chain  = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const imported = await importStateCapsule(capsule)
    // Full chain starting at genesis — verifyAll should pass
    expect(await imported.verifyAll()).toBe(true)
  })

  it('partial (epoch) imported chain tip matches original; block linkage within pending is valid', async () => {
    const chain  = await buildChain(5)
    const epoch  = await sealEpoch(chain, 0, 0, 1)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    const imported = await importStateCapsule(capsule)
    // The tip state root is preserved
    expect(imported.lastBlock!.state_root_after).toBe(chain.lastBlock!.state_root_after)
    // The capsule itself verified OK — that proves post-epoch block linkage
    expect(await verifyStateCapsule(capsule)).toBe(true)
  })

  it('is deterministic — two imports of same capsule produce same tip state_root', async () => {
    const chain   = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const [i1, i2] = await Promise.all([
      importStateCapsule(capsule),
      importStateCapsule(capsule),
    ])
    expect(i1.lastBlock!.state_root_after).toBe(i2.lastBlock!.state_root_after)
  })
})
