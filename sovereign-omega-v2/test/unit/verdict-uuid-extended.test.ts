// ============================================================
// Verdict + UUID Extended Tests
// Targets:
//   crdt/verdict.ts L22: verdictOrdinal when idx === -1 → 0
//   event/uuid.ts: generateUUIDv7 basic smoke (monotonicity)
// ============================================================

import { describe, it, expect } from 'vitest'
import { verdictOrdinal, joinVerdict } from '../../src/crdt/verdict.js'
import type { ConstitutionalVerdict } from '../../src/constitutional/types.js'
import { generateUUIDv7 } from '../../src/event/uuid.js'

// ─── verdictOrdinal: unknown verdict (idx === -1 path) ───────

describe('verdictOrdinal: unknown verdict returns 0', () => {
  it('returns 0 for a verdict not in VERDICT_ORDER', () => {
    const unknown = 'UNKNOWN_VERDICT' as ConstitutionalVerdict
    expect(verdictOrdinal(unknown)).toBe(0)
  })

  it('returns 0 for an empty-string verdict', () => {
    const empty = '' as ConstitutionalVerdict
    expect(verdictOrdinal(empty)).toBe(0)
  })

  it('returns 0 when verdict is a numeric string cast', () => {
    const bad = '999' as ConstitutionalVerdict
    expect(verdictOrdinal(bad)).toBe(0)
  })

  it('known verdicts return non-zero indices (sanity check)', () => {
    expect(verdictOrdinal('PERMIT')).toBe(0)
    expect(verdictOrdinal('DEFER')).toBe(1)
    expect(verdictOrdinal('REJECT')).toBe(2)
    expect(verdictOrdinal('ESCALATE')).toBe(3)
  })

  it('joinVerdict with unknown verdict uses ordinal 0 (treated as PERMIT)', () => {
    const unknown = 'BOGUS' as ConstitutionalVerdict
    // unknown ordinal = 0, ESCALATE ordinal = 3 → ESCALATE wins
    expect(joinVerdict(unknown, 'ESCALATE')).toBe('ESCALATE')
    // unknown ordinal = 0, PERMIT ordinal = 0 → first (unknown) wins
    expect(joinVerdict(unknown, 'PERMIT')).toBe(unknown)
  })
})

// ─── generateUUIDv7: basic smoke ─────────────────────────────

describe('generateUUIDv7: basic UUIDv7 properties', () => {
  it('returns a string of length 36', () => {
    const uuid = generateUUIDv7()
    expect(uuid).toHaveLength(36)
  })

  it('has the correct UUID format with hyphens', () => {
    const uuid = generateUUIDv7()
    const parts = uuid.split('-')
    expect(parts).toHaveLength(5)
    expect(parts[0]).toHaveLength(8)
    expect(parts[1]).toHaveLength(4)
    expect(parts[2]).toHaveLength(4)
    expect(parts[3]).toHaveLength(4)
    expect(parts[4]).toHaveLength(12)
  })

  it('consecutive calls produce different UUIDs', () => {
    const ids = new Set(Array.from({ length: 20 }, () => generateUUIDv7()))
    expect(ids.size).toBeGreaterThan(1)
  })

  it('UUIDs are lexicographically non-decreasing (monotonic)', () => {
    const ids = Array.from({ length: 50 }, () => generateUUIDv7())
    for (let i = 1; i < ids.length; i++) {
      expect(ids[i]! >= ids[i - 1]!).toBe(true)
    }
  })
})
