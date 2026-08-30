// ============================================================
// Gate 55 — CRDT Convergence Adversarial
// ~22 tests: G-Set join at 150-entry scale (100+100, 50 overlap),
//   3-way associativity at scale (40+40+40 = 120 entries),
//   10× determinism on identical input, conflict detection at
//   specific position inside a 50-entry chain.
//
// Gaps filled vs test/unit/crdt.test.ts:
//   - Large-scale join (100 entries per side, 50-entry overlap)
//   - 3-way associativity: join(join(A,B),C) = join(A,join(B,C))
//   - 10× concurrent-equivalent determinism check (sync function)
//   - Conflict at sequence 25 of 50 (not position 0 or last)
//   - Result order: always ascending by sequence
//   - Idempotency at scale: join(A,A) = A for 100-entry set
// ============================================================

import { describe, it, expect } from 'vitest'
import { joinLedgerEntries } from '../../src/crdt/ledger.js'
import { CRDTConflictError } from '../../src/crdt/types.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const TS = 1_600_000_000_000

function makeEntry(n: number, frameChar = 'a'): LedgerEntry {
  return Object.freeze<LedgerEntry>({
    sequence: seq(n),
    previous_hash: GENESIS_HASH,
    frame_hash: h(frameChar),
    governance_hash: h('g'),
    timestamp_ms: TS + n,
  })
}

function buildRange(start: number, end: number, frameChar = 'a'): LedgerEntry[] {
  return Array.from({ length: end - start + 1 }, (_, i) => makeEntry(start + i, frameChar))
}

// ─── Large-scale join ─────────────────────────────────────

describe('CRDT: large-scale G-Set join', () => {
  it('100+100 entries with 50-entry overlap → 150 unique entries', () => {
    const setA = buildRange(1, 100)    // seq 1–100
    const setB = buildRange(51, 150)   // seq 51–150 (overlap: 51–100)
    const joined = joinLedgerEntries(setA, setB)
    expect(joined.length).toBe(150)
  })

  it('result is sorted ascending by sequence', () => {
    const setA = buildRange(1, 100)
    const setB = buildRange(51, 150)
    const joined = joinLedgerEntries(setA, setB)
    for (let i = 0; i < joined.length - 1; i++) {
      expect(joined[i]!.sequence < joined[i + 1]!.sequence).toBe(true)
    }
  })

  it('first sequence = 1, last sequence = 150', () => {
    const setA = buildRange(1, 100)
    const setB = buildRange(51, 150)
    const joined = joinLedgerEntries(setA, setB)
    expect(joined[0]!.sequence).toBe(seq(1))
    expect(joined[149]!.sequence).toBe(seq(150))
  })

  it('join is commutative at scale: join(A,B) same as join(B,A)', () => {
    const setA = buildRange(1, 100)
    const setB = buildRange(51, 150)
    const ab = joinLedgerEntries(setA, setB)
    const ba = joinLedgerEntries(setB, setA)
    expect(ab.length).toBe(ba.length)
    for (let i = 0; i < ab.length; i++) {
      expect(ab[i]!.sequence).toBe(ba[i]!.sequence)
    }
  })

  it('idempotency at scale: join(A,A) = A for 100-entry set', () => {
    const setA = buildRange(1, 100)
    const joined = joinLedgerEntries(setA, setA)
    expect(joined.length).toBe(100)
    for (let i = 0; i < 100; i++) {
      expect(joined[i]!.sequence).toBe(seq(i + 1))
    }
  })

  it('join with empty produces original set (left identity)', () => {
    const setA = buildRange(1, 80)
    const joined = joinLedgerEntries(setA, [])
    expect(joined.length).toBe(80)
  })

  it('join with empty produces original set (right identity)', () => {
    const setA = buildRange(1, 80)
    const joined = joinLedgerEntries([], setA)
    expect(joined.length).toBe(80)
  })
})

// ─── 3-way associativity ──────────────────────────────────

