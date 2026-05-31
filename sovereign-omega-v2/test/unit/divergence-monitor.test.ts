// ============================================================
// SOVEREIGN OMEGA — DivergenceMonitor tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  assessDivergence,
  allAgree,
  DivergenceMonitorError,
} from '../../src/ledger/divergence-monitor.js'
import { captureNodeCheckpoint } from '../../src/ledger/node-checkpoint.js'
import { assembleBlock } from '../../src/ledger/block.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

const EPOCH_BASE = 1_600_000_000_000

function makeEntry(seq: number, tag = 'a'): LedgerEntry {
  return Object.freeze<LedgerEntry>({
    sequence:        BigInt(seq) as SequenceNumber,
    previous_hash:   GENESIS_HASH,
    frame_hash:      (tag.repeat(64)) as SHA256Hex,
    governance_hash: ('b'.repeat(64)) as SHA256Hex,
    timestamp_ms:    EPOCH_BASE + seq * 1_000,
  })
}

describe('assessDivergence', () => {
  it('throws DivergenceMonitorError on empty checkpoints', () => {
    expect(() => assessDivergence([])).toThrow(DivergenceMonitorError)
  })

  it('throws DivergenceMonitorError on height mismatch', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const cpA    = await captureNodeCheckpoint('node-a', block0)
    const cpB    = await captureNodeCheckpoint('node-b', block1)
    expect(() => assessDivergence([cpA, cpB])).toThrow(DivergenceMonitorError)
  })

  it('single node → bft_achieved=true (100% quorum)', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cp    = await captureNodeCheckpoint('node-a', block)
    const report = assessDivergence([cp])
    expect(report.bft_achieved).toBe(true)
    expect(report.quorum_fraction).toBe(1)
    expect(report.total_nodes).toBe(1)
    expect(report.diverged).toHaveLength(0)
    expect(report.in_consensus).toContain('node-a')
  })

  it('all nodes agree → bft_achieved=true, diverged empty', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const [cpA, cpB, cpC] = await Promise.all([
      captureNodeCheckpoint('node-a', block),
      captureNodeCheckpoint('node-b', block),
      captureNodeCheckpoint('node-c', block),
    ])
    const report = assessDivergence([cpA, cpB, cpC])
    expect(report.bft_achieved).toBe(true)
    expect(report.quorum_fraction).toBe(1)
    expect(report.diverged).toHaveLength(0)
    expect(report.consensus_root).toBe(block.state_root_after)
  })

  it('majority agree → bft_achieved=true, minority in diverged', async () => {
    const blockGood = await assembleBlock(null, [makeEntry(0, 'a')])
    const blockBad  = await assembleBlock(null, [makeEntry(0, 'c')]) // different content
    // 3 honest nodes, 1 Byzantine
    const [cpA, cpB, cpC, cpEvil] = await Promise.all([
      captureNodeCheckpoint('node-a', blockGood),
      captureNodeCheckpoint('node-b', blockGood),
      captureNodeCheckpoint('node-c', blockGood),
      captureNodeCheckpoint('node-evil', blockBad),
    ])
    const report = assessDivergence([cpA, cpB, cpC, cpEvil])
    expect(report.bft_achieved).toBe(true)
    expect(report.quorum_fraction).toBeCloseTo(3 / 4)
    expect(report.in_consensus).toHaveLength(3)
    expect(report.diverged).toHaveLength(1)
    expect(report.diverged[0]).toBe('node-evil')
  })

  it('quorum exactly at φ → bft_achieved=true', async () => {
    // 5 nodes: 3 agree (3/5 = 0.6 < φ), so need to get exactly ≥ φ
    // Use 8 nodes: ceil(0.618 * 8) = 5 → 5/8 = 0.625 >= 0.618 → true
    const blockGood = await assembleBlock(null, [makeEntry(0, 'a')])
    const blockBad  = await assembleBlock(null, [makeEntry(0, 'c')])
    const good = await Promise.all(
      ['a','b','c','d','e'].map(n => captureNodeCheckpoint(`node-${n}`, blockGood)),
    )
    const bad = await Promise.all(
      ['x','y','z'].map(n => captureNodeCheckpoint(`node-${n}`, blockBad)),
    )
    const report = assessDivergence([...good, ...bad])
    // 5/8 = 0.625 >= 0.618 → true
    expect(report.bft_achieved).toBe(true)
    expect(report.in_consensus).toHaveLength(5)
    expect(report.diverged).toHaveLength(3)
  })

  it('below φ quorum → bft_achieved=false', async () => {
    // 3 nodes: 1 on each fork → tie → no plurality
    const blockA = await assembleBlock(null, [makeEntry(0, 'a')])
    const blockB = await assembleBlock(null, [makeEntry(0, 'c')])
    const [cpA1, cpB1] = await Promise.all([
      captureNodeCheckpoint('node-a1', blockA),
      captureNodeCheckpoint('node-b1', blockB),
    ])
    const report = assessDivergence([cpA1, cpB1])
    // 2 nodes, perfect split → no plurality → bft_achieved=false
    expect(report.bft_achieved).toBe(false)
    expect(report.consensus_root).toBeNull()
    expect(report.quorum_fraction).toBe(0)
  })

  it('3-way split → no plurality, bft_achieved=false', async () => {
    const blocks = await Promise.all([
      assembleBlock(null, [makeEntry(0, 'a')]),
      assembleBlock(null, [makeEntry(0, 'c')]),
      assembleBlock(null, [makeEntry(0, 'e')]),
    ])
    const cps = await Promise.all(blocks.map((b, i) => captureNodeCheckpoint(`node-${i}`, b)))
    const report = assessDivergence(cps)
    // 1/1/1 split — no plurality
    expect(report.bft_achieved).toBe(false)
    expect(report.consensus_root).toBeNull()
  })

  it('report contains correct block_height', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cp    = await captureNodeCheckpoint('node-a', block)
    const report = assessDivergence([cp])
    expect(report.block_height).toBe(0)
  })

  it('is deterministic — same inputs produce identical reports', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cps   = await Promise.all(['a','b','c'].map(n => captureNodeCheckpoint(`node-${n}`, block)))
    const [r1, r2] = [assessDivergence(cps), assessDivergence(cps)]
    expect(r1.consensus_root).toBe(r2.consensus_root)
    expect(r1.quorum_fraction).toBe(r2.quorum_fraction)
    expect(r1.bft_achieved).toBe(r2.bft_achieved)
  })
})

describe('allAgree', () => {
  it('throws on empty', () => {
    expect(() => allAgree([])).toThrow(DivergenceMonitorError)
  })

  it('returns true when all nodes share the same root and height', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cps   = await Promise.all(['a','b'].map(n => captureNodeCheckpoint(`node-${n}`, block)))
    expect(allAgree(cps)).toBe(true)
  })

  it('returns false when any node diverges', async () => {
    const blockA = await assembleBlock(null, [makeEntry(0, 'a')])
    const blockB = await assembleBlock(null, [makeEntry(0, 'c')])
    const [cpA, cpB] = await Promise.all([
      captureNodeCheckpoint('node-a', blockA),
      captureNodeCheckpoint('node-b', blockB),
    ])
    expect(allAgree([cpA, cpB])).toBe(false)
  })

  it('single node always agrees with itself', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cp    = await captureNodeCheckpoint('node-a', block)
    expect(allAgree([cp])).toBe(true)
  })
})
