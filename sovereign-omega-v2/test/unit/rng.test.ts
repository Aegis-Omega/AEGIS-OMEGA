// ============================================================
// SeededRNG Tests — calibration/rng.ts
// EPISTEMIC TIER: T0
// Full coverage: constructor, next(), sampleIndices(), deriveSeed()
// ============================================================

import { describe, it, expect } from 'vitest'
import { SeededRNG, deriveSeed } from '../../src/calibration/rng.js'

// ─── SeededRNG constructor + next() ──────────────────────

describe('SeededRNG: determinism (same seed → same sequence)', () => {
  it('produces identical sequence × 3 for the same seed', () => {
    const run = (seed: number) => {
      const rng = new SeededRNG(seed)
      return [rng.next(), rng.next(), rng.next()]
    }
    const r1 = run(42)
    const r2 = run(42)
    const r3 = run(42)
    expect(r1).toEqual(r2)
    expect(r2).toEqual(r3)
  })

  it('different seeds produce different sequences', () => {
    const run = (seed: number) => {
      const rng = new SeededRNG(seed)
      return [rng.next(), rng.next(), rng.next()]
    }
    expect(run(0)).not.toEqual(run(1))
    expect(run(42)).not.toEqual(run(99999))
    expect(run(0xdeadbeef)).not.toEqual(run(0xbeefdead))
  })

  it('seed 0 is valid and deterministic', () => {
    const a = new SeededRNG(0).next()
    const b = new SeededRNG(0).next()
    expect(a).toBe(b)
  })
})

describe('SeededRNG.next(): output range', () => {
  it('all values are in [0, 1)', () => {
    const rng = new SeededRNG(12345)
    for (let i = 0; i < 100; i++) {
      const v = rng.next()
      expect(v).toBeGreaterThanOrEqual(0)
      expect(v).toBeLessThan(1)
    }
  })

  it('advances state — consecutive calls return different values', () => {
    const rng = new SeededRNG(99)
    const seen = new Set<number>()
    for (let i = 0; i < 20; i++) seen.add(rng.next())
    // Very unlikely to have <5 unique values in 20 draws from a quality PRNG
    expect(seen.size).toBeGreaterThan(5)
  })
})

// ─── sampleIndices ────────────────────────────────────────

describe('SeededRNG.sampleIndices()', () => {
  it('returns n unique indices from [0, max)', () => {
    const rng = new SeededRNG(7)
    const indices = rng.sampleIndices(5, 10)
    expect(indices).toHaveLength(5)
    expect(new Set(indices).size).toBe(5)
    indices.forEach(i => {
      expect(i).toBeGreaterThanOrEqual(0)
      expect(i).toBeLessThan(10)
    })
  })

  it('returns all when n === max', () => {
    const rng = new SeededRNG(3)
    const indices = rng.sampleIndices(5, 5)
    expect(indices).toHaveLength(5)
    expect(new Set(indices).size).toBe(5)
  })

  it('returns empty array when n === 0', () => {
    const rng = new SeededRNG(1)
    expect(rng.sampleIndices(0, 10)).toHaveLength(0)
  })

  it('n > max — returns max items (pool exhausted)', () => {
    const rng = new SeededRNG(5)
    const indices = rng.sampleIndices(10, 3)
    expect(indices).toHaveLength(3)
  })

  it('is deterministic × 3', () => {
    const run = () => new SeededRNG(101).sampleIndices(4, 8)
    expect(run()).toEqual(run())
    expect(run()).toEqual(run())
  })
})

// ─── deriveSeed ───────────────────────────────────────────

describe('deriveSeed()', () => {
  it('returns a number', () => {
    expect(typeof deriveSeed('stream-1', 'epoch-1')).toBe('number')
  })

  it('is deterministic × 3 for same inputs', () => {
    const s1 = deriveSeed('stream-abc', 'epoch-001')
    const s2 = deriveSeed('stream-abc', 'epoch-001')
    const s3 = deriveSeed('stream-abc', 'epoch-001')
    expect(s1).toBe(s2)
    expect(s2).toBe(s3)
  })

  it('different streamId → different seed', () => {
    expect(deriveSeed('a', 'e')).not.toBe(deriveSeed('b', 'e'))
  })

  it('different epochId → different seed', () => {
    expect(deriveSeed('s', '1')).not.toBe(deriveSeed('s', '2'))
  })

  it('empty strings are valid inputs', () => {
    expect(typeof deriveSeed('', '')).toBe('number')
  })

  it('seed is unsigned 32-bit (>= 0)', () => {
    const seed = deriveSeed('stream', 'epoch')
    expect(seed).toBeGreaterThanOrEqual(0)
    expect(Number.isInteger(seed)).toBe(true)
  })
})
