// ============================================================
// SOVEREIGN OMEGA — NodeCheckpoint tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  captureNodeCheckpoint,
  verifyNodeCheckpoint,
  compareCheckpoints,
  NodeCheckpointError,
} from '../../src/ledger/node-checkpoint.js'
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

describe('captureNodeCheckpoint', () => {
  it('produces a checkpoint with correct height and state_root', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cp    = await captureNodeCheckpoint('node-a', block)
    expect(cp.block_height).toBe(0)
    expect(cp.state_root).toBe(block.state_root_after)
    expect(cp.node_id).toBe('node-a')
    expect(cp.is_replay_reconstructable).toBe(true)
  })

  it('throws NodeCheckpointError for empty node_id', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    await expect(captureNodeCheckpoint('', block)).rejects.toBeInstanceOf(NodeCheckpointError)
    await expect(captureNodeCheckpoint('  ', block)).rejects.toBeInstanceOf(NodeCheckpointError)
  })

  it('is deterministic — triple run produces identical checkpoint_hash', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const [c1, c2, c3] = await Promise.all([
      captureNodeCheckpoint('node-x', block),
      captureNodeCheckpoint('node-x', block),
      captureNodeCheckpoint('node-x', block),
    ])
    expect(c1.checkpoint_hash).toBe(c2.checkpoint_hash)
    expect(c2.checkpoint_hash).toBe(c3.checkpoint_hash)
  })
})

describe('verifyNodeCheckpoint', () => {
  it('returns true for an unmodified checkpoint', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cp    = await captureNodeCheckpoint('node-a', block)
    expect(await verifyNodeCheckpoint(cp)).toBe(true)
  })

  it('returns false when state_root is tampered', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cp    = await captureNodeCheckpoint('node-a', block)
    const tampered = { ...cp, state_root: 'f'.repeat(64) as SHA256Hex }
    expect(await verifyNodeCheckpoint(tampered)).toBe(false)
  })

  it('returns false when node_id is tampered', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cp    = await captureNodeCheckpoint('node-a', block)
    const tampered = { ...cp, node_id: 'node-evil' }
    expect(await verifyNodeCheckpoint(tampered)).toBe(false)
  })
})

describe('compareCheckpoints', () => {
  it('returns matches:true when two nodes agree at the same height', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cpA   = await captureNodeCheckpoint('node-a', block)
    const cpB   = await captureNodeCheckpoint('node-b', block)
    const result = compareCheckpoints(cpA, cpB)
    expect(result.matches).toBe(true)
    expect(result.compared_at_height).toBe(0)
    expect(result.reason).toBeUndefined()
  })

  it('returns matches:false when nodes are at different heights', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const cpA    = await captureNodeCheckpoint('node-a', block0)
    const cpB    = await captureNodeCheckpoint('node-b', block1)
    const result = compareCheckpoints(cpA, cpB)
    expect(result.matches).toBe(false)
    expect(result.reason).toContain('height mismatch')
  })

  it('returns matches:false when state_roots diverge at the same height', async () => {
    const entryA = Object.freeze<LedgerEntry>({
      sequence: 0n as SequenceNumber, previous_hash: GENESIS_HASH,
      frame_hash: ('a'.repeat(64)) as SHA256Hex,
      governance_hash: ('b'.repeat(64)) as SHA256Hex, timestamp_ms: EPOCH_BASE,
    })
    const entryB = Object.freeze<LedgerEntry>({
      sequence: 0n as SequenceNumber, previous_hash: GENESIS_HASH,
      frame_hash: ('c'.repeat(64)) as SHA256Hex,  // different content
      governance_hash: ('d'.repeat(64)) as SHA256Hex, timestamp_ms: EPOCH_BASE,
    })
    const blockA = await assembleBlock(null, [entryA])
    const blockB = await assembleBlock(null, [entryB])
    const cpA    = await captureNodeCheckpoint('node-a', blockA)
    const cpB    = await captureNodeCheckpoint('node-b', blockB)
    const result = compareCheckpoints(cpA, cpB)
    expect(result.matches).toBe(false)
    expect(result.reason).toContain('state_root divergence')
  })
})
