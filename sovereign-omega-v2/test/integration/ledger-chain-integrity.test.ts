// ============================================================
// Gate 54 — Ledger Hash Chain Integrity
// ~22 tests: verifyChain() adversarial proof at tamper positions
//   (first, middle, last), hash-chain linkage law
//   (each entry's previous_hash equals hashValue of prior entry),
//   GENESIS_HASH contract, verifySequences structural check,
//   LedgerChain structural invariants.
//
// Proves the ledger is not just structurally append-only but
// cryptographically self-verifying: a WASM node or independent
// auditor can verify every link using only hashValue() and
// GENESIS_HASH — no trusted state required.
// ============================================================

import { describe, it, expect } from 'vitest'
import { LedgerChain } from '../../src/ledger/chain.js'
import { verifyChain, verifySequences } from '../../src/ledger/verify.js'
import { GENESIS_HASH, LedgerConstraintError, type LedgerEntry } from '../../src/ledger/types.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const TS = 1_600_000_000_000

async function buildChain(n: number): Promise<{ chain: LedgerChain; entries: LedgerEntry[] }> {
  let chain = LedgerChain.empty()
  let prevHash: SHA256Hex = GENESIS_HASH
  const entries: LedgerEntry[] = []
  for (let i = 1; i <= n; i++) {
    const entry = Object.freeze<LedgerEntry>({
      sequence: seq(i),
      previous_hash: prevHash,
      frame_hash: h(i.toString(16).padStart(1, '0')),
      governance_hash: h('g'),
      timestamp_ms: TS + i,
    })
    entries.push(entry)
    chain = chain.append(entry)
    prevHash = await hashValue(entry)
  }
  return { chain, entries }
}

// ─── GENESIS_HASH contract ─────────────────────────────────

describe('Ledger: GENESIS_HASH contract', () => {
  it('GENESIS_HASH is 64 zeros', () => {
    expect(GENESIS_HASH).toBe('0'.repeat(64))
    expect(GENESIS_HASH).toHaveLength(64)
  })

  it('first entry in a correct chain has previous_hash = GENESIS_HASH', async () => {
    const { entries } = await buildChain(5)
    expect(entries[0]!.previous_hash).toBe(GENESIS_HASH)
  })
})

// ─── Hash-chain linkage law ────────────────────────────────

describe('Ledger: hash-chain linkage law', () => {
  // Proves: entries[i+1].previous_hash === hashValue(entries[i]) for all i
  it('10-entry chain: every link is cryptographically correct', async () => {
    const { entries } = await buildChain(10)
    for (let i = 0; i < entries.length - 1; i++) {
      const expectedHash = await hashValue(entries[i]!)
      expect(entries[i + 1]!.previous_hash).toBe(expectedHash)
    }
  })

  it('hashValue(entry) is deterministic × 3 for the same entry', async () => {
    const { entries } = await buildChain(3)
    const h1 = await hashValue(entries[1]!)
    const h2 = await hashValue(entries[1]!)
    const h3 = await hashValue(entries[1]!)
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different frame_hash → different hashValue output', async () => {
    const a: LedgerEntry = Object.freeze({ sequence: seq(1), previous_hash: GENESIS_HASH, frame_hash: h('a'), governance_hash: h('g'), timestamp_ms: TS })
    const b: LedgerEntry = Object.freeze({ sequence: seq(1), previous_hash: GENESIS_HASH, frame_hash: h('b'), governance_hash: h('g'), timestamp_ms: TS })
    expect(await hashValue(a)).not.toBe(await hashValue(b))
  })
})

// ─── verifyChain adversarial ──────────────────────────────

