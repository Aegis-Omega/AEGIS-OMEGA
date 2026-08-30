// ============================================================
// SOVEREIGN OMEGA — Misc Branch Coverage 7
// EPISTEMIC TIER: T2
//
// Targeted branch coverage for remaining distributed ledger gaps:
//
//   block.ts L135: verifyBlock — state_root_before tampered → false
//   block.ts:      verifyBlock — genesis block verified against non-null prev → false
//   block-chain.ts: verifyAll on tampered middle block returns false
//   constitutional-audit.ts L124: verifyAll block_index regression guard
//                                 (defensive dead-code coverage via snapshot)
// ============================================================

import { describe, it, expect } from 'vitest'
import { assembleBlock, verifyBlock } from '../../src/ledger/block.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import {
  buildAuditEntry,
  ConstitutionalAuditLog,
} from '../../src/ledger/constitutional-audit.js'
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

// ── verifyBlock — state_root_before tampering ─────────────

describe('verifyBlock — state_root_before tampered (L135)', () => {
  it('genesis block with tampered state_root_before → false', async () => {
    const block    = await assembleBlock(null, [makeEntry(0)])
    const tampered = { ...block, state_root_before: 'e'.repeat(64) as SHA256Hex }
    expect(await verifyBlock(tampered, null)).toBe(false)
  })

  it('chained block with tampered state_root_before → false', async () => {
    const block0   = await assembleBlock(null, [makeEntry(0)])
    const block1   = await assembleBlock(block0, [makeEntry(1)])
    const tampered = { ...block1, state_root_before: 'e'.repeat(64) as SHA256Hex }
    expect(await verifyBlock(tampered, block0)).toBe(false)
  })

  it('genesis block verified against a non-null prev (wrong context) → false', async () => {
    // A genesis block has prev_hash = GENESIS_HASH. If we verify it against a non-null
    // prevBlock, the expected prev_hash becomes SHA256(prevBlock), not GENESIS_HASH,
    // so verifyBlock returns false (L134).
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    // block0 is genesis; verify it against block1 (wrong prev) → false
    expect(await verifyBlock(block0, block1)).toBe(false)
  })
})

// ── BlockChain.verifyAll — tampered middle block ───────────

describe('BlockChain.verifyAll() — tampered interior block', () => {
  it('tampered block at index 2 in a 4-block chain → verifyAll returns false', async () => {
    const block0   = await assembleBlock(null, [makeEntry(0)])
    const block1   = await assembleBlock(block0, [makeEntry(1)])
    const block2   = await assembleBlock(block1, [makeEntry(2)])
    const block3   = await assembleBlock(block2, [makeEntry(3)])
    const bad      = { ...block2, state_root_after: '9'.repeat(64) as SHA256Hex }
    const chain    = BlockChain.empty().append(block0).append(block1).append(bad).append(block3)
    // Blocks at wrong indices are caught by BlockChain.append() via index check,
    // but we've replaced a block of the same index — verifyAll detects the hash mismatch.
    expect(await chain.verifyAll()).toBe(false)
  })

  it('untampered 3-block chain → verifyAll returns true', async () => {
    const block0 = await assembleBlock(null, [makeEntry(0)])
    const block1 = await assembleBlock(block0, [makeEntry(1)])
    const block2 = await assembleBlock(block1, [makeEntry(2)])
    const chain  = BlockChain.empty().append(block0).append(block1).append(block2)
    expect(await chain.verifyAll()).toBe(true)
  })
})

// ── ConstitutionalAuditLog — snapshot with valid log ─────

describe('ConstitutionalAuditLog.verifyAll() — structural robustness', () => {
  it('two entries at same block_index both verify → verifyAll true', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const e1    = await buildAuditEntry('A', block, GOV)
    const e2    = await buildAuditEntry('B', block, ('d'.repeat(64)) as SHA256Hex)
    const log   = ConstitutionalAuditLog.empty().append(e1).append(e2)
    expect(await log.verifyAll()).toBe(true)
  })

  it('verifyAll on single-entry log verifies the audit_hash', async () => {
    const block = await assembleBlock(null, [makeEntry(0)])
    const entry = await buildAuditEntry('dec-solo', block, GOV)
    const log   = ConstitutionalAuditLog.empty().append(entry)
    expect(await log.verifyAll()).toBe(true)
    // Tamper the single entry
    const bad   = { ...entry, governance_hash: '9'.repeat(64) as SHA256Hex }
    const logBad = ConstitutionalAuditLog.empty().append(bad)
    expect(await logBad.verifyAll()).toBe(false)
  })
})

// ── LedgerEntry boundary — sequence at BigInt(0) ──────────

describe('Ledger boundary — BigInt(0) sequence', () => {
  it('makeEntry with seq=0 produces frozen LedgerEntry with BigInt(0) sequence', () => {
    const entry = makeEntry(0)
    expect(entry.sequence).toBe(0n)
    expect(Object.isFrozen(entry)).toBe(true)
  })
})