describe('CRDT: 3-way associativity at scale', () => {
  const setA = buildRange(1, 40)
  const setB = buildRange(41, 80)
  const setC = buildRange(81, 120)

  it('join(join(A,B),C) has 120 entries', () => {
    expect(joinLedgerEntries(joinLedgerEntries(setA, setB), setC).length).toBe(120)
  })

  it('join(A,join(B,C)) has 120 entries', () => {
    expect(joinLedgerEntries(setA, joinLedgerEntries(setB, setC)).length).toBe(120)
  })

  it('join(join(A,B),C) and join(A,join(B,C)) produce identical sequence order', () => {
    const lhs = joinLedgerEntries(joinLedgerEntries(setA, setB), setC)
    const rhs = joinLedgerEntries(setA, joinLedgerEntries(setB, setC))
    expect(lhs.length).toBe(rhs.length)
    for (let i = 0; i < lhs.length; i++) {
      expect(lhs[i]!.sequence).toBe(rhs[i]!.sequence)
      expect(lhs[i]!.frame_hash).toBe(rhs[i]!.frame_hash)
    }
  })

  it('all entries span sequences 1–120 in both groupings', () => {
    const lhs = joinLedgerEntries(joinLedgerEntries(setA, setB), setC)
    expect(lhs[0]!.sequence).toBe(seq(1))
    expect(lhs[119]!.sequence).toBe(seq(120))
  })
})

// ─── Determinism (10× identical calls) ────────────────────

describe('CRDT: joinLedgerEntries determinism', () => {
  it('10 calls on identical 100-entry inputs → identical lengths', () => {
    const setA = buildRange(1, 60)
    const setB = buildRange(31, 90)
    const results = Array.from({ length: 10 }, () => joinLedgerEntries(setA, setB))
    for (const r of results) expect(r.length).toBe(results[0]!.length)
  })

  it('10 calls → identical first and last sequences', () => {
    const setA = buildRange(1, 60)
    const setB = buildRange(31, 90)
    const results = Array.from({ length: 10 }, () => joinLedgerEntries(setA, setB))
    for (const r of results) {
      expect(r[0]!.sequence).toBe(results[0]![0]!.sequence)
      expect(r[r.length - 1]!.sequence).toBe(results[0]![results[0]!.length - 1]!.sequence)
    }
  })

  it('result is frozen', () => {
    const joined = joinLedgerEntries(buildRange(1, 5), buildRange(3, 8))
    expect(Object.isFrozen(joined)).toBe(true)
  })
})

// ─── Conflict detection ───────────────────────────────────

describe('CRDT: conflict detection at scale', () => {
  it('conflict at sequence 1 (first position) → throws CRDTConflictError', () => {
    const setA = [makeEntry(1, 'a'), makeEntry(2, 'a'), makeEntry(3, 'a')]
    const setB = [makeEntry(1, 'x'), makeEntry(2, 'a'), makeEntry(3, 'a')]
    expect(() => joinLedgerEntries(setA, setB)).toThrow(CRDTConflictError)
  })

  it('conflict at sequence 25 of 50 → throws CRDTConflictError', () => {
    const setA = buildRange(1, 50, 'a')
    const setB = [
      ...buildRange(1, 24, 'a'),
      makeEntry(25, 'x'),          // tampered
      ...buildRange(26, 50, 'a'),
    ]
    expect(() => joinLedgerEntries(setA, setB)).toThrow(CRDTConflictError)
  })

  it('conflict at last position (sequence 50) → throws CRDTConflictError', () => {
    const setA = buildRange(1, 50, 'a')
    const setB = [...buildRange(1, 49, 'a'), makeEntry(50, 'x')]
    expect(() => joinLedgerEntries(setA, setB)).toThrow(CRDTConflictError)
  })

  it('CRDTConflictError is instance of Error', () => {
    const err = new CRDTConflictError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('CRDTConflictError')
  })

  it('error message includes the conflicting sequence number', () => {
    const setA = [makeEntry(7, 'a')]
    const setB = [makeEntry(7, 'x')]
    try {
      joinLedgerEntries(setA, setB)
      expect.fail('should have thrown')
    } catch (e) {
      expect((e as CRDTConflictError).message).toContain('7')
    }
  })
})
