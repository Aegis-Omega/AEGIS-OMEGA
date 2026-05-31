// ============================================================
// SOVEREIGN OMEGA — Distributed Ledger Audit × Observer × Capsule Composition
// EPISTEMIC TIER: T2
//
// Integration test composing the three observability/compliance layers
// of the distributed ledger stack:
//
//   ConstitutionalAuditLog — EU AI Act Art. 12 decision binder
//   LedgerObserver         — MetacognitiveLoop bridge (consciousness)
//   StateCapsule           — portable state-transfer bundle
//
// Together they form the full compliance-conscious pipeline:
//   CommittedBlocks → audit decisions + observe events → capsule export.
//
// Tests verify:
//   - Joint build passes all three verifications simultaneously
//   - Determinism: same blocks → identical audit/observer hashes
//   - Tamper propagation: one corrupted audit entry → verifyAll() false,
//     observer certify() still true (independent chains)
//   - Capsule integrity upheld through the full pipeline
// ============================================================

import { describe, it, expect } from 'vitest'
import { assembleBlock } from '../../src/ledger/block.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import {
  buildAuditEntry,
  ConstitutionalAuditLog,
  AuditLogError,
} from '../../src/ledger/constitutional-audit.js'
import { LedgerObserver } from '../../src/ledger/ledger-observer.js'
import { exportStateCapsule, verifyStateCapsule } from '../../src/ledger/state-capsule.js'
import { sealEpoch } from '../../src/ledger/epoch-seal.js'
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

async function buildPipeline(length: number) {
  let chain     = BlockChain.empty()
  let prevBlock = null
  let auditLog  = ConstitutionalAuditLog.empty()
  let observer  = LedgerObserver.empty()

  for (let i = 0; i < length; i++) {
    const block = await assembleBlock(prevBlock, [makeEntry(i)])
    chain       = chain.append(block)
    prevBlock   = block

    // Audit entry — one governance decision per block
    const entry = await buildAuditEntry(`dec-${i}`, block, GOV)
    auditLog    = auditLog.append(entry)

    // Observe block commit
    observer = await observer.observeBlockCommit(block)
  }

  return { chain, auditLog, observer }
}

