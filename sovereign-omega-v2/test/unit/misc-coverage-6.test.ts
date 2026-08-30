// ============================================================
// SOVEREIGN OMEGA — Misc Branch Coverage 6
// EPISTEMIC TIER: T2
//
// Targeted branch coverage for remaining distributed ledger gaps:
//
//   epoch-seal.ts L109: verifyEpochSeal — tampered start_height > end_height
//   epoch-seal.ts: verifyEpochSeal seal_hash re-derivation mismatch via
//                  mutated epoch_number (exercises the final return arm)
//   constitutional-audit.ts: empty log snapshot determinism
//   ledger-observer.ts: observe() generic passthrough
//   block-chain.ts: append() throws BlockChainError for wrong index
// ============================================================

import { describe, it, expect } from 'vitest'
import { assembleBlock } from '../../src/ledger/block.js'
import { BlockChain, BlockChainError } from '../../src/ledger/block-chain.js'
import { sealEpoch, verifyEpochSeal } from '../../src/ledger/epoch-seal.js'
import {
  buildAuditEntry,
  ConstitutionalAuditLog,
  AUDIT_LOG_VERSION,
} from '../../src/ledger/constitutional-audit.js'
import { LedgerObserver } from '../../src/ledger/ledger-observer.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

const EPOCH_BASE = 1_600_000_000_000
const GOV = ('c'.repeat(64)) as SHA256Hex

function makeEntry(seq: number): LedgerEntry {
  return Object.freeze<LedgerEntry>({
    sequence:        BigInt(seq) as SequenceNumber,
    previous_hash:   GENESIS_HASH,
    frame_hash:      ('a'.repeat(64)) as SHA256Hex,
    governance_hash: GOV,
    timestamp_ms:    EPOCH_BASE + seq * 1_000,
  })
}

async function buildChain(length: number): Promise<BlockChain> {
  let chain     = BlockChain.empty()
  let prevBlock = null
  for (let i = 0; i < length; i++) {
    const block = await assembleBlock(prevBlock, [makeEntry(i)])
    chain       = chain.append(block)
    prevBlock   = block
  }
  return chain
}

// ── epoch-seal verifyEpochSeal branches ───────────────────

describe('verifyEpochSeal — remaining branch coverage', () => {
  it('tampered seal with start_height > end_height → returns false (L109)', async () => {
    const chain  = await buildChain(4)
    const seal   = await sealEpoch(chain, 0, 0, 3)
    // Tamper: make start_height > end_height
    const tampered = { ...seal, start_height: 3, end_height: 1 }
    expect(await verifyEpochSeal(tampered, chain)).toBe(false)
  })

  it('tampered epoch_number → seal_hash mismatch, returns false', async () => {
    const chain  = await buildChain(4)
    const seal   = await sealEpoch(chain, 0, 0, 3)
    // Tamper: change epoch_number without updating seal_hash
    const tampered = { ...seal, epoch_number: 99 }
    expect(await verifyEpochSeal(tampered, chain)).toBe(false)
  })

  it('seal verifies after round-trip through tampered then untampered', async () => {
    const chain  = await buildChain(3)
    const seal   = await sealEpoch(chain, 0, 0, 2)
    // Untampered still verifies
    expect(await verifyEpochSeal(seal, chain)).toBe(true)
    // Tampered does not
    const bad = { ...seal, start_height: 99 }
    expect(await verifyEpochSeal(bad, chain)).toBe(false)
    // Original still verifies after tampered test
    expect(await verifyEpochSeal(seal, chain)).toBe(true)
  })
})

// ── ConstitutionalAuditLog — empty snapshot ───────────────

describe('ConstitutionalAuditLog — empty snapshot fields', () => {
  it('empty snapshot has schema_version, entry_count=0, and valid log_root', async () => {
    const snap = await ConstitutionalAuditLog.empty().snapshot()
    expect(snap.schema_version).toBe(AUDIT_LOG_VERSION)
    expect(snap.entry_count).toBe(0)
    expect(snap.log_root).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(snap.log_root)).toBe(true)
  })

  it('empty snapshot is deterministic across three runs', async () => {
    const [s1, s2, s3] = await Promise.all([
      ConstitutionalAuditLog.empty().snapshot(),
      ConstitutionalAuditLog.empty().snapshot(),
      ConstitutionalAuditLog.empty().snapshot(),
    ])
    expect(s1.log_root).toBe(s2.log_root)
    expect(s2.log_root).toBe(s3.log_root)
  })
})

// ── LedgerObserver generic observe() ─────────────────────

describe('LedgerObserver.observe() — generic passthrough', () => {
  it('observe() with arbitrary layer appends entry and certifies', async () => {
    const obs  = await LedgerObserver.empty().observe({
      layer:  'SELF_MODEL',
      signal: 'direct observation — generic passthrough',
      tier:   'T2',
    })
    expect(obs.length).toBe(1)
    const cert = await obs.certify()
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(1)
  })

  it('observe() chained with observeBlockCommit preserves sequence', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    let obs = LedgerObserver.empty()
    obs = await obs.observe({ layer: 'SENSATION', signal: 'pre-commit check', tier: 'T0' })
    obs = await obs.observeBlockCommit(block)
    obs = await obs.observe({ layer: 'METACOGNITIVE', signal: 'post-commit audit', tier: 'T2' })
    expect(obs.length).toBe(3)
    const entries = obs.loop.getAll()
    expect(entries[0]!.sequence).toBe(1n)
    expect(entries[1]!.sequence).toBe(2n)
    expect(entries[2]!.sequence).toBe(3n)
    const cert = await obs.certify()
    expect(cert.is_valid).toBe(true)
  })
})

// ── BlockChain.append() — wrong index throws ──────────────

describe('BlockChain.append() — wrong index rejects', () => {
  it('appending block with wrong index throws BlockChainError', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const block2 = await assembleBlock(block1, [makeEntry(2)])
    const chain  = BlockChain.empty().append(block0)
    // block2 has index=2 but chain expects index=1
    expect(() => chain.append(block2)).toThrow(BlockChainError)
  })

  it('partial(2) rejects block with index=0 (expects index=2)', async () => {
    const chain  = await buildChain(3)
    const block0 = chain.getAll()[0]!
    const partial = BlockChain.partial(2)
    // block0 has index=0 but partial expects index=2
    expect(() => partial.append(block0)).toThrow(BlockChainError)
  })
})

// ── ConstitutionalAuditLog — is_replay_reconstructable ───

describe('ConstitutionalAuditLog — audit entry fields', () => {
  it('audit entry has is_replay_reconstructable=true', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const entry = await buildAuditEntry('dec-001', block, GOV)
    expect(entry.is_replay_reconstructable).toBe(true)
    expect(entry.block_index).toBe(0)
    expect(entry.state_root_at_block).toBe(block.state_root_after)
  })
})
