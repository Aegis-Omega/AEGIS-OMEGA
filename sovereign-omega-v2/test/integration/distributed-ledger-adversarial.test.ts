// ============================================================
// SOVEREIGN OMEGA — Distributed Ledger Adversarial Integration Test
// EPISTEMIC TIER: T2
//
// Byzantine failure scenarios for the distributed ledger stack:
//   - Chain fork: two competing head blocks, neither a superset
//   - >1/3 Byzantine nodes: quorum breaks, bft_achieved=false
//   - StateCapsule tampering: every tampered field detected
//   - Constitutional audit breach: tampered entry fails verifyAll()
//   - LedgerObserver certify() catches tampered entry_hash
//   - EventBridge → Byzantine replay: corrupted block detected
// ============================================================

import { describe, it, expect } from 'vitest'
import { assembleBlock, verifyBlock } from '../../src/ledger/block.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import { replayChain } from '../../src/ledger/block-replay.js'
import { captureNodeCheckpoint } from '../../src/ledger/node-checkpoint.js'
import { assessDivergence, allAgree } from '../../src/ledger/divergence-monitor.js'
import { sealEpoch } from '../../src/ledger/epoch-seal.js'
import { exportStateCapsule, verifyStateCapsule } from '../../src/ledger/state-capsule.js'
import { buildAuditEntry, ConstitutionalAuditLog } from '../../src/ledger/constitutional-audit.js'
import { LedgerObserver } from '../../src/ledger/ledger-observer.js'
import { LedgerChain } from '../../src/ledger/chain.js'
import { bridgeToBlockChain } from '../../src/ledger/event-bridge.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import { certifyMetacognitiveLoop } from '../../src/metacognition/loop.js'
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

async function buildChain(length: number, tag = 'a'): Promise<BlockChain> {
  let chain    = BlockChain.empty()
  let prevBlock = null
  for (let i = 0; i < length; i++) {
    const block = await assembleBlock(prevBlock, [makeEntry(i, tag)])
    chain       = chain.append(block)
    prevBlock   = block
  }
  return chain
}

describe('Chain fork adversarial', () => {
  it('honest chain and forked chain have different final state roots', async () => {
    const honest = await buildChain(4, 'a')
    const forked = await buildChain(4, 'c')
    expect(honest.lastBlock!.state_root_after).not.toBe(forked.lastBlock!.state_root_after)
  })

  it('verifyAll() passes on honest chain, blocks verify on forked chain independently', async () => {
    const honest = await buildChain(3, 'a')
    const forked = await buildChain(3, 'c')
    expect(await honest.verifyAll()).toBe(true)
    expect(await forked.verifyAll()).toBe(true)
  })

  it('block from honest chain does not verify against forked chain context', async () => {
    const honest = await buildChain(3, 'a')
    const forked = await buildChain(3, 'c')
    // Block 2 of honest chain verifies against block 1 of honest chain
    const honestBlocks = honest.getAll()
    expect(await verifyBlock(honestBlocks[2]!, honestBlocks[1]!)).toBe(true)
    // But NOT against block 1 of the forked chain
    const forkedBlocks = forked.getAll()
    expect(await verifyBlock(honestBlocks[2]!, forkedBlocks[1]!)).toBe(false)
  })

  it('DivergenceMonitor detects fork — different chains produce different checkpoints', async () => {
    const honest = await buildChain(2, 'a')
    const forked = await buildChain(2, 'c')
    const [cpHonest, cpForked] = await Promise.all([
      captureNodeCheckpoint('node-honest', honest.lastBlock!),
      captureNodeCheckpoint('node-forked', forked.lastBlock!),
    ])
    expect(allAgree([cpHonest, cpForked])).toBe(false)
    const report = assessDivergence([cpHonest, cpForked])
    expect(report.bft_achieved).toBe(false)
  })
})

describe('Byzantine quorum failure (>1/3 malicious)', () => {
  it('4 Byzantine + 3 honest (4/7 > 3/7) → Byzantine achieves plurality but not φ-quorum', async () => {
    // 7 nodes: 4 on forked chain, 3 on honest chain
    // 4/7 ≈ 0.571 < φ ≈ 0.618 → bft_achieved=false
    const honest = await buildChain(2, 'a')
    const forked = await buildChain(2, 'c')
    const honestCps = await Promise.all(
      ['h1','h2','h3'].map(n => captureNodeCheckpoint(n, honest.lastBlock!)),
    )
    const byzantineCps = await Promise.all(
      ['b1','b2','b3','b4'].map(n => captureNodeCheckpoint(n, forked.lastBlock!)),
    )
    const report = assessDivergence([...honestCps, ...byzantineCps])
    // Byzantine have plurality (4/7) but not φ-quorum
    expect(report.bft_achieved).toBe(false)
    expect(report.quorum_fraction).toBeCloseTo(4 / 7)
  })

  it('5 honest + 2 Byzantine (5/7 > φ) → honest quorum survives', async () => {
    const honest  = await buildChain(2, 'a')
    const forked  = await buildChain(2, 'c')
    const honestCps   = await Promise.all(
      ['h1','h2','h3','h4','h5'].map(n => captureNodeCheckpoint(n, honest.lastBlock!)),
    )
    const byzantineCps = await Promise.all(
      ['b1','b2'].map(n => captureNodeCheckpoint(n, forked.lastBlock!)),
    )
    const report = assessDivergence([...honestCps, ...byzantineCps])
    expect(report.bft_achieved).toBe(true)
    expect(report.quorum_fraction).toBeCloseTo(5 / 7)
    expect(report.diverged).toHaveLength(2)
  })
})

