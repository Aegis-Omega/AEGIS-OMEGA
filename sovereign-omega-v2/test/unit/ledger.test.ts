// ============================================================
// Gate 17 — Merkle Replay Ledger Tests
// ~20 tests: chain append, sequence guard, hash chain,
//   checkpoint merkle, snapshot freezing, verifyChain
// ============================================================

import { describe, it, expect } from 'vitest'
import { LedgerChain } from '../../src/ledger/chain.js'
import {
  LedgerConstraintError,
  GENESIS_HASH,
  type LedgerEntry,
} from '../../src/ledger/types.js'
import { captureCheckpoint } from '../../src/ledger/checkpoint.js'
import { verifyChain, verifySequences } from '../../src/ledger/verify.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

// ─── Helpers ───────────────────────────────────────────────

const TS = 1_600_000_000_000  // fixed epoch constant — never Date.now()

function makeEntry(
  seq: bigint,
  previousHash: SHA256Hex = GENESIS_HASH,
): LedgerEntry {
  return Object.freeze({
    sequence: seq as SequenceNumber,
    previous_hash: previousHash,
    frame_hash: ('f'.repeat(64)) as SHA256Hex,
    governance_hash: ('e'.repeat(64)) as SHA256Hex,
    timestamp_ms: TS + Number(seq),
  })
}

async function buildChain(length: number): Promise<{
  chain: LedgerChain
  entries: LedgerEntry[]
}> {
  const entries: LedgerEntry[] = []
  let chain = LedgerChain.empty()
  let prevHash = GENESIS_HASH

  for (let i = 0; i < length; i++) {
    const entry = makeEntry(BigInt(i + 1), prevHash)
    entries.push(entry)
    chain = chain.append(entry)
    prevHash = await hashValue(entry)
  }

  return { chain, entries }
}

// ─── LedgerChain ───────────────────────────────────────────

describe('LedgerChain', () => {
  it('empty() produces zero-length chain', () => {
    const chain = LedgerChain.empty()
    expect(chain.length).toBe(0)
    expect(chain.lastEntry).toBeNull()
    expect(chain.lastSequence).toBeNull()
    expect(chain.getAll()).toHaveLength(0)
  })

  it('append() single entry increments length', () => {
    const chain = LedgerChain.empty().append(makeEntry(1n))
    expect(chain.length).toBe(1)
    expect(chain.lastSequence).toBe(1n)
    expect(chain.lastEntry?.sequence).toBe(1n)
  })

  it('append() 5 entries in sequence — all present in order', () => {
    let chain = LedgerChain.empty()
    for (let i = 1; i <= 5; i++) chain = chain.append(makeEntry(BigInt(i)))
    expect(chain.length).toBe(5)
    const all = chain.getAll()
    for (let i = 0; i < 5; i++) expect(all[i]?.sequence).toBe(BigInt(i + 1))
  })

  it('append() is immutable — original chain unaffected', () => {
    const a = LedgerChain.empty()
    const b = a.append(makeEntry(1n))
    const c = b.append(makeEntry(2n))
    expect(a.length).toBe(0)
    expect(b.length).toBe(1)
    expect(c.length).toBe(2)
  })

  it('append() throws LedgerConstraintError on equal sequence', () => {
    const chain = LedgerChain.empty().append(makeEntry(3n))
    expect(() => chain.append(makeEntry(3n))).toThrow(LedgerConstraintError)
  })

  it('append() throws LedgerConstraintError on decreasing sequence', () => {
    const chain = LedgerChain.empty().append(makeEntry(5n))
    expect(() => chain.append(makeEntry(2n))).toThrow(LedgerConstraintError)
  })

  it('getAll() returns frozen array', () => {
    const chain = LedgerChain.empty().append(makeEntry(1n)).append(makeEntry(2n))
    expect(Object.isFrozen(chain.getAll())).toBe(true)
  })

  it('getAll() — entries are frozen objects', () => {
    const chain = LedgerChain.empty().append(makeEntry(1n))
    const entries = chain.getAll()
    expect(Object.isFrozen(entries[0])).toBe(true)
  })

  it('sequence gaps are allowed (non-contiguous)', () => {
    let chain = LedgerChain.empty()
    chain = chain.append(makeEntry(1n))
    chain = chain.append(makeEntry(10n))
    chain = chain.append(makeEntry(100n))
    expect(chain.length).toBe(3)
    expect(chain.lastSequence).toBe(100n)
  })
})

// ─── captureCheckpoint ─────────────────────────────────────

