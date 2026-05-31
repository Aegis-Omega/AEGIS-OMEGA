// ============================================================
// SOVEREIGN OMEGA — LedgerObserver tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import { LedgerObserver } from '../../src/ledger/ledger-observer.js'
import { assembleBlock } from '../../src/ledger/block.js'
import { sealEpoch } from '../../src/ledger/epoch-seal.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import { assessDivergence } from '../../src/ledger/divergence-monitor.js'
import { captureNodeCheckpoint } from '../../src/ledger/node-checkpoint.js'
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

describe('LedgerObserver', () => {
  it('starts empty with length 0', () => {
    const obs = LedgerObserver.empty()
    expect(obs.length).toBe(0)
  })

  it('observeBlockCommit increments length and records CONSCIOUSNESS layer', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const obs   = await LedgerObserver.empty().observeBlockCommit(block)
    expect(obs.length).toBe(1)
    const entry = obs.loop.getAll()[0]!
    expect(entry.observation.layer).toBe('CONSCIOUSNESS')
    expect(entry.observation.signal).toContain('block 0 committed')
    expect(entry.observation.tier).toBe('T2')
  })

  it('observeEpochSeal records AUTOPOIETIC_CLOSURE', async () => {
    const chain  = await buildChain(3)
    const seal   = await sealEpoch(chain, 0, 0, 2)
    const obs    = await LedgerObserver.empty().observeEpochSeal(seal)
    expect(obs.length).toBe(1)
    const entry = obs.loop.getAll()[0]!
    expect(entry.observation.layer).toBe('AUTOPOIETIC_CLOSURE')
    expect(entry.observation.signal).toContain('epoch 0 sealed')
    expect(entry.observation.signal).toContain('[0..2]')
  })

  it('observeDivergence records METACOGNITIVE layer', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cps   = await Promise.all([
      captureNodeCheckpoint('node-a', block),
      captureNodeCheckpoint('node-b', block),
    ])
    const report = assessDivergence(cps)
    const obs    = await LedgerObserver.empty().observeDivergence(report)
    expect(obs.length).toBe(1)
    const entry = obs.loop.getAll()[0]!
    expect(entry.observation.layer).toBe('METACOGNITIVE')
    expect(entry.observation.signal).toContain('bft_achieved')
  })

  it('observeCheckpoint records SELF_MODEL layer', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const cp    = await captureNodeCheckpoint('node-a', block)
    const obs   = await LedgerObserver.empty().observeCheckpoint(cp)
    expect(obs.length).toBe(1)
    const entry = obs.loop.getAll()[0]!
    expect(entry.observation.layer).toBe('SELF_MODEL')
    expect(entry.observation.signal).toContain('node-a')
  })

  it('chains are immutable — each observe() returns a new instance', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const obs0  = LedgerObserver.empty()
    const obs1  = await obs0.observeBlockCommit(block)
    expect(obs0.length).toBe(0)
    expect(obs1.length).toBe(1)
  })

  it('multiple observations build monotonically increasing sequence chain', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    let obs = LedgerObserver.empty()
    obs = await obs.observeBlockCommit(block0)
    obs = await obs.observeBlockCommit(block1)
    expect(obs.length).toBe(2)
    const entries = obs.loop.getAll()
    expect(entries[0]!.sequence).toBe(1n)
    expect(entries[1]!.sequence).toBe(2n)
  })

  it('certify() returns is_valid=true for untampered loop', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const obs   = await LedgerObserver.empty().observeBlockCommit(block)
    const cert  = await obs.certify()
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(1)
    expect(cert.terminal_hash).toHaveLength(64)
  })

  it('certify() returns is_valid=true for empty loop', async () => {
    const cert = await LedgerObserver.empty().certify()
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
  })

  it('full pipeline: blocks + epoch + divergence + checkpoint — all certify', async () => {
    const chain  = await buildChain(4)
    const seal   = await sealEpoch(chain, 0, 0, 3)
    const cps    = await Promise.all([
      captureNodeCheckpoint('node-a', chain.lastBlock!),
      captureNodeCheckpoint('node-b', chain.lastBlock!),
    ])
    const report = assessDivergence(cps)

    let obs = LedgerObserver.empty()
    for (const block of chain.getAll()) {
      obs = await obs.observeBlockCommit(block)
    }
    obs = await obs.observeEpochSeal(seal)
    obs = await obs.observeDivergence(report)
    obs = await obs.observeCheckpoint(cps[0]!)

    expect(obs.length).toBe(7)  // 4 blocks + 1 seal + 1 divergence + 1 checkpoint
    const cert = await obs.certify()
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(7)
  })

  it('is deterministic — same events produce identical terminal_hash', async () => {
    async function buildObs() {
      const block = await assembleBlock(null, [makeEntry(0)])
      return (await LedgerObserver.empty().observeBlockCommit(block)).certify()
    }
    const [c1, c2, c3] = await Promise.all([buildObs(), buildObs(), buildObs()])
    expect(c1.terminal_hash).toBe(c2.terminal_hash)
    expect(c2.terminal_hash).toBe(c3.terminal_hash)
  })
})
