// ============================================================
// Gate 20 — CRDT Convergence Lattice Tests
// ~24 tests: SITRState join laws, verdict join laws, ledger
//   G-Set join, conflict detection, fold helpers.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SITRState } from '../../src/sitr/types.js'
import type { ConstitutionalVerdict } from '../../src/constitutional/types.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import { joinSITRState, foldSITRStates, sitrLeq } from '../../src/crdt/sitr.js'
import { joinVerdict, foldVerdicts, verdictLeq } from '../../src/crdt/verdict.js'
import { joinLedgerEntries } from '../../src/crdt/ledger.js'
import { CRDTConflictError } from '../../src/crdt/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

// ─── Helpers ───────────────────────────────────────────────

const TS = 1_600_000_000_000

function makeEntry(seq: bigint, frameSeed = 'f'): LedgerEntry {
  return Object.freeze({
    sequence: seq as SequenceNumber,
    previous_hash: GENESIS_HASH,
    frame_hash: (frameSeed.repeat(64)) as SHA256Hex,
    governance_hash: ('e'.repeat(64)) as SHA256Hex,
    timestamp_ms: TS + Number(seq),
  })
}

// ─── SITRState join ────────────────────────────────────────

describe('joinSITRState — semilattice laws', () => {
  const states: SITRState[] = ['STABLE', 'DEGRADED', 'UNSTABLE', 'CONSTITUTIONAL_RISK', 'CONTAINED', 'COMPROMISED']

  it('idempotent: join(a, a) = a for all states', () => {
    for (const s of states) {
      expect(joinSITRState(s, s)).toBe(s)
    }
  })

  it('commutative: join(a, b) = join(b, a)', () => {
    for (const a of states) {
      for (const b of states) {
        expect(joinSITRState(a, b)).toBe(joinSITRState(b, a))
      }
    }
  })

  it('associative: join(join(a,b),c) = join(a,join(b,c))', () => {
    const triple: SITRState[] = ['STABLE', 'UNSTABLE', 'COMPROMISED']
    const [a, b, c] = triple as [SITRState, SITRState, SITRState]
    expect(joinSITRState(joinSITRState(a, b), c))
      .toBe(joinSITRState(a, joinSITRState(b, c)))
  })

  it('COMPROMISED dominates all', () => {
    for (const s of states) {
      expect(joinSITRState('COMPROMISED', s)).toBe('COMPROMISED')
    }
  })

  it('STABLE is the bottom element', () => {
    for (const s of states) {
      expect(joinSITRState('STABLE', s)).toBe(s)
    }
  })

  it('foldSITRStates([]) = STABLE (lattice bottom)', () => {
    expect(foldSITRStates([])).toBe('STABLE')
  })

  it('foldSITRStates picks maximum', () => {
    expect(foldSITRStates(['STABLE', 'DEGRADED', 'CONTAINED'])).toBe('CONTAINED')
  })

  it('sitrLeq: STABLE ≤ COMPROMISED', () => {
    expect(sitrLeq('STABLE', 'COMPROMISED')).toBe(true)
    expect(sitrLeq('COMPROMISED', 'STABLE')).toBe(false)
  })
})

// ─── ConstitutionalVerdict join ────────────────────────────

describe('joinVerdict — semilattice laws', () => {
  const verdicts: ConstitutionalVerdict[] = ['PERMIT', 'DEFER', 'REJECT', 'ESCALATE']

  it('idempotent: join(v, v) = v for all verdicts', () => {
    for (const v of verdicts) {
      expect(joinVerdict(v, v)).toBe(v)
    }
  })

  it('commutative: join(a, b) = join(b, a)', () => {
    for (const a of verdicts) {
      for (const b of verdicts) {
        expect(joinVerdict(a, b)).toBe(joinVerdict(b, a))
      }
    }
  })

  it('ESCALATE dominates all', () => {
    for (const v of verdicts) {
      expect(joinVerdict('ESCALATE', v)).toBe('ESCALATE')
    }
  })

  it('PERMIT is the bottom element', () => {
    for (const v of verdicts) {
      expect(joinVerdict('PERMIT', v)).toBe(v)
    }
  })

  it('REJECT vs DEFER → REJECT', () => {
    expect(joinVerdict('REJECT', 'DEFER')).toBe('REJECT')
  })

  it('foldVerdicts([]) = PERMIT (lattice bottom)', () => {
    expect(foldVerdicts([])).toBe('PERMIT')
  })

  it('foldVerdicts picks most restrictive', () => {
    expect(foldVerdicts(['PERMIT', 'DEFER', 'REJECT'])).toBe('REJECT')
  })

  it('verdictLeq: PERMIT ≤ ESCALATE', () => {
    expect(verdictLeq('PERMIT', 'ESCALATE')).toBe(true)
    expect(verdictLeq('ESCALATE', 'PERMIT')).toBe(false)
  })
})

// ─── LedgerEntry G-Set join ────────────────────────────────

describe('joinLedgerEntries — G-Set CRDT', () => {
  it('join([], []) = []', () => {
    expect(joinLedgerEntries([], [])).toHaveLength(0)
  })

  it('join(A, []) = A (identity on right)', () => {
    const a = [makeEntry(1n), makeEntry(2n)]
    const result = joinLedgerEntries(a, [])
    expect(result).toHaveLength(2)
  })

  it('join([], B) = B (identity on left)', () => {
    const b = [makeEntry(1n), makeEntry(2n)]
    const result = joinLedgerEntries([], b)
    expect(result).toHaveLength(2)
  })

  it('disjoint sets merged and sorted by sequence', () => {
    const a = [makeEntry(1n), makeEntry(3n)]
    const b = [makeEntry(2n), makeEntry(4n)]
    const result = joinLedgerEntries(a, b)
    expect(result.map(e => e.sequence)).toEqual([1n, 2n, 3n, 4n])
  })

  it('idempotent: join(A, A) = A', () => {
    const a = [makeEntry(1n), makeEntry(2n)]
    const result = joinLedgerEntries(a, a)
    expect(result).toHaveLength(2)
  })

  it('commutative: join(A, B) sequence order matches join(B, A)', () => {
    const a = [makeEntry(1n), makeEntry(3n)]
    const b = [makeEntry(2n), makeEntry(4n)]
    const r1 = joinLedgerEntries(a, b)
    const r2 = joinLedgerEntries(b, a)
    expect(r1.map(e => e.sequence)).toEqual(r2.map(e => e.sequence))
  })

  it('duplicate identical entry deduplicated without error', () => {
    const entry = makeEntry(5n)
    const result = joinLedgerEntries([entry], [entry])
    expect(result).toHaveLength(1)
    expect(result[0]?.sequence).toBe(5n)
  })

  it('conflict: same sequence, different content → CRDTConflictError', () => {
    const e1 = makeEntry(1n, 'a')
    const e2 = makeEntry(1n, 'b')  // same sequence, different frame_hash
    expect(() => joinLedgerEntries([e1], [e2])).toThrow(CRDTConflictError)
  })

  it('result is frozen', () => {
    const result = joinLedgerEntries([makeEntry(1n)], [makeEntry(2n)])
    expect(Object.isFrozen(result)).toBe(true)
  })
})