describe('StateCapsule adversarial', () => {
  it('tampering capsule_hash → verify fails', async () => {
    const chain   = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const tampered = { ...capsule, capsule_hash: 'f'.repeat(64) as SHA256Hex }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('tampering pending_block state_root → verify fails', async () => {
    const chain   = await buildChain(4)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const badBlock = { ...capsule.pending_blocks[2]!, state_root_after: '9'.repeat(64) as SHA256Hex }
    const pending  = [...capsule.pending_blocks.slice(0, 2), badBlock, capsule.pending_blocks[3]!]
    const tampered = { ...capsule, pending_blocks: pending }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('tampering tip_checkpoint state_root → verify fails', async () => {
    const chain   = await buildChain(3)
    const capsule = await exportStateCapsule('node-a', chain, null)
    const badCp   = { ...capsule.tip_checkpoint, state_root: 'e'.repeat(64) as SHA256Hex }
    const tampered = { ...capsule, tip_checkpoint: badCp }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })

  it('epoch seal mismatch with anchor_block → verify fails', async () => {
    const chain  = await buildChain(6)
    const epoch  = await sealEpoch(chain, 0, 0, 2)
    const capsule = await exportStateCapsule('node-a', chain, epoch)
    // Swap anchor_block with a different block from the chain
    const wrongAnchor = chain.getAll()[1]!  // index 1, not 2
    const tampered    = { ...capsule, anchor_block: wrongAnchor }
    expect(await verifyStateCapsule(tampered)).toBe(false)
  })
})

describe('ConstitutionalAuditLog adversarial', () => {
  it('single tampered entry fails verifyAll()', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const GOV    = ('c'.repeat(64)) as SHA256Hex
    const e0     = await buildAuditEntry('dec-0', block0, GOV)
    const e1     = await buildAuditEntry('dec-1', block1, GOV)
    const tampered = { ...e0, audit_hash: 'f'.repeat(64) as SHA256Hex }
    const log = ConstitutionalAuditLog.empty().append(tampered).append(e1)
    expect(await log.verifyAll()).toBe(false)
  })

  it('replacing governance_hash without updating audit_hash → verifyAll fails', async () => {
    const block  = await assembleBlock(null, [makeEntry(0)])
    const entry  = await buildAuditEntry('dec-x', block, ('c'.repeat(64)) as SHA256Hex)
    const tampered = { ...entry, governance_hash: 'f'.repeat(64) as SHA256Hex }
    const log    = ConstitutionalAuditLog.empty().append(tampered)
    expect(await log.verifyAll()).toBe(false)
  })
})

describe('LedgerObserver certify adversarial', () => {
  it('manually injected tampered entry → certify is_valid=false', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const obs   = await LedgerObserver.empty().observeBlockCommit(block)
    // Manually tamper the entry_hash of the only entry
    const entries = obs.loop.getAll()
    const tampered = [{ ...entries[0]!, entry_hash: 'f'.repeat(64) as SHA256Hex }]
    const cert  = await certifyMetacognitiveLoop(tampered)
    expect(cert.is_valid).toBe(false)
  })
})

describe('EventBridge adversarial', () => {
  it('bridged chain with a tampered block fails replayChain', async () => {
    // Build a LedgerChain and bridge it to a BlockChain
    let lChain = LedgerChain.empty()
    for (let i = 0; i < 4; i++) lChain = lChain.append(makeEntry(i))
    const result = await bridgeToBlockChain(lChain, 2)

    // Tamper the second block's state_root_after
    const blocks = result.blockChain.getAll()
    const bad    = { ...blocks[1]!, state_root_after: '9'.repeat(64) as SHA256Hex }
    const tampered = BlockChain.empty().append(blocks[0]!).append(bad)

    const replay = await replayChain(tampered)
    expect(replay.is_valid).toBe(false)
    expect(replay.failed_at_index).toBe(1)
  })
})
