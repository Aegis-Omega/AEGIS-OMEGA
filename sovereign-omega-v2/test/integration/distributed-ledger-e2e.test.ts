// ============================================================
// SOVEREIGN OMEGA — Distributed Ledger E2E Integration Test
// EPISTEMIC TIER: T2
//
// Exercises the full distributed ledger pipeline:
//   LedgerEntries → CommittedBlocks → BlockChain
//   → BlockReplay → NodeCheckpoints → DivergenceMonitor
//   → EpochSeal → EpochSeal verification
//
// Four simulated nodes: coordinator (φ-weight), two auditors, one
// Byzantine node injecting a tampered state root. The honest 3/4
// achieve φ-BFT quorum; the Byzantine node is identified in diverged.
// ============================================================

import { describe, it, expect } from 'vitest'
import { assembleBlock, verifyBlock } from '../../src/ledger/block.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import { replayChain, replayRange } from '../../src/ledger/block-replay.js'
import { captureNodeCheckpoint, compareCheckpoints } from '../../src/ledger/node-checkpoint.js'
import { assessDivergence, allAgree } from '../../src/ledger/divergence-monitor.js'
import { sealEpoch, verifyEpochSeal } from '../../src/ledger/epoch-seal.js'
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

describe('Distributed Ledger — E2E pipeline', () => {
  it('assembles, replays, checkpoints, and seals a 6-block chain correctly', async () => {
    // ── 1. Assemble 6 blocks ──────────────────────────────────
    let chain     = BlockChain.empty()
    let prevBlock = null
    for (let i = 0; i < 6; i++) {
      const block = await assembleBlock(prevBlock, [makeEntry(i)])
      chain       = chain.append(block)
      prevBlock   = block
    }
    expect(chain.length).toBe(6)
    expect(chain.height).toBe(5)

    // ── 2. Full chain verification ─────────────────────────────
    expect(await chain.verifyAll()).toBe(true)

    // ── 3. Block replay — valid chain ─────────────────────────
    const replay = await replayChain(chain)
    expect(replay.is_valid).toBe(true)
    expect(replay.block_count).toBe(6)
    expect(replay.state_trace).toHaveLength(6)
    expect(replay.final_state_root).toBe(chain.lastBlock!.state_root_after)

    // State trace must be strictly ordered — each root must differ
    const uniqueRoots = new Set(replay.state_trace)
    expect(uniqueRoots.size).toBe(6)

    // ── 4. Range replay — blocks 2..4 ──────────────────────────
    const ranged = await replayRange(chain, 2, 4)
    expect(ranged.is_valid).toBe(true)
    expect(ranged.block_count).toBe(3)
    const blocks = chain.getAll()
    expect(ranged.final_state_root).toBe(blocks[4]!.state_root_after)

    // ── 5. Three honest nodes produce checkpoints at height 5 ─
    const [cpCoord, cpAudit1, cpAudit2] = await Promise.all([
      captureNodeCheckpoint('coordinator', chain.lastBlock!),
      captureNodeCheckpoint('auditor-1',   chain.lastBlock!),
      captureNodeCheckpoint('auditor-2',   chain.lastBlock!),
    ])

    // All honest nodes agree
    expect(allAgree([cpCoord, cpAudit1, cpAudit2])).toBe(true)

    // pairwise comparison
    const cmp = compareCheckpoints(cpCoord, cpAudit1)
    expect(cmp.matches).toBe(true)
    expect(cmp.compared_at_height).toBe(5)

    // ── 6. Byzantine node on a diverged chain ─────────────────
    // Tamper the last block's state_root_after
    const lastBlock    = chain.lastBlock!
    const tamperedLast = { ...lastBlock, state_root_after: 'f'.repeat(64) as SHA256Hex }
    const cpByzantine  = await captureNodeCheckpoint('byzantine', tamperedLast)

    // Byzantine node disagrees with coordinator
    const cmpByz = compareCheckpoints(cpCoord, cpByzantine)
    expect(cmpByz.matches).toBe(false)
    expect(cmpByz.reason).toContain('state_root divergence')

    // ── 7. DivergenceMonitor: 3/4 honest → φ-BFT achieved ─────
    const report = assessDivergence([cpCoord, cpAudit1, cpAudit2, cpByzantine])
    expect(report.bft_achieved).toBe(true)
    expect(report.quorum_fraction).toBeCloseTo(3 / 4)
    expect(report.in_consensus).toHaveLength(3)
    expect(report.diverged).toContain('byzantine')
    expect(report.consensus_root).toBe(lastBlock.state_root_after)

    // ── 8. Epoch 0: seal blocks 0..2, Epoch 1: seal blocks 3..5 ─
    const [seal0, seal1] = await Promise.all([
      sealEpoch(chain, 0, 0, 2),
      sealEpoch(chain, 1, 3, 5),
    ])
    expect(seal0.final_state_root).toBe(blocks[2]!.state_root_after)
    expect(seal1.final_state_root).toBe(blocks[5]!.state_root_after)
    expect(seal0.seal_hash).not.toBe(seal1.seal_hash)

    // Both seals verify against the chain
    expect(await verifyEpochSeal(seal0, chain)).toBe(true)
    expect(await verifyEpochSeal(seal1, chain)).toBe(true)

    // ── 9. Tampered seal does not verify ──────────────────────
    const tamperedSeal = { ...seal0, merkle_root: 'e'.repeat(64) as SHA256Hex }
    expect(await verifyEpochSeal(tamperedSeal, chain)).toBe(false)
  })

  it('Byzantine replay is detected at block level', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const tampered = { ...block1, state_root_after: '9'.repeat(64) as SHA256Hex }

    // verifyBlock catches it
    expect(await verifyBlock(tampered, block0)).toBe(false)

    // replayChain catches it too
    const chain  = BlockChain.empty().append(block0).append(tampered)
    const replay = await replayChain(chain)
    expect(replay.is_valid).toBe(false)
    expect(replay.failed_at_index).toBe(1)
  })

  it('all components are deterministic end-to-end', async () => {
    async function buildAndSeal() {
      let chain    = BlockChain.empty()
      let prevBlock = null
      for (let i = 0; i < 3; i++) {
        const block = await assembleBlock(prevBlock, [makeEntry(i)])
        chain       = chain.append(block)
        prevBlock   = block
      }
      const replay = await replayChain(chain)
      const cp     = await captureNodeCheckpoint('node', chain.lastBlock!)
      const seal   = await sealEpoch(chain, 0, 0, 2)
      return { replay, cp, seal }
    }

    const [r1, r2, r3] = await Promise.all([buildAndSeal(), buildAndSeal(), buildAndSeal()])

    // All replay traces identical
    expect(r1.replay.final_state_root).toBe(r2.replay.final_state_root)
    expect(r2.replay.final_state_root).toBe(r3.replay.final_state_root)

    // All checkpoint hashes identical
    expect(r1.cp.checkpoint_hash).toBe(r2.cp.checkpoint_hash)
    expect(r2.cp.checkpoint_hash).toBe(r3.cp.checkpoint_hash)

    // All seal hashes identical
    expect(r1.seal.seal_hash).toBe(r2.seal.seal_hash)
    expect(r2.seal.seal_hash).toBe(r3.seal.seal_hash)
  })
})