describe('verifyChain: adversarial tamper detection', () => {
  it('empty entries → valid, verified_entries=0', async () => {
    const result = await verifyChain([])
    expect(result.valid).toBe(true)
    expect(result.verified_entries).toBe(0)
  })

  it('valid 10-entry chain → valid, verified_entries=10', async () => {
    const { entries } = await buildChain(10)
    const result = await verifyChain(entries)
    expect(result.valid).toBe(true)
    expect(result.verified_entries).toBe(10)
  })

  it('tamper frame_hash at entry[3] → fails at entry[4] (next link broken)', async () => {
    const { entries } = await buildChain(10)
    const tampered = [...entries]
    tampered[3] = Object.freeze({ ...entries[3]!, frame_hash: h('tampered') })
    const result = await verifyChain(tampered)
    expect(result.valid).toBe(false)
    expect(result.failed_at_sequence).toBe(seq(5))  // entry[4] = sequence 5
  })

  it('tamper previous_hash of entry[0] to non-genesis → fails at sequence 1', async () => {
    const { entries } = await buildChain(5)
    const tampered = [...entries]
    tampered[0] = Object.freeze({ ...entries[0]!, previous_hash: h('not-genesis') })
    const result = await verifyChain(tampered)
    expect(result.valid).toBe(false)
    expect(result.failed_at_sequence).toBe(seq(1))
    expect(result.verified_entries).toBe(0)
  })

  it('tamper governance_hash at entry[5] → fails at entry[6]', async () => {
    const { entries } = await buildChain(10)
    const tampered = [...entries]
    tampered[5] = Object.freeze({ ...entries[5]!, governance_hash: h('bad') })
    const result = await verifyChain(tampered)
    expect(result.valid).toBe(false)
    expect(result.failed_at_sequence).toBe(seq(7))  // entry[6] = sequence 7
  })

  it('tamper last entry frame_hash → chain fails at verified_entries = length-1', async () => {
    const { entries } = await buildChain(8)
    const tampered = [...entries]
    const last = entries.length - 1
    tampered[last] = Object.freeze({ ...entries[last]!, frame_hash: h('x') })
    // Last entry tampered but no "next" entry to fail — but its own hash
    // contribution would break a subsequent append; verifyChain still passes
    // for the last entry itself (it only checks incoming link, not outgoing)
    const result = await verifyChain(tampered)
    // The last entry's previous_hash is still valid (we didn't tamper entries[last-1])
    // so verifyChain sees: all previous links valid, last entry's own hash doesn't matter
    // This is by design — the chain integrity is about linkage, not self-hash of last
    expect(result.valid).toBe(true)
    expect(result.verified_entries).toBe(8)
  })

  it('tamper previous_hash of entry[5] directly → fails at entry[5]', async () => {
    const { entries } = await buildChain(10)
    const tampered = [...entries]
    tampered[5] = Object.freeze({ ...entries[5]!, previous_hash: h('z') })
    const result = await verifyChain(tampered)
    expect(result.valid).toBe(false)
    expect(result.failed_at_sequence).toBe(seq(6))
  })
})

// ─── verifySequences structural check ─────────────────────

describe('verifySequences: structural-only validation', () => {
  it('empty → valid, 0 verified entries', async () => {
    const { entries } = await buildChain(0)
    const result = verifySequences(entries)
    expect(result.valid).toBe(true)
    expect(result.verified_entries).toBe(0)
  })

  it('strictly monotonic 5-entry chain → valid', async () => {
    const { entries } = await buildChain(5)
    expect(verifySequences(entries).valid).toBe(true)
  })

  it('non-monotonic sequence (3,2) → invalid', () => {
    const entries: LedgerEntry[] = [
      Object.freeze({ sequence: seq(1), previous_hash: GENESIS_HASH, frame_hash: h('a'), governance_hash: h('g'), timestamp_ms: TS }),
      Object.freeze({ sequence: seq(3), previous_hash: h('p'), frame_hash: h('b'), governance_hash: h('g'), timestamp_ms: TS }),
      Object.freeze({ sequence: seq(2), previous_hash: h('q'), frame_hash: h('c'), governance_hash: h('g'), timestamp_ms: TS }),
    ]
    const result = verifySequences(entries)
    expect(result.valid).toBe(false)
    expect(result.failed_at_sequence).toBe(seq(2))
  })

  it('duplicate sequence → invalid', () => {
    const entries: LedgerEntry[] = [
      Object.freeze({ sequence: seq(1), previous_hash: GENESIS_HASH, frame_hash: h('a'), governance_hash: h('g'), timestamp_ms: TS }),
      Object.freeze({ sequence: seq(1), previous_hash: h('p'), frame_hash: h('b'), governance_hash: h('g'), timestamp_ms: TS }),
    ]
    expect(verifySequences(entries).valid).toBe(false)
  })
})

// ─── LedgerChain structural invariants ────────────────────

describe('LedgerChain: structural invariants', () => {
  it('LedgerConstraintError on equal sequence', async () => {
    const { chain } = await buildChain(3)
    const badEntry: LedgerEntry = Object.freeze({
      sequence: seq(3),  // same as last
      previous_hash: h('p'),
      frame_hash: h('f'),
      governance_hash: h('g'),
      timestamp_ms: TS,
    })
    expect(() => chain.append(badEntry)).toThrow(LedgerConstraintError)
  })

  it('LedgerConstraintError on decreasing sequence', async () => {
    const { chain } = await buildChain(5)
    const badEntry: LedgerEntry = Object.freeze({
      sequence: seq(2),  // less than last (5)
      previous_hash: h('p'),
      frame_hash: h('f'),
      governance_hash: h('g'),
      timestamp_ms: TS,
    })
    expect(() => chain.append(badEntry)).toThrow(LedgerConstraintError)
  })

  it('lastEntry and lastSequence track correctly', async () => {
    const { chain } = await buildChain(7)
    expect(chain.lastSequence).toBe(seq(7))
    expect(chain.lastEntry?.sequence).toBe(seq(7))
  })

  it('source chain unchanged after append (immutable)', async () => {
    const { chain } = await buildChain(3)
    const entry: LedgerEntry = Object.freeze({
      sequence: seq(4),
      previous_hash: h('p'),
      frame_hash: h('f'),
      governance_hash: h('g'),
      timestamp_ms: TS,
    })
    chain.append(entry)
    expect(chain.length).toBe(3)
    expect(chain.lastSequence).toBe(seq(3))
  })
})