describe('captureCheckpoint', () => {
  it('empty chain produces valid snapshot with zero-entry merkle root', async () => {
    const snap = await captureCheckpoint(LedgerChain.empty())
    expect(snap.entry_count).toBe(0)
    expect(snap.entries).toHaveLength(0)
    expect(snap.is_replay_reconstructable).toBe(true)
    expect(snap.merkle_root).toHaveLength(64)
    expect(snap.schema_version).toBe('1.0.0')
  })

  it('snapshot is deeply frozen', async () => {
    const snap = await captureCheckpoint(LedgerChain.empty().append(makeEntry(1n)))
    expect(Object.isFrozen(snap)).toBe(true)
    expect(Object.isFrozen(snap.entries)).toBe(true)
  })

  it('captureCheckpoint is deterministic — same chain → same root 3×', async () => {
    const chain = LedgerChain.empty()
      .append(makeEntry(1n))
      .append(makeEntry(2n))
      .append(makeEntry(3n))
    const r1 = await captureCheckpoint(chain)
    const r2 = await captureCheckpoint(chain)
    const r3 = await captureCheckpoint(chain)
    expect(r1.merkle_root).toBe(r2.merkle_root)
    expect(r2.merkle_root).toBe(r3.merkle_root)
    expect(r1.merkle_root).toHaveLength(64)
  })

  it('different entries produce different merkle roots', async () => {
    const chain1 = LedgerChain.empty().append(makeEntry(1n))
    const chain2 = LedgerChain.empty().append({
      ...makeEntry(1n),
      frame_hash: ('a'.repeat(64)) as SHA256Hex,
    })
    const r1 = await captureCheckpoint(chain1)
    const r2 = await captureCheckpoint(chain2)
    expect(r1.merkle_root).not.toBe(r2.merkle_root)
  })

  it('snapshot_sequence reflects last entry sequence', async () => {
    const chain = LedgerChain.empty().append(makeEntry(7n)).append(makeEntry(99n))
    const snap = await captureCheckpoint(chain)
    expect(snap.snapshot_sequence).toBe(99n)
    expect(snap.entry_count).toBe(2)
  })
})

// ─── verifyChain ───────────────────────────────────────────

describe('verifyChain', () => {
  it('empty entries → valid', async () => {
    const r = await verifyChain([])
    expect(r.valid).toBe(true)
    expect(r.verified_entries).toBe(0)
  })

  it('valid single-entry chain passes (genesis anchor)', async () => {
    const entry = makeEntry(1n, GENESIS_HASH)
    const r = await verifyChain([entry])
    expect(r.valid).toBe(true)
    expect(r.verified_entries).toBe(1)
  })

  it('valid 3-entry chain with correct hashes passes', async () => {
    const { entries } = await buildChain(3)
    const r = await verifyChain(entries)
    expect(r.valid).toBe(true)
    expect(r.verified_entries).toBe(3)
  })

  it('broken hash chain detected at entry 2', async () => {
    const { entries } = await buildChain(3)
    // Tamper: replace entry[1].previous_hash with wrong value
    const tampered = [
      entries[0]!,
      { ...entries[1]!, previous_hash: 'b'.repeat(64) as SHA256Hex },
      entries[2]!,
    ]
    const r = await verifyChain(tampered)
    expect(r.valid).toBe(false)
    expect(r.reason).toContain('hash chain broken')
  })

  it('first entry with non-genesis previous_hash → invalid', async () => {
    const bad = makeEntry(1n, 'a'.repeat(64) as SHA256Hex)
    const r = await verifyChain([bad])
    expect(r.valid).toBe(false)
    expect(r.reason).toContain('GENESIS_HASH')
  })

  it('non-monotonic sequence detected', async () => {
    const e1 = makeEntry(1n, GENESIS_HASH)
    const e1hash = await hashValue(e1) as SHA256Hex
    const e3 = makeEntry(3n, e1hash)
    const e3hash = await hashValue(e3) as SHA256Hex
    // entry with lower sequence inserted after e3
    const e2 = makeEntry(2n, e3hash)
    const r = await verifyChain([e1, e3, e2])
    expect(r.valid).toBe(false)
    expect(r.reason).toContain('not strictly after')
  })
})

// ─── verifySequences ───────────────────────────────────────

describe('verifySequences (synchronous)', () => {
  it('empty → valid', () => {
    expect(verifySequences([]).valid).toBe(true)
  })

  it('strictly monotonic [1,2,3] → valid', () => {
    const entries = [makeEntry(1n), makeEntry(2n), makeEntry(3n)]
    expect(verifySequences(entries).valid).toBe(true)
  })

  it('non-monotonic [1,3,2] → invalid', () => {
    const entries = [makeEntry(1n), makeEntry(3n), makeEntry(2n)]
    const r = verifySequences(entries)
    expect(r.valid).toBe(false)
    expect(r.failed_at_sequence).toBe(2n)
  })
})