describe('ConstitutionalAuditLog × LedgerObserver × StateCapsule composition', () => {
  it('joint build: all three verifications pass simultaneously', async () => {
    const { chain, auditLog, observer } = await buildPipeline(4)

    // Audit log intact
    expect(await auditLog.verifyAll()).toBe(true)
    expect(auditLog.length).toBe(4)

    // Observer chain intact
    const cert = await observer.certify()
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(4)

    // Capsule exports and verifies
    const capsule = await exportStateCapsule('node-a', chain, null)
    expect(await verifyStateCapsule(capsule)).toBe(true)
    expect(capsule.pending_blocks).toHaveLength(4)
  })

  it('audit log snapshot root and observer terminal_hash are both 64-char hex', async () => {
    const { auditLog, observer } = await buildPipeline(3)

    const snap = await auditLog.snapshot()
    expect(snap.log_root).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(snap.log_root)).toBe(true)

    const cert = await observer.certify()
    expect(cert.terminal_hash).not.toBeNull()
    expect(cert.terminal_hash!).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(cert.terminal_hash!)).toBe(true)
  })

  it('determinism: identical blocks produce identical audit log_root and observer terminal_hash', async () => {
    const [r1, r2, r3] = await Promise.all([
      buildPipeline(3),
      buildPipeline(3),
      buildPipeline(3),
    ])
    const [s1, s2, s3] = await Promise.all([
      r1.auditLog.snapshot(),
      r2.auditLog.snapshot(),
      r3.auditLog.snapshot(),
    ])
    const [c1, c2, c3] = await Promise.all([
      r1.observer.certify(),
      r2.observer.certify(),
      r3.observer.certify(),
    ])

    expect(s1.log_root).toBe(s2.log_root)
    expect(s2.log_root).toBe(s3.log_root)
    expect(c1.terminal_hash).toBe(c2.terminal_hash)
    expect(c2.terminal_hash).toBe(c3.terminal_hash)
  })

  it('tampered audit entry → verifyAll() false; observer certify() unaffected', async () => {
    const { chain, auditLog, observer } = await buildPipeline(4)

    // Tamper second audit entry
    const entries = auditLog.getAll()
    const bad     = { ...entries[1]!, audit_hash: 'f'.repeat(64) as SHA256Hex }
    const tampered = ConstitutionalAuditLog.empty()
      .append(entries[0]!)
      .append(bad)
      .append(entries[2]!)
      .append(entries[3]!)

    expect(await tampered.verifyAll()).toBe(false)

    // Observer chain is independent — not broken by audit tampering
    const cert = await observer.certify()
    expect(cert.is_valid).toBe(true)

    // Capsule still verifies (uses block chain, not audit log)
    const capsule = await exportStateCapsule('node-a', chain, null)
    expect(await verifyStateCapsule(capsule)).toBe(true)
  })

  it('audit log enforces block_index monotonicity across the pipeline', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const e0     = await buildAuditEntry('dec-0', block0, GOV)
    const e1     = await buildAuditEntry('dec-1', block1, GOV)

    // Forward order: ok
    const log = ConstitutionalAuditLog.empty().append(e0).append(e1)
    expect(await log.verifyAll()).toBe(true)

    // Regression: e1 then e0 → throw
    const forward = ConstitutionalAuditLog.empty().append(e1)
    expect(() => forward.append(e0)).toThrow(AuditLogError)
  })

  it('observer records AUTOPOIETIC_CLOSURE for epoch seal between blocks', async () => {
    const { chain, observer: obs0 } = await buildPipeline(4)
    const seal = await sealEpoch(chain, 0, 0, 3)
    const observer = await obs0.observeEpochSeal(seal)

    expect(observer.length).toBe(5)  // 4 blocks + 1 seal
    const entries = observer.loop.getAll()
    expect(entries[4]!.observation.layer).toBe('AUTOPOIETIC_CLOSURE')

    const cert = await observer.certify()
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(5)
  })

  it('capsule export with epoch seal contains correct anchor_block and pending_blocks', async () => {
    const { chain } = await buildPipeline(6)
    const seal = await sealEpoch(chain, 0, 0, 3)

    const capsule = await exportStateCapsule('node-a', chain, seal)
    expect(await verifyStateCapsule(capsule)).toBe(true)

    // anchor = block at index 3 (last epoch block)
    expect(capsule.anchor_block!.index).toBe(3)
    // pending = blocks after epoch (4, 5)
    expect(capsule.pending_blocks).toHaveLength(2)
    expect(capsule.pending_blocks[0]!.index).toBe(4)
    expect(capsule.pending_blocks[1]!.index).toBe(5)

    // Audit log can be built independently on the same blocks
    const blocks = chain.getAll()
    let auditLog = ConstitutionalAuditLog.empty()
    for (const b of blocks) {
      const e = await buildAuditEntry(`dec-${b.index}`, b, GOV)
      auditLog = auditLog.append(e)
    }
    expect(await auditLog.verifyAll()).toBe(true)
    expect(auditLog.length).toBe(6)

    const snap = await auditLog.snapshot()
    expect(snap.entry_count).toBe(6)
  })

  it('multiple governance decisions per block are all audit-valid', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const [e1, e2, e3] = await Promise.all([
      buildAuditEntry('dec-A', block, GOV),
      buildAuditEntry('dec-B', block, ('d'.repeat(64)) as SHA256Hex),
      buildAuditEntry('dec-C', block, ('e'.repeat(64)) as SHA256Hex),
    ])
    const log = ConstitutionalAuditLog.empty().append(e1).append(e2).append(e3)
    expect(await log.verifyAll()).toBe(true)
    expect(log.length).toBe(3)
    const snap = await log.snapshot()
    expect(snap.entry_count).toBe(3)
  })

  it('full pipeline: 6 blocks, epoch seal, 2 pending, audit + observer + capsule all valid', async () => {
    const { chain, auditLog, observer: obs } = await buildPipeline(6)
    const seal     = await sealEpoch(chain, 0, 0, 3)
    const observer = await obs.observeEpochSeal(seal)

    // All three verifications pass
    expect(await auditLog.verifyAll()).toBe(true)
    const cert = await observer.certify()
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(7)  // 6 blocks + 1 seal

    const capsule = await exportStateCapsule('node-a', chain, seal)
    expect(await verifyStateCapsule(capsule)).toBe(true)

    // Capsule + audit agree on block count
    const totalBlocks = 1 + capsule.pending_blocks.length  // anchor + pending
    expect(auditLog.length).toBe(chain.length)
    expect(totalBlocks).toBe(3)  // anchor(3) + pending(4,5)
  })
})
