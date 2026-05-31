// ============================================================
// SOVEREIGN OMEGA — ConstitutionalAuditLog tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  buildAuditEntry,
  verifyAuditEntry,
  ConstitutionalAuditLog,
  AuditLogError,
  AUDIT_LOG_VERSION,
} from '../../src/ledger/constitutional-audit.js'
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

const FAKE_GOV_HASH = ('c'.repeat(64)) as SHA256Hex

describe('buildAuditEntry', () => {
  it('produces an entry with correct block_index and state_root_at_block', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const entry = await buildAuditEntry('dec-001', block, FAKE_GOV_HASH)
    expect(entry.decision_id).toBe('dec-001')
    expect(entry.block_index).toBe(0)
    expect(entry.state_root_at_block).toBe(block.state_root_after)
    expect(entry.governance_hash).toBe(FAKE_GOV_HASH)
    expect(entry.is_replay_reconstructable).toBe(true)
  })

  it('throws AuditLogError for empty decision_id', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    await expect(buildAuditEntry('', block, FAKE_GOV_HASH)).rejects.toBeInstanceOf(AuditLogError)
    await expect(buildAuditEntry('  ', block, FAKE_GOV_HASH)).rejects.toBeInstanceOf(AuditLogError)
  })

  it('audit_hash is 64-char hex', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const entry = await buildAuditEntry('dec-x', block, FAKE_GOV_HASH)
    expect(entry.audit_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(entry.audit_hash)).toBe(true)
  })

  it('is deterministic — same inputs produce identical audit_hash', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const [e1, e2, e3] = await Promise.all([
      buildAuditEntry('dec-001', block, FAKE_GOV_HASH),
      buildAuditEntry('dec-001', block, FAKE_GOV_HASH),
      buildAuditEntry('dec-001', block, FAKE_GOV_HASH),
    ])
    expect(e1.audit_hash).toBe(e2.audit_hash)
    expect(e2.audit_hash).toBe(e3.audit_hash)
  })

  it('different decision_ids produce different audit_hashes', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const [e1, e2] = await Promise.all([
      buildAuditEntry('dec-A', block, FAKE_GOV_HASH),
      buildAuditEntry('dec-B', block, FAKE_GOV_HASH),
    ])
    expect(e1.audit_hash).not.toBe(e2.audit_hash)
  })
})

describe('verifyAuditEntry', () => {
  it('returns true for a valid entry', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const entry = await buildAuditEntry('dec-001', block, FAKE_GOV_HASH)
    expect(await verifyAuditEntry(entry)).toBe(true)
  })

  it('returns false when audit_hash is tampered', async () => {
    const block   = await assembleBlock(null, [makeEntry(0)])
    const entry   = await buildAuditEntry('dec-001', block, FAKE_GOV_HASH)
    const tampered = { ...entry, audit_hash: 'f'.repeat(64) as SHA256Hex }
    expect(await verifyAuditEntry(tampered)).toBe(false)
  })

  it('returns false when decision_id is tampered', async () => {
    const block   = await assembleBlock(null, [makeEntry(0)])
    const entry   = await buildAuditEntry('dec-001', block, FAKE_GOV_HASH)
    const tampered = { ...entry, decision_id: 'dec-evil' }
    expect(await verifyAuditEntry(tampered)).toBe(false)
  })

  it('returns false when state_root_at_block is tampered', async () => {
    const block   = await assembleBlock(null, [makeEntry(0)])
    const entry   = await buildAuditEntry('dec-001', block, FAKE_GOV_HASH)
    const tampered = { ...entry, state_root_at_block: 'e'.repeat(64) as SHA256Hex }
    expect(await verifyAuditEntry(tampered)).toBe(false)
  })
})

describe('ConstitutionalAuditLog', () => {
  it('starts empty', () => {
    const log = ConstitutionalAuditLog.empty()
    expect(log.length).toBe(0)
    expect(log.getAll()).toHaveLength(0)
  })

  it('append returns a new log without mutating the original', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const entry = await buildAuditEntry('dec-001', block, FAKE_GOV_HASH)
    const log   = ConstitutionalAuditLog.empty()
    const log1  = log.append(entry)
    expect(log.length).toBe(0)
    expect(log1.length).toBe(1)
  })

  it('throws AuditLogError on block_index regression', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const e0     = await buildAuditEntry('dec-0', block0, FAKE_GOV_HASH)
    const e1     = await buildAuditEntry('dec-1', block1, FAKE_GOV_HASH)
    const log    = ConstitutionalAuditLog.empty().append(e1)
    expect(() => log.append(e0)).toThrow(AuditLogError)
  })

  it('allows multiple entries at the same block_index', async () => {
    const block  = await assembleBlock(null, [makeEntry(0)])
    const e1     = await buildAuditEntry('dec-A', block, FAKE_GOV_HASH)
    const e2     = await buildAuditEntry('dec-B', block, ('d'.repeat(64)) as SHA256Hex)
    const log    = ConstitutionalAuditLog.empty().append(e1).append(e2)
    expect(log.length).toBe(2)
  })

  it('verifyAll returns true for a valid log', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const e0     = await buildAuditEntry('dec-0', block0, FAKE_GOV_HASH)
    const e1     = await buildAuditEntry('dec-1', block1, FAKE_GOV_HASH)
    const log    = ConstitutionalAuditLog.empty().append(e0).append(e1)
    expect(await log.verifyAll()).toBe(true)
  })

  it('verifyAll returns true for empty log', async () => {
    expect(await ConstitutionalAuditLog.empty().verifyAll()).toBe(true)
  })

  it('verifyAll returns false when an entry is tampered', async () => {
    const block  = await assembleBlock(null, [makeEntry(0)])
    const entry  = await buildAuditEntry('dec-001', block, FAKE_GOV_HASH)
    const tampered = { ...entry, audit_hash: 'f'.repeat(64) as SHA256Hex }
    const log    = ConstitutionalAuditLog.empty().append(tampered)
    expect(await log.verifyAll()).toBe(false)
  })

  it('snapshot has correct schema_version, entry_count, and non-empty log_root', async () => {
    const block  = await assembleBlock(null, [makeEntry(0)])
    const entry  = await buildAuditEntry('dec-001', block, FAKE_GOV_HASH)
    const log    = ConstitutionalAuditLog.empty().append(entry)
    const snap   = await log.snapshot()
    expect(snap.schema_version).toBe(AUDIT_LOG_VERSION)
    expect(snap.entry_count).toBe(1)
    expect(snap.log_root).toHaveLength(64)
  })

  it('empty snapshot has deterministic log_root', async () => {
    const [s1, s2] = await Promise.all([
      ConstitutionalAuditLog.empty().snapshot(),
      ConstitutionalAuditLog.empty().snapshot(),
    ])
    expect(s1.log_root).toBe(s2.log_root)
  })

  it('snapshot log_root changes when entries differ', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const e0     = await buildAuditEntry('dec-0', block0, FAKE_GOV_HASH)
    const e1     = await buildAuditEntry('dec-1', block1, FAKE_GOV_HASH)
    const logA   = ConstitutionalAuditLog.empty().append(e0)
    const logB   = ConstitutionalAuditLog.empty().append(e0).append(e1)
    const [sA, sB] = await Promise.all([logA.snapshot(), logB.snapshot()])
    expect(sA.log_root).not.toBe(sB.log_root)
  })
})
